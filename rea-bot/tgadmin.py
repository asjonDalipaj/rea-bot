from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DB_API_BASE_URL = os.getenv('API_BASE_URL')

FURNISHED, INCLUDING_BILLS, MIN_PRICE, MAX_PRICE, MIN_SQM, MAX_SQM, MIN_BEDROOM, CITY = range(8)

# Start conversation and handle /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    username = update.effective_user.username  # Get the username

    user_info = {
        'chat_id': str(chat_id),
        'username': username
    }

    try:
        response = requests.post(f'{DB_API_BASE_URL}/users', json=user_info)
        if response.status_code == 201:
            await update.message.reply_text("Welcome to Hopper! Let's setup some filters for your future rental: Would you want the property to be furnished? (yes/no)")
        elif response.status_code == 200:
            await update.message.reply_text("Hello, welcome back to Hopper, you're already registered - there is no need to register again!")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    return FURNISHED

# Handlers for each state in the conversation
async def furnished_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()
    context.user_data['furnished'] = text == 'yes'
    await update.message.reply_text("Would you want bills included? (yes/no)")
    return INCLUDING_BILLS

async def including_bills_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()
    context.user_data['including_bills'] = text == 'yes'
    await update.message.reply_text("What would be the minimum price you consider? (whole numbers only)")
    return MIN_PRICE

# Handler for MIN_PRICE state
async def min_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_price'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text("What is the maximum price? (whole numbers only)")
        return MAX_PRICE
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the minimum price.")
        return MIN_PRICE

# Handler for MAX_PRICE state
async def max_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['max_price'] = int(text)  # Save the maximum price as an integer
        await update.message.reply_text("What is the minimum square meters? (leave empty in case you don't have a preference)")
        return MIN_SQM
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the maximum price.")
        return MAX_PRICE

async def min_sqm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_sqm'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text("What is the maximum sqm? (leave empty in case you don't have a preference)")
        return MAX_SQM
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the minimum sqm.")
        return MIN_SQM

# Handler for MAX_PRICE state
async def max_sqm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['max_sqm'] = int(text)  # Save the maximum price as an integer
        await update.message.reply_text("How many bedrooms? (whole numbers only)")
        return MIN_BEDROOM
    except ValueError:
        await update.message.reply_text("Please enter a city between these: Utrecht")
        return MAX_SQM
    
async def min_bedroom_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_bedroom'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text("And lastly, in which city you'd like to live?")
        return CITY
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the bedrooms.")
        return MIN_BEDROOM

async def city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['city'] = update.message.text.lower()
    chat_id = update.effective_chat.id
    
    if context.user_data['city'] != 'utrecht':
        await update.message.reply_text("Please enter a city between these: Utrecht.")
        return CITY

    user = requests.get(DB_API_BASE_URL, f'/users/{chat_id}')
    filter_data = {
        'user_id': user['id'],
        'furnished': context.user_data['furnished'],
        'including_bills': context.user_data['including_bills'],
        'min_price': context.user_data['min_price'],
        'max_price': context.user_data['max_price'],
        'min_sqm': context.user_data['min_sqm'],
        'max_sqm': context.user_data['max_sqm'],
        'min_bedroom': context.user_data['min_bedroom'],
        'city': context.user_data['city']
    }

    try:
        response = requests.post(f'{DB_API_BASE_URL}/filters', json=filter_data)
        if response.status_code == 201:
            await update.message.reply_text("Your filter has been saved, you will now receive notfiications on nww listings. Thank you!")
        else:
            await update.message.reply_text("There was an error saving your filter.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Error: {e}")

    return ConversationHandler.END

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

def main():
    # Create the Application and pass it your bot's token.
    tg_bot_hash = os.getenv('TG_BOT_HASH')
    application = Application.builder().token(tg_bot_hash).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FURNISHED: [MessageHandler(filters.TEXT & ~filters.COMMAND, furnished_handler)],
            INCLUDING_BILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, including_bills_handler)],
            MIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_price_handler)],
            MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_price_handler)],
            MIN_SQM: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_sqm_handler)],
            MAX_SQM: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_sqm_handler)],
            MIN_BEDROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_bedroom_handler)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()