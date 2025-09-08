import os
import json
import asyncio
import logging
from typing import Optional, Set, Dict

import httpx
from telegram import Bot, Update, Message
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError
import dotenv

dotenv.load_dotenv()

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(), logging.FileHandler("data/bot.log")]
)
logger = logging.getLogger("tg-audio-bot")

# =========================
# Config
# =========================
API_BASE_URL = "https://api.metisai.ir/openai/v1"

# =========================
# Storage Layer
# =========================


class Storage:
    """
    Persists:
      - VIP users
      - last update offset
    """

    def __init__(
        self,
        base_dir: str = "data",
        vip_path: str = "data/vip_users.json",
        offset_path: str = "data/last_offset.json",
    ):
        self.base_dir = base_dir
        self.vip_path = vip_path
        self.offset_path = offset_path
        self.files_dir = os.path.join(self.base_dir, "files")

        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.files_dir, exist_ok=True)

    async def load_vip_users(self) -> Set[int]:
        try:
            with open(self.vip_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("vip_users", []))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    async def save_vip_users(self, vip_users: Set[int]):
        with open(self.vip_path, "w", encoding="utf-8") as f:
            json.dump({"vip_users": list(vip_users)}, f, indent=2)

    async def load_offset(self) -> Optional[int]:
        try:
            with open(self.offset_path, "r", encoding="utf-8") as f:
                return json.load(f).get("offset")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    async def save_offset(self, offset: int):
        with open(self.offset_path, "w", encoding="utf-8") as f:
            json.dump({"offset": offset}, f, indent=2)

# =========================
# MetisAI Audio Client
# =========================


