from logger import setup_logger
import asyncio
import random
import json
import re
import traceback
import os
import sys
from dotenv import load_dotenv
import requests
import argparse
from perplexity import Perplexity
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

scraper_logger = setup_logger('scraper_logger', './logs/scraper_logfile.log')

def get_users():
    response = requests.get(f'{DB_API_BASE_URL}/users')
    if response.status_code == 200:
        return response.json()
    else:
        return []

def get_filters_for_user(user_id):
    response = requests.get(f'{DB_API_BASE_URL}/users/{user_id}/filters')
    if response.status_code == 200:
        return response.json()
    else:
        return []

def normalize_string(s):
    # Convert to lowercase and strip whitespace
    s = s.lower().strip()
    return s

def listing_matches_filters(listing, filters):
    # Convert listing values to appropriate types
    listing_price = float(listing['price'])
    listing_area = int(listing['area'])
    listing_bedrooms = int(listing['bedrooms'])
    listing_address = normalize_string(listing['address'])
    including_bills = listing['including_bills'].lower() == 'true'
    furnished = listing['furnished'].lower() == 'true'

    # scraper_logger.info('Listing: %s' % listing)

    # Iterate over filters
    for idx, filter in enumerate(filters):
        # scraper_logger.info(f'Checking filter {idx}: {filter}')

        # Extract and normalize filter criteria
        min_price = float(filter.get('min_price', 0))
        max_price = float(filter.get('max_price', float('inf')))
        min_sqm = int(filter.get('min_sqm', 0))
        max_sqm = int(filter.get('max_sqm', float('inf')))
        min_bedroom = int(filter.get('min_bedroom', 0))
        filter_city = normalize_string(filter['city']) if filter['city'] else listing_address
        
        # Calculate adjusted price based on bills inclusion
        adjusted_price = listing_price + 160 if not including_bills and filter.get('including_bills') else listing_price

        scraper_logger.info(f"Filter {idx} - Price Range: {min_price} <= {adjusted_price} <= {max_price}")
        scraper_logger.info(f"Filter {idx} - Area Range: {min_sqm} <= {listing_area} <= {max_sqm}")
        scraper_logger.info(f"Filter {idx} - Bedrooms: {min_bedroom} <= {listing_bedrooms}")
        scraper_logger.info(f"Filter {idx} - City Match: {filter_city} in {listing_address}")

        # Check if the listing matches the filter
        is_furnished_match = (filter.get('furnished') is None or filter['furnished'].lower() == str(furnished).lower())
        is_bills_included_match = (filter.get('including_bills') is None or filter['including_bills'].lower() == str(including_bills).lower())
        is_price_match = min_price <= adjusted_price <= max_price
        is_area_match = min_sqm <= listing_area <= max_sqm
        is_bedroom_match = min_bedroom <= listing_bedrooms
        is_city_match = filter_city in listing_address

        if all([is_furnished_match, is_bills_included_match, is_price_match, is_area_match, is_bedroom_match, is_city_match]):
            return True
        else:
            scraper_logger.info(f"Listing does not match filter {idx}")

    scraper_logger.info("No filters matched the listing.")
    return False

def notify_flask_app(chat_id, listing):
    notification_data = {'chat_id': chat_id, 'listing': listing}
    response = requests.post(f'{DB_API_BASE_URL}/notify', json=notification_data)
    return response.status_code

def check_and_notify(listing):
    # Todo manage if api is down
    users = get_users()
    # scraper_logger.info('Users: %s' % users)
    for user in users:
        # scraper_logger.info('User: %s' % user)
        filters = get_filters_for_user(user['id'])
        # scraper_logger.info('Filters: %s', filters)
        if listing_matches_filters(listing, filters):
            # scraper_logger.info('Matches filters, sending notification')
            notify_flask_app(user['chat_id'], listing)
        # else:
        #     if user['username'] == 'OfficialAssa':
        #         scraper_logger.info('Sending notification to admin')
        #         scraper_logger.info('Listing: %s', listing)
        #         scraper_logger.info('Filters: %s', filters)
        #         notify_flask_app(user['chat_id'], listing)

def cleanse(response_text):
    start = response_text.find('{')
    
    # We add 1 to include the closing brace itself in the slice
    end = response_text.rfind('}') + 1

    # If both braces are found, slice the string
    if start != -1 and end != -1:
        cleaned_text = response_text[start:end]
    else:
        # If the braces are not found, return the original text
        cleaned_text = response_text

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
    response = requests.post(f'{DB_API_BASE_URL}/listings', json=new_data)

    if response.status_code == 201:
        scraper_logger.info("Listing added successfully")
    else:
        scraper_logger.error("Failed to add listing", response.json())

async def send_message_with_retry(message, max_retries=3):
    attempt = 0
    try:
        scraper_logger.info('Running query...')
        response = None
        for chunk in perplexity.search(message):
            response = chunk  # Assuming the last chunk contains the answer
        
        # After iterating over the generator, check if the response contains 'answer'
        if response and 'answer' in response:
            scraper_logger.info(response['answer'])
            return response['answer']

    except e:
        if 'already running' in str(e):
            attempt += 1
            scraper_logger.info(f"Server Error encountered. Retry attempt {attempt}/{max_retries}.")
            # Since this is an async function, we still need to wait asynchronously.
            await asyncio.sleep(60)
        else:
            scraper_logger.info(f"An unexpected error occurred: {e}")
            scraper_logger.error(traceback.format_exc())
            await sys.exit(1)

        scraper_logger.info(f"Failed to send message after {max_retries} retries. Skipping message.")

