# GoftarGPT Telegram Bot 🗣️🤖

A powerful and responsive Telegram bot that leverages AI for advanced audio processing. It can seamlessly transcribe voice messages into text and convert text messages back into high-quality speech. The bot includes a simple VIP system to manage user access.

This bot is built using Python with `asyncio` for high performance and relies on an OpenAI-compatible API for its AI capabilities.

-----

## ✨ Features

  * 🎤 **Speech-to-Text**: Send or forward any voice message, and the bot will instantly reply with the transcribed text.
  * ✍️ **Text-to-Speech**: Send a text message, and the bot will generate a high-quality voice message in response using a modern TTS model.
  * 🔐 **VIP Access Control**: The bot is private by default. Only users who provide a secret VIP code can access its core features.
  * 💾 **Persistent Storage**: VIP user lists and the bot's progress are saved locally to JSON files, ensuring data persists across restarts.
  * 📝 **Comprehensive Logging**: All important events are logged to both the console and a file (`data/bot.log`) for easy debugging and monitoring.
  * 🚀 **Asynchronous**: Built with `asyncio` to handle multiple user requests concurrently without blocking.

-----

## 🛠️ Setup and Installation

Follow these steps to get your own instance of the bot up and running.

### 1\. Prerequisites

  * **Python 3.8+**
  * A **Telegram Bot Token**. You can get one from [@BotFather](https://t.me/BotFather) on Telegram.
  * An **API Key** from an OpenAI-compatible service that provides audio endpoints (like MetisAI, as configured, or OpenAI itself).

### 2\. Clone the Repository

```bash
git clone https://github.com/mahdighaemi123/GoftarGPT
cd GoftarGPT
```

### 3\. Run the Bot

```bash
docker compose up -d
```

The bot will create a `data/` directory automatically to store logs and state files. You should see a log message in your console confirming that the bot is running.

-----

## 🚀 Usage

1.  **Start a chat** with your bot on Telegram.
2.  The bot will initially restrict access. **Send the `VIP_CODE`** that you defined in your `.env` file.
3.  The bot will confirm your VIP status. You can now use its features:
      * **To get text from a voice message**: Record and send a voice note, or forward one from another chat.
      * **To get a voice message from text**: Simply type and send any text message.

-----

## 📂 Project Structure

```
/
|
|-- data/                 # Auto-generated for logs and state
|   |-- files/            # Temporary storage for downloaded audio files
|   |-- bot.log           # Log file
|   |-- vip_users.json    # Stores VIP user chat IDs
|   `-- last_offset.json  # Stores the last processed update ID
|
|-- .env                  # Your secret credentials (you must create this)
|-- requirements.txt      # List of Python dependencies
|-- Dockerfile            # Docker file details
|-- docker-compose.yaml   # Docker compose details
`-- bot.py                # The main application script
```