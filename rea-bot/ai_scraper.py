from logger import setup_logger
import asyncio
import random
import json
import re
import traceback
import hashlib
import os
import sys
from dotenv import load_dotenv
import requests
import argparse
from perplexity import Perplexity
from telegram import Bot
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures

scraper_logger = setup_logger('scraper_logger', './logs/scraper_logfile.log')

# Utilities func
def generate_md5_hash(data_dict):
    # Create a string concatenation of the 'address' and 'price' fields
    hash_input = data_dict['address'] + data_dict['price']
    # Encode the string to bytes
    hash_input_encoded = hash_input.encode('utf-8')
    # Create an MD5 hash object and update it with the encoded string
    md5_hash = hashlib.md5()
    md5_hash.update(hash_input_encoded)
    # Return the hexadecimal digest of the hash
    return md5_hash.hexdigest()

def cleanse(response_text):
    # Split the text into lines
    lines = response_text.splitlines()

    # Ensure there are at least two lines to remove
    if 'json' in response_text:
        # Remove the first and last lines
        lines = lines[1:-1]

    # Join the remaining lines back into a single string
    cleaned_text = '\n'.join(lines)

    return cleaned_text

# Cleanse to DB
def save_data(data):
    # Strip whitespace that might be at the start/end of the string
    data = data.strip()
    
    try:
        # Try to parse the string into JSON
        new_data = json.loads(data)
    except json.JSONDecodeError:
        # If it fails, raise an error
        scraper_logger.info("New data is not valid JSON and cannot be appended")
    
    # Make a POST request to the insert endpoint
    response = requests.post(api_url, json=new_data)

    if response.status_code == 201:
        scraper_logger.info("Listing added successfully")
    else:
        scraper_logger.error("Failed to add listing", response.json())

