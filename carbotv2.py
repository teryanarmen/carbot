import os
import requests
import random
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your Telegram Bot Token
TOKEN = '7175210188:AAEvZEdEeuMv2eI58GbYwlixPoyqo34W-4I'

# Replace with your Auto.dev API Key
AUTO_DEV_API_KEY = 'ZrQEPSkKdGVyeWFuYXJtZW5AZ21haWwuY29t'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Use /car [amount] to find a car around that price.')

async def get_random_car(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text('Please provide a valid dollar amount. Usage: /car [amount]')
        return

    target_price = int(context.args[0])
    
    url = "https://auto.dev/api/listings"
    params = {
        "apikey": AUTO_DEV_API_KEY,
        "price_min": max(0, target_price * 0.9),
        "price_max": target_price * 1.10,
        "page": 1,
        "exclude_no_price": "true"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('records') and len(data['records']) > 0:
            listing = random.choice(data['records'])
            year = listing.get('year', 'N/A')
            make = listing.get('make', 'N/A')
            model = listing.get('model', 'N/A')
            photo_url = listing.get('primaryPhotoUrl')
            
            message = f"With your ${target_price}, you could have bought a {year} {make} {model}!"

            if photo_url:
                await update.message.reply_photo(photo=photo_url, caption=message)
            else:
                await update.message.reply_text(message)
        else:
            if target_price < 10000000:
                with open('./betless.jpeg', 'rb') as photo:
                    await update.message.reply_photo(photo=photo)
            else:
                with open('./betmore.jpeg', 'rb') as photo:
                    await update.message.reply_photo(photo=photo)

    except Exception as e:
        logger.error(f"Error in get_random_car: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

def main():
    # Initialize the application with more aggressive settings
    application = (
        Application.builder()
        .token(TOKEN)
        .connection_pool_size(8)  # Increase connection pool
        .connect_timeout(30.0)    # Longer connect timeout
        .read_timeout(30.0)       # Longer read timeout
        .write_timeout(30.0)      # Longer write timeout
        .pool_timeout(30.0)       # Longer pool timeout
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("car", get_random_car))

    # Start the bot
    print("Starting bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        pool_timeout=None
    )

if __name__ == '__main__':
    main()