from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
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

FURNISHED, INCLUDING_BILLS, MIN_PRICE, MAX_PRICE, MIN_SQM, MAX_SQM, MIN_BEDROOM, CITY, MESSAGE, ADD_OR_CHANGE = range(10)

# Utilities

def get_user_by_chat_id(chat_id):
    response = requests.get(f'{DB_API_BASE_URL}/users/{chat_id}')
    if response.status_code == 200:
        return response.json()
    else:
        return []

def get_filters_by_user_id(user_id):
    response = requests.get(f'{DB_API_BASE_URL}/users/{user_id}/filters')
    if response.status_code == 200:
        return response.json()
    else:
        return []

def get_message_by_user_id(user_id):
    response = requests.get(f'{DB_API_BASE_URL}/users/{user_id}/message')
    if response.status_code == 200:
        return response.json()
    else:
        return []

# Start conversation and handle /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    reply_keyboard = [['Yes', 'No']]
    reply_keyboard_add_change = [['Add', 'Change', 'Cancel']]

    user_info = {
        'chat_id': str(chat_id),
        'username': username
    }

    try:
        response = requests.post(f'{DB_API_BASE_URL}/users', json=user_info)
        if response.status_code == 201:
            markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                "Welcome to Hopper! Let's setup some filters for your future rental: Would you want the property to be *furnished?*",
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
        elif response.status_code == 200:
            user = get_user_by_chat_id(chat_id)
            filters = get_filters_by_user_id(user['id'])
            message = get_message_by_user_id(user['id'])

            # Prepare text for each filter in the list
            filters_text_list = []
            for filter_ in filters:
                human_readable_filter = {
                    'Furnished': 'Yes' if filter_['furnished'] else 'No',
                    'Including bills': 'Yes' if filter_['including_bills'] else 'No',
                    'Min price': filter_['min_price'],
                    'Max price': filter_['max_price'],
                    'Min sqm': filter_['min_sqm'],
                    'Max sqm': filter_['max_sqm'],
                    'Min bedroom': filter_['min_bedroom'],
                    'City': filter_['city']
                }
                filter_text = "\n".join([f"{key}: {value}" for key, value in human_readable_filter.items()])
                filters_text_list.append(filter_text)

            # Combine all filter texts into one string
            filters_text = "\n\n".join(filters_text_list)

            # Prepare text for user message
            message_text = "\n".join([msg['message'] for msg in message])  # Assuming message is a list of messages

            # Prepare the keyboard markup
            markup = ReplyKeyboardMarkup(reply_keyboard_add_change, one_time_keyboard=True, resize_keyboard=True)

            # Prepare the full text including the filters and message
            full_text = (
                "Hello, welcome back to Hopper, you're already registered.\n\n"
                "*Current Filters:*\n"
                f"{filters_text}\n\n"
                "*Your Message:*\n"
                f"{message_text}\n\n"
                "Would you like to *add or change anything?*"
            )

            # Send the message to the user
            await update.message.reply_text(
                full_text,
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            return ADD_OR_CHANGE

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    return FURNISHED

async def add_or_change_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = update.message.text.lower()
    reply_keyboard = [['Yes', 'No']]
    
    # Add new filters
    if text == 'add':
        # Add handler logic here
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Great! Let's setup some more  filters for your future rental: Would you want the property to be *furnished?*",
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return FURNISHED
    elif text == 'change':
        # Change handler logic here
        await update.message.reply_text(
            "Let's change your filters...",
            parse_mode=ParseMode.MARKDOWN)
        return FURNISHED
    elif text == 'cancel':
        # Cancel handler logic here
        await update.message.reply_text(
            "You cancelled, see you next time!",
            parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    else:
        # Handle invalid input
        await update.message.reply_text(
            "Please choose 'Add', 'Change', or 'Cancel'.",
            parse_mode=ParseMode.MARKDOWN)
        return ADD_OR_CHANGE

# Handlers for each state in the conversation
async def furnished_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    reply_keyboard = [['Yes', 'No']]
    text = update.message.text.lower()
    context.user_data['furnished'] = text
    context.user_data['furnished'] = 'true' if context.user_data['furnished'] == 'yes' else 'false'

    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Would you want *bills included?*",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return INCLUDING_BILLS

async def including_bills_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = update.message.text.lower()
    context.user_data['including_bills'] = text
    context.user_data['including_bills'] = 'true' if context.user_data['furnished'] == 'yes' else 'false'

    await update.message.reply_text(
        "What would be the *minimum price* you consider? (whole numbers only)",
        parse_mode=ParseMode.MARKDOWN)
    return MIN_PRICE

# Handler for MIN_PRICE state
async def min_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_price'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text(
            "And what about the *maximum price?* (whole numbers only)",
            parse_mode=ParseMode.MARKDOWN)
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
        await update.message.reply_text(
            "What is the *minimum square* meters?",
            parse_mode=ParseMode.MARKDOWN)
        return MIN_SQM
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the maximum price.")
        return MAX_PRICE

async def min_sqm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_sqm'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text(
            "What is the *maximum sqm?*",
            parse_mode=ParseMode.MARKDOWN)
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
        await update.message.reply_text(
            "How many *bedrooms?* (whole numbers only)",
            parse_mode=ParseMode.MARKDOWN)
        return MIN_BEDROOM
    except ValueError:
        await update.message.reply_text("Please enter a city between these: Utrecht")
        return MAX_SQM
    
