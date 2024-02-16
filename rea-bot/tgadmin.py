from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DB_API_BASE_URL = 'http://localhost:5000/'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    username = update.effective_user.username  # Get the username

    user_info = {
        'chat_id': str(chat_id),
        'username': username
    }

    try:
        response = requests.post(f'{DB_API_BASE_URL}/users', json=user_info)
        if response.status_code == 201:
            await update.message.reply_text("You have been added. Thank you!")
        elif response.status_code == 200:
            await update.message.reply_text("You are already registered, no need to register again!")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def main():
    # Create the Application and pass it your bot's token.
    tg_bot_hash = os.getenv('TG_BOT_HASH')
    application = Application.builder().token(tg_bot_hash).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()