async def send_message_with_retry(message, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            scraper_logger.info('Running query...')
            response = None
            for chunk in perplexity.search(message):
                response = chunk  # Assuming the last chunk contains the answer
            
            # After iterating over the generator, check if the response contains 'answer'
            if response and 'answer' in response:
                scraper_logger.info(response['answer'])
                return response['answer']

        except Exception as e:
            if 'already running' in str(e):
                attempt += 1
                scraper_logger.info(f"Server Error encountered. Retry attempt {attempt}/{max_retries}.")
                await asyncio.sleep(60)
            else:
                scraper_logger.info(f"An unexpected error occurred: {e}")
                scraper_logger.error(traceback.format_exc())
                return None  # or handle the error appropriately

    scraper_logger.info(f"Failed to send message after {max_retries} retries. Skipping message.")
    return None  # or handle the failure case appropriately

async def scrape(broker, area, max_price):
    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True) 

        userAgentStrings = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.2227.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.2228.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.3497.92 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        ];

        context = await browser.new_context(
            user_agent=userAgentStrings[random.randint(0, len(userAgentStrings) - 1)],
            bypass_csp=True
        )
        
        page = await context.new_page()

        url = broker.url.format(area=area, max_price=max_price)
        scraper_logger.info(f"Scraping {broker.name} - {url}")
        
        await page.goto(url)
        
        # Remove cookie dialog for cleaning up page
        if broker.cookie_modal_selector:
            eval_func = """() => {{
                const modal = document.querySelector('{cookie_modal_selector}');
                if (modal) {{
                    modal.parentElement.removeChild(modal);
                }}
            }}"""

            eval_func = eval_func.format(cookie_modal_selector=broker.cookie_modal_selector)
            await page.evaluate(eval_func)
        else:
            scraper_logger.info(f"No cookie modal defined in config for {broker.name}, continuing")

        try:
            # Wait for the page to load fully
            await page.wait_for_load_state()

            # Extract data from the page
            # html_broker = await page.inner_html('body')
            listings = await page.query_selector_all(broker.listing_selector)

            href = None
            
            # Wait for the selector instead if no ad is found
            if not listings:
                scraper_logger.info(f'wait_for_selector({broker.listing_selector})')
                await page.wait_for_selector(broker.listing_selector)
                listings = await page.query_selector_all(broker.listing_selector)

            # if broker.name == 'Pararius':
                # html_broker = await page.inner_html('body')

                # with open ('./debug/html_' + broker.name + '.html', 'w') as file_html:
                #     file_html.write(html_broker)
                # await page.screenshot(path='./debug/screenshot_' + broker.name + '.png')
            
            for listing in listings:
                    text = await listing.inner_text()

                    # Taking in consideration every website has an anchor for the listing details/content - find the href for the listing_link
                    href_regex = re.compile(r'\bhref=["\']([^\'" >]+)')
                    # Get the outer HTML of the listing element
                    outer_html = await page.evaluate('(element) => element.outerHTML', listing)
                    # with open ('outer_html.html', 'w') as file_html:
                    #     file_html.write(outer_html)
                    
                    # Search for hrefs within the HTML using the regex
                    matches = href_regex.findall(outer_html)
                    if matches:
                        # Usually the closest href is the link to the listing
                        href = matches[0]

                        # Check whether missing domain url
                        if broker.domain not in href:
                            href = broker.domain + href
                        scraper_logger.info(f'Processing listing - {href}')

                        # Todo last - to improve through all sites?
                        # Define any query parameters you want to send
                        params = {
                            'listing_link': href
                        }

                        # Send a GET request with the query parameters
                        response = requests.get(api_url, params=params)

                        # Check if the request was successful
                        if response.status_code == 200 and response.json():
                            # Parse the response JSON into a Python dictionary
                            scraper_logger.info(f'Found data! - Skipping call to AI')
                            continue
                        else:

                            # Delay for not overcrowding the servers
                            await asyncio.sleep(10)
                            ## Call AI ##

                            # Create a new context with a different user agent for each listing
                            new_user_agent = userAgentStrings[random.randint(0, len(userAgentStrings) - 1)]
                            listing_context = await browser.new_context(user_agent=new_user_agent)

                            listing_page = await listing_context.new_page()

                            # Click the listing using the selector within the new page
                            await listing_page.goto(f"{href}")
                            await listing_page.wait_for_load_state()

                            # Reading the whole body because might be the AI can cross-find some information
                            # from other boxes present in the page rather the description only
                            page_text = await listing_page.inner_text('body')

                            # scraper_logger.info(f'single listing: {text}')
                            message = """
                            From this text, cleanse and convert the information (if there) to a JSON object, matching this schema: 

                            {
                                "address":"",
                                "price":"",
                                "area":"",
                                "bedrooms":"",
                                "energy_label":""
                                "furnished":""
                            }

                            Format of the fields:
                            address - a string, must be formatted in: street, postal code, city
                            price - numbers only, must exclude other chars 
                            area - numbers only, must exclude other chars 
                            bedrooms - a string 
                            energy_label - a string
                            furnished - a string, true or false

                            Important! Limit responses to a valid JSON, no explanatory text. Never truncate the JSON with an ellipsis. Always srurround the values with double quotes and escape quotes with \\. Always omit trailing commas. 

                            Text:
                            """
                            message += text + "\n" + page_text
                            # scraper_logger.info(f'message: {message}')
                            # response_text = await send_message_with_retry(client, bot, message, 270446664) # chinchilla
                            response_text = await send_message_with_retry(message) # Perplexity
                            
                            # Looks like cleanse is not needed anymore? :D
                            response_text = cleanse(response_text)
                            response_data = json.loads(response_text)
                            
                            # Add a new field with the key 'listing_link' and the value of href
                            response_data['listing_link'] = href
                            updated_response_text = json.dumps(response_data, ensure_ascii=False)
                            scraper_logger.info(updated_response_text)

                            # response_text = await send_message_with_retry(client, bot, message, 262252582) # a2
                            # scraper_logger.info(f'Response text: {response_text}')

                            save_data(updated_response_text)
                            
                            # Send notification
                            
                            notification_message = (
                                f"🏄 Found new listing!\n"
                                f"{response_data['address']} - € {response_data['price']} p/m - {response_data['bedrooms']} bedroom(s) - {response_data['area']} m2 - E/L: {response_data['energy_label']}\n"
                                f"{response_data['listing_link']}"
                            )

                            # Ensure each line is stripped of leading/trailing whitespace
                            formatted_msg = "\n".join(line.strip() for line in notification_message.splitlines())

                            applying_msg = (
                                f"I'm looking for an apartment in Utrecht and I've found your listing at {response_data['address']}.\n"
                                "I would love to view this apartment!\n"
                                "My name is Asjon and I am a Software Engineer. My bruto income is €5800 per month. I'm moving in by myself.\n\n"
                                "I'm available for a viewing as soon as it's possible. Could I come by for a viewing?\n\n"
                                "You can reach me at +31 683715213 or asjon.dalipaj@gmail.com.\n\n"
                                "Hope to hear from you!\n"
                                "Kind regards,\n"
                                "Asjon"
                            )

                            # Ensure each line is stripped of leading/trailing whitespace
                            formatted_apply_msg = "\n".join(line.strip() for line in applying_msg.splitlines())

                            # Send the messages to the channel
                            await tg_bot.send_message(chat_id=tg_channel_id, text=formatted_msg)
                            await tg_bot.send_message(chat_id=tg_channel_id, text=formatted_apply_msg)

                            # Close the listing page and context after processing
                            await listing_page.close()
                            await listing_context.close()
                    else:
                        scraper_logger.info("No URL found in the HTML of this listing.")
                    
                    # TODO 2 - Handle pagination if required
                    # next_button = await page.query_selector(next_button_selector)
                    # scraper_logger.info("Next Page btn:", next_button)
                    # if next_button:
                    #     scraper_logger.info(f"Another page for {area}")     
                    #     await scrape(area, url, listing_selector, next_button_selector, page_number + 1)
        # except PlaywrightTimeoutError as e:
        #     scraper_logger.info(f"Timeout reaching {broker.name}, or simply, no listings to scrape - skipping!")
        #     scraper_logger.info(f"-- End {broker.name} --")
        except Exception as e:
            # if href:
            #     scraper_logger.error(f"There was an error processing this listing - {href}")
            scraper_logger.error(traceback.format_exc())
        finally:
            await browser.close()

    scraper_logger.info(f"-- End {broker.name} --")