async def min_bedroom_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    # You can add validation to ensure the input is a valid number
    try:
        context.user_data['min_bedroom'] = int(text)  # Save the minimum price as an integer
        await update.message.reply_text(
            "And lastly, in which *city* you'd like to live?",
            parse_mode=ParseMode.MARKDOWN)
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

    user = get_user_by_chat_id(chat_id)
    filter_data = {
        'userid': user['id'],
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
            await update.message.reply_text(
                "Your filter has been saved, would you like to add a *message for applying* to the listings?\n"
                "Here's a suggestion:",
                parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text(
                "I'm looking for an apartment in Utrecht and I've found your listing at [ADDRESS].\n"
                "I would love to view this apartment!\n"
                f"My name is {update.effective_user.username} and I am a [your profession]. My bruto income is [€your bruto] per month. I'm moving in [by myself/my partner].\n\n"
                "I'm available for a viewing as soon as it's possible. Could I come by for a viewing?\n\n"
                "You can reach me at '+XX your phone number' or your.mail@gmail.com.\n\n"
                "Hope to hear from you!\n"
                "Kind regards,\n"
                f"{update.effective_user.username}")

            return MESSAGE
        else:
            await update.message.reply_text("There was an error saving your filter.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Error: {e}")
        return CITY

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['message'] = update.message.text
    chat_id = update.effective_chat.id
    
    user = get_user_by_chat_id(chat_id)
    message_data = {
        'userid': user['id'],
        'message': context.user_data['message']
    }

    try:
        response = requests.post(f'{DB_API_BASE_URL}/message', json=message_data)
        if response.status_code == 201:
            await update.message.reply_text("Everything is set up! You will now receive notifications as soon as a listing is published. Good luck!")
        else:
            await update.message.reply_text("There was an error saving your message.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Error: {e}")

    return ConversationHandler.END

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('You canceled. Open the menu and tap on ''start'' for inserting again the filters.')
    return ConversationHandler.END

def main():
    # Create the Application and pass it your bot's token.
    tg_bot_hash = os.getenv('TG_BOT_HASH')
    application = Application.builder().token(tg_bot_hash).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ADD_OR_CHANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_or_change_handler)],
            FURNISHED: [MessageHandler(filters.TEXT & ~filters.COMMAND, furnished_handler)],
            INCLUDING_BILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, including_bills_handler)],
            MIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_price_handler)],
            MAX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_price_handler)],
            MIN_SQM: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_sqm_handler)],
            MAX_SQM: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_sqm_handler)],
            MIN_BEDROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_bedroom_handler)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_handler)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()