async def scrape(url, domain, ad_selector, next_button_selector, cookie_modal_selector, page_number=1):
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

        url = url.format(area=area, max_price=max_price, page_number=page_number)
        scraper_logger.info(f"Scraping {broker['name']} - {url}")
        
        await page.goto(url)
        
        # Remove cookie dialog for cleaning up page
        if cookie_modal_selector:
            eval_func = """() => {{
                const modal = document.querySelector('{cookie_modal_selector}');
                if (modal) {{
                    modal.parentElement.removeChild(modal);
                }}
            }}"""

            eval_func = eval_func.format(cookie_modal_selector=cookie_modal_selector)
            await page.evaluate(eval_func)
        else:
            scraper_logger.info("No cookie modal defined in config, continuing")

        try:
            scraper_logger.info(f"-- Scraping page {page_number}--")
            # Wait for the page to load fully

            await page.wait_for_load_state()

            # Extract data from the page
            # html_broker = await page.inner_html('body')
            listings = await page.query_selector_all(ad_selector)
            
            href = None
            
            # Wait for the selector instead if no ad is found
            if not listings:
                await page.wait_for_selector(ad_selector, timeout=8000)
                listings = await page.query_selector_all(ad_selector)

            # if broker['name'] == 'Pararius':
            #     html_broker = await page.inner_html('body')
    
            #     with open ('./debug/html_' + broker['name'] + '.html', 'w') as file_html:
            #         file_html.write(html_broker)
            #     await page.screenshot(path='./debug/screenshot_' + broker['name'] + '.png')
            
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
                        if domain not in href:
                            href = domain + href
                        scraper_logger.info(f'Processing listing - {href}')

                        # Todo last - to improve through all sites?
                        # Define any query parameters you want to send
                        params = {
                            'listing_link': href
                        }

                        # Send a GET request with the query parameters
                        response = requests.get(f'{DB_API_BASE_URL}/listings', params=params)

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
                            From this text, only return a JSON object, matching exactly this schema: 

                            {
                                "address":"",
                                "price":"",
                                "area":"",
                                "bedrooms":"",
                                "energy_label":""
                                "furnished":""
                                "including_bills":""
                            }

                            Field formatings:
                            address - a string, title case, must be formatted in: street, postal code, city
                            price - numbers only, must exclude other chars 
                            area - numbers only, must exclude other chars 
                            bedrooms - a string, 1 as default, must return the number of bedrooms only 
                            energy_label - a string
                            furnished - a string, must return true or false
                            including_bills - a string, must return true or false

                            Important! If data is not there always return an empty string. Never truncate the JSON with an ellipsis. Always srurround the values with double quotes and escape quotes with \\. Always omit trailing commas. 

                            Text:
                            """
                            message += text + "\n" + page_text
                            # scraper_logger.info(f'message: {message}')
                            # response_text = await send_message_with_retry(client, bot, message, 270446664) # chinchilla
                            response_text = await send_message_with_retry(message) # Perplexity

                            # response_text = """
                            # {
                            #     "address":"Schonberglaan 189, 3454HS, Utrecht",
                            #     "price":"1130",
                            #     "area":"73",
                            #     "bedrooms":"3",
                            #     "energy_label":"A",
                            #     "furnished":"false",
                            #     "including_bills":"false"
                            # }
                            # """
                            # Looks like cleanse is not needed anymore? :D
                            response_text = cleanse(response_text)
                            response_data = json.loads(response_text)
                            
                            # Add a new field with the key 'listing_link' and the value of href
                            response_data['listing_link'] = href
                            updated_response_text = json.dumps(response_data, ensure_ascii=False)
                            # scraper_logger.info(updated_response_text)

                            save_data(updated_response_text)
                            # scraper_logger.info(f"Data - page {page_number}: {data}")
                            
                            # scraper_logger.info('check_and_notify')
                            check_and_notify(response_data)

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
        except PlaywrightTimeoutError as e:
            scraper_logger.info(f"Timeout reaching {broker['name']}, or simply, no listings to scrape - skipping!")
            scraper_logger.info(f"-- End {broker['name']} --")
        except Exception as e:
            if href:
                scraper_logger.error(f"There was an error processing this listing - {href}")
            scraper_logger.error(traceback.format_exc())
        finally:
            await browser.close()

    scraper_logger.info(f"-- End {broker['name']} --")

if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument('-area', help='Specify the area', default=None)
    parser.add_argument('-max_price', help='Specify the maximum price', type=int, default=None)

    args = parser.parse_args()

    area = args.area
    max_price = args.max_price

    # Function to load configurations
    def load_config(config_file):
        with open(config_file, 'r') as file:
            return json.load(file)

    # Config
    # Read API key from a file and pass it to the function
    load_dotenv()

    api_key = os.getenv('API_KEY')
    # Replacing with Perplexity
    perplexity = Perplexity()
    
    config = load_config('./utilities/brokers.json')
    # Define the API endpoint
    DB_API_BASE_URL = 'http://localhost:5000'

    scraper_logger.info('### Scraper started ###')

    # Setup your asyncio event loop before the loop
    loop = asyncio.get_event_loop()

    # Loop through all the brokers in the config
    for broker in config['brokers']:
        domain = broker['domain']
        url = broker['url']
        listing_selector = broker['listing_selector']
        next_button_selector = broker['next_button_selector']
        cookie_modal_selector = broker['cookie_modal_selector']

        # Call scrape function for the current broker
        # Use the event loop you set up earlier
        coroutine = scrape(url, domain, listing_selector, next_button_selector, cookie_modal_selector)
        try:
            loop.run_until_complete(coroutine)
        except Exception as e:
            scraper_logger.info(f"An error occurred while scraping {broker['name']} in {area}: {e}")
            scraper_logger.error(traceback.format_exc())

    # Close the event loop after all tasks are done
    loop.close()

    # Close perplexity connection
    perplexity.close()