# Broker class to hold the configuration and state
class Broker:
    def __init__(self, config):
        # Set attributes directly from the config dictionary
        self.name = config.get('name')
        self.domain = config.get('domain')
        self.url = config.get('url')
        self.listing_selector = config.get('listing_selector')
        self.next_button_selector = config.get('next_button_selector')
        self.cookie_modal_selector = config.get('cookie_modal_selector')

# Function to load configurations
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = json.load(file)

    return [Broker(broker_config) for broker_config in config['brokers']]

# This function will run in separate processes and cannot be a coroutine
def run_scrape_in_process(broker, area, max_price):
    # Since this runs in a new process, we need to set up a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Now we can run the coroutine scrape in the new event loop
    result = loop.run_until_complete(scrape(broker, area, max_price))
    loop.close()
    return result

def scrape_all_brokers(brokers, area, max_price):
    # We use ProcessPoolExecutor to run things in parallel processes
    with ProcessPoolExecutor() as executor:
        # Create a list to hold all the futures
        futures = [
            executor.submit(run_scrape_in_process, broker, area, max_price)
            for broker in brokers
        ]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                # Handle the result
                print(f"Scraping result: {result}")
            except Exception as exc:
                print(f"An exception occurred: {exc}")

if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument('-area', help='Specify the area', default=None)
    parser.add_argument('-max_price', help='Specify the maximum price', type=int, default=None)

    args = parser.parse_args()

    area = args.area
    max_price = args.max_price

    # Config
    # Read API key from a file and pass it to the function
    load_dotenv()
    api_key = os.getenv('API_KEY')
    perplexity = Perplexity()

    # Setup Telegram
    # Prepend '-' for using channel ID
    tg_channel_id = os.getenv('TG_CHANNEL_ID')
    tg_channel_id = f'-{tg_channel_id}'
    tg_bot_hash = os.getenv('TG_BOT_HASH')
    tg_bot = Bot(token=tg_bot_hash)
    
    # Load configuration for brokers
    brokers = load_config('./utilities/brokers.json')
    api_url = 'http://localhost:5000/listings'
    scraper_logger.info('### Scraper started ###')

    # Run the scrape for all brokers
    scrape_all_brokers(brokers, area, max_price)
    
    # Close perplexity connection
    perplexity.close()