class AudioClient:
    """A client to interact with MetisAI audio endpoints."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.client = httpx.AsyncClient(
            base_url=API_BASE_URL, headers=self.headers, timeout=60.0)

    async def transcribe_audio(self, file_path: str) -> Optional[str]:
        """Sends an audio file for transcription (Speech-to-Text)."""
        try:
            with open(file_path, "rb") as audio_file:
                files = {"file": (os.path.basename(file_path), audio_file)}
                data = {"model": "whisper-1"}
                response = await self.client.post("/audio/transcriptions", files=files, data=data)
                response.raise_for_status()
                result = response.json()
                return result.get("text")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"API Error during transcription: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None

    async def generate_speech(self, text: str) -> Optional[bytes]:
        """Generates speech from text (Text-to-Speech)."""
        try:
            payload = {
                "model": "tts-1-hd",
                "input": text,
                "voice": "alloy"
            }
            response = await self.client.post("/audio/speech", json=payload)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.error(
                f"API Error during speech generation: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate speech: {e}")
            return None

    async def close(self):
        await self.client.close()

# =========================
# Telegram Bot
# =========================


class TelegramAudioBot:
    def __init__(
        self,
        bot_token: str,
        audio_client: AudioClient,
        storage: Storage,
        vip_code: str,
    ):
        self.bot = Bot(token=bot_token)
        self.api = audio_client
        self.storage = storage
        self.vip_code = vip_code

        self.vip_users: Set[int] = set()
        self.offset: Optional[int] = None

    async def start(self):
        """Loads state and starts the main bot loop."""
        self.offset = await self.storage.load_offset()
        self.vip_users = await self.storage.load_vip_users()

        bot_user = await self.bot.get_me()
        logger.info(f"🤖 Bot '{bot_user.full_name}' is running...")

        while True:
            try:
                updates = await self.bot.get_updates(
                    offset=self.offset,
                    limit=10,
                    timeout=30,
                    allowed_updates=["message"]
                )
                if updates:
                    await asyncio.gather(*[self.process_update(u) for u in updates])
                    self.offset = updates[-1].update_id + 1
                    await self.storage.save_offset(self.offset)
            except Exception as e:
                logger.error(f"Error fetching updates: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def process_update(self, update: Update):
        message = update.message
        if not message:
            return

        chat_id = message.chat.id
        text = (message.text or "").strip()

        # 1. VIP enrollment command
        if text and text == self.vip_code:
            self.vip_users.add(chat_id)
            await self.storage.save_vip_users(self.vip_users)
            await self.safe_send(chat_id, "🎉 تبریک! شما اکنون کاربر VIP هستید.", reply_to=message.message_id)
            return

        # 2. Access control
        if chat_id not in self.vip_users:
            await self.safe_send(chat_id, "🔒 برای استفاده از این ربات، لطفاً کد VIP خود را ارسال کنید.", reply_to=message.message_id)
            return

        # 3. Handle different message types
        try:
            if message.voice:
                await self.handle_voice(chat_id, message)
            elif message.text:
                await self.handle_text(chat_id, message)
            else:
                await self.safe_send(chat_id, "لطفاً یک پیام متنی یا صوتی ارسال کنید. ❌", reply_to=message.message_id)
        except Exception as e:
            logger.exception("Failed to process update")
            await self.safe_send(chat_id, "❌ خطایی در پردازش پیام شما رخ داد.", reply_to=message.message_id)

    async def handle_text(self, chat_id: int, message: Message):
        """Converts text to speech and sends it as a voice message, replying to the original."""
        await self.bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
        logger.info(f"Generating speech for chat {chat_id}...")

        audio_content = await self.api.generate_speech(message.text)

        if audio_content:
            await self.bot.send_voice(chat_id, voice=audio_content, reply_to_message_id=message.message_id)
            logger.info(f"Sent speech to chat {chat_id}.")
        else:
            await self.safe_send(chat_id, "⚠️ متاسفانه نتوانستم متن شما را به صوت تبدیل کنم.", reply_to=message.message_id)

    async def handle_voice(self, chat_id: int, message: Message):
        """Transcribes a voice message and sends the text back, replying to the original."""
        await self.bot.send_chat_action(chat_id, ChatAction.TYPING)

        file_path = None
        try:
            logger.info(f"Downloading voice message from chat {chat_id}...")
            voice_file = await self.bot.get_file(message.voice.file_id)
            file_path = os.path.join(
                self.storage.files_dir, f"{message.voice.file_id}.oga")
            await voice_file.download_to_drive(file_path)

            logger.info(f"Transcribing audio for chat {chat_id}...")
            transcribed_text = await self.api.transcribe_audio(file_path)

            if transcribed_text:
                await self.safe_send(chat_id, transcribed_text, reply_to=message.message_id)
                logger.info(f"Sent transcription to chat {chat_id}.")
            else:
                await self.safe_send(chat_id, "⚠️ متاسفانه نتوانستم این پیام صوتی را به متن تبدیل کنم.", reply_to=message.message_id)

        finally:
            # Clean up the downloaded file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.error(
                        f"Error removing temp audio file {file_path}: {e}")

    async def safe_send(self, chat_id: int, text: str, reply_to: Optional[int] = None):
        """Sends a message safely, with an optional reply_to parameter."""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=reply_to,
                disable_web_page_preview=True,
            )
        except TelegramError as e:
            logger.warning(
                f"Markdown send failed: {e}. Sending as plain text.")
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to,
                    disable_web_page_preview=True
                )
            except TelegramError as final_e:
                logger.error(
                    f"Final send attempt failed for chat {chat_id}: {final_e}")


# =========================
# Entrypoint
# =========================
async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    METIS_API_KEY = os.getenv("METIS_API_KEY")
    VIP_CODE = os.getenv("VIP_CODE", "VIP123")

    if not BOT_TOKEN or not METIS_API_KEY:
        logger.critical(
            "Missing required environment variables: BOT_TOKEN and METIS_API_KEY are required.")
        return

    storage = Storage()
    client = AudioClient(api_key=METIS_API_KEY)
    bot = TelegramAudioBot(
        bot_token=BOT_TOKEN,
        audio_client=client,
        storage=storage,
        vip_code=VIP_CODE,
    )

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down.")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
    finally:
        await client.close()
        logger.info("Bot has been shut down.")

if __name__ == "__main__":
    asyncio.run(main())
