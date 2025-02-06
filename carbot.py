import os
import requests
import random
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from openai import AsyncOpenAI

# Set up logging with a stream handler
logger = logging.getLogger('carbot')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables
load_dotenv()

# Get environment variables
# TOKEN = os.getenv('TEST_TELEGRAM_BOT_TOKEN') # used to test 
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTO_DEV_API_KEY = os.getenv('AUTO_DEV_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Validate environment variables
if not TOKEN or not AUTO_DEV_API_KEY:
    logger.error("Missing required environment variables. Please check your .env file.")
    raise ValueError("Missing required environment variables. Please check your .env file.")

if not OPENAI_API_KEY:
    logger.error("Missing OpenAI API key in .env file")
    raise ValueError("Missing OpenAI API key in .env file")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Use /car [amount] to find a car around that price.')

async def parse_car_query(query: str) -> dict[str, any]:
    """Convert natural language query to Auto.dev API parameters"""
    try:
        logger.info(f"Sending query to OpenAI: {query}")
        response = await aclient.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Convert natural language car search queries into Auto.dev API parameters.

Important formatting rules:
1. Car makes must use proper capitalization (e.g., "BMW", "Mercedes-Benz", "Audi", "Toyota", "Hyundai", "Porsche"). Only capitalize the first letter of each word unless the make is an abbreviation like "BMW" or "MDX". Do not capitalize the full word for other makes.  
2. Colors must use the "exterior_color[]" parameter with these exact values: black, silver, white, gray, red, green, yellow, blue, brown, orange, purple, gold
3. Body styles must use the "body_style[]" parameter with these exact values: convertible, coupe, minivan, crossover, sedan, suv, truck, wagon
4. All array parameters must include the [] suffix in the key name (e.g., "exterior_color[]", "body_style[]", "features[]")
5. Conditions must use "condition[]" with these exact values: new, used, certified pre-owned
6. Transmissions must use "transmission[]" with these exact values: automatic, manual
7. Drivetrains must use "driveline[]" with these exact values: RWD, FWD, 4X4, AWD

Examples:
- "red bmw" → {"make": "BMW", "exterior_color[]": "red"}
- "used toyota suv" → {"make": "Toyota", "body_style[]": "suv", "condition[]": "used"}
- "manual mercedes" → {"make": "Mercedes-Benz", "transmission[]": "manual"}
- "porsche" → {"make": "Porsche"}"""},
                {"role": "user", "content": f"Convert this car search query to parameters: {query}"}
            ],
            temperature=0.1,
            max_tokens=250,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "car_search_params",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "make": {"type": ["string", "null"]},
                            "model": {"type": ["string", "null"]},
                            "exterior_color[]": {"type": ["string", "null"], "enum": ["black", "silver", "white", "gray", "red", "green", "yellow", "blue", "brown", "orange", "purple", "gold", None]},
                            "body_style[]": {"type": ["string", "null"], "enum": ["convertible", "coupe", "minivan", "crossover", "sedan", "suv", "truck", "wagon", None]},
                            "category": {"type": ["string", "null"], "enum": ["american", "classic", "commuter", "electric", "family", "fuel_efficient", "hybrid", "muscle", "sport", "supercar", None]},
                            "condition[]": {"type": ["string", "null"], "enum": ["new", "used", "certified pre-owned", None]},
                            "features[]": {"type": ["string", "null"], "enum": ["backup_camera", "bluetooth", "heated_seats", "leather", "navigation", "sunroof", None]},
                            "transmission[]": {"type": ["string", "null"], "enum": ["automatic", "manual", None]},
                            "driveline[]": {"type": ["string", "null"], "enum": ["RWD", "FWD", "4X4", "AWD", None]},
                            "sort_filter": {"type": ["string", "null"], "enum": ["price:asc", "price:desc", "year:desc", "mileage:asc", None]}
                        },
                        "required": [
                            "make", "model", "exterior_color[]", "body_style[]", "category", 
                            "condition[]", "features[]", "transmission[]", 
                            "driveline[]", "sort_filter"
                        ],
                        "additionalProperties": False
                    }
                }
            }
        )

        # Log complete response object for debugging
        logger.info(f"Complete OpenAI Response: {response}")
        
        # Get the response content
        raw_response = response.choices[0].message.content
        logger.info(f"Raw AI Response: {raw_response}")
        
        if not raw_response or raw_response.isspace():
            logger.error("OpenAI returned empty or whitespace response")
            return {}

        try:
            # Parse the response into a Python dict using json.loads instead of eval
            params = json.loads(raw_response)
            logger.info(f"Parsed parameters: {params}")
            
            # Filter out null values
            filtered_params = {k: v for k, v in params.items() if v is not None}
            logger.info(f"Filtered parameters being returned: {filtered_params}")
            return filtered_params
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {raw_response}")
            logger.error(f"JSON decode error: {e}")
            return {}

    except Exception as e:
        logger.error(f"Error in OpenAI call: {str(e)}")
        return {}

async def get_autodev_car(update: Update, target_price: int, search_query: str = None) -> None:
    url = "https://auto.dev/api/listings"
    params = {
        "apikey": AUTO_DEV_API_KEY,
        "price_min": max(0, target_price * 0.9),
        "price_max": target_price * 1.10,
        "page": 1,
        "exclude_no_price": "true"
    }

    # Add search parameters from natural language query
    if search_query:
        logger.info(f"Processing search query: {search_query}")
        additional_params = await parse_car_query(search_query)
        logger.info(f"Additional parameters from query: {additional_params}")
        params.update(additional_params)
        logger.info(f"Final parameters for Auto.dev API: {params}")

    try:
        logger.info(f"Making request to Auto.dev API: {url}")
        response = requests.get(url, params=params, timeout=10)
        
        # Log the actual URL being called
        logger.info(f"Full URL with parameters: {response.url}")
        
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            logger.error(f"Response content: {response.text}")
            raise

        data = response.json()
        
        record_count = len(data.get('records', []))
        logger.info(f"Auto.dev API returned {record_count} records")
        
        if record_count == 0:
            if target_price < 1000:
                # return betmore.png
                await update.message.reply_photo(photo='betmore.png')
            elif target_price > 25000000:
                await update.message.reply_photo(photo='betless.png')
            else:
                await update.message.reply_text("Sorry, I couldn't find any cars matching your criteria. Try adjusting your search parameters.")
        return
    
        # Log first few records for debugging
        if record_count > 0:
            logger.info("First record details:")
            first_record = data['records'][0]
            logger.info(f"Year: {first_record.get('year')}")
            logger.info(f"Make: {first_record.get('make')}")
            logger.info(f"Model: {first_record.get('model')}")
            logger.info(f"Price: {first_record.get('price')}")

        listing = random.choice(data['records'])
        year = listing.get('year', 'N/A')
        make = listing.get('make', 'N/A')
        model = listing.get('model', 'N/A')
        photo_url = listing.get('primaryPhotoUrl')
        
        logger.info(f"Selected car: {year} {make} {model}")

        message = f"With your ${target_price}, you could have bought a {year} {make} {model}!"

        if photo_url:
            await update.message.reply_photo(photo=photo_url, caption=message)
        else:
            await update.message.reply_text(message)

    except requests.exceptions.Timeout:
        logger.error("Request to Auto.dev API timed out")
        await update.message.reply_text("The request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error occurred: {e}")
        await update.message.reply_text("An error occurred while fetching car data. Please try again.")
    except Exception as e:
        logger.error(f"Error in get_autodev_car: {str(e)}")
        logger.exception("Full traceback:")
        await update.message.reply_text("An error occurred. Please try again.")

async def get_random_car(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Please provide an amount: /car [amount] [optional: description]")
            return

        try:
            amount = int(args[0])
        except ValueError:
            await update.message.reply_text("Please provide a valid number for the amount.")
            return

        # Join remaining args as the search query
        search_query = " ".join(args[1:]) if len(args) > 1 else None
        
        # Log the incoming command
        logger.info(f"Received command: /car {amount} {search_query if search_query else ''}")

        if search_query == "ebay":
            # ... existing eBay handling ...
            pass
        else:
            await get_autodev_car(update, amount, search_query)

    except Exception as e:
        logger.error(f"Error in get_random_car: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

def main():
    # Initialize the application with more aggressive settings
    logger.info("Initializing bot application...")
    application = (
        Application.builder()
        .token(TOKEN)
        .connection_pool_size(8)
        .get_updates_connection_pool_size(8)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .get_updates_write_timeout(30.0)
        .get_updates_pool_timeout(30.0)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("car", get_random_car))

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()