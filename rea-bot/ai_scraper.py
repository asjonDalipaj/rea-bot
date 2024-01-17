import asyncio
import random
import json
import re
import sys
import hashlib
import os
import requests
from perplexity import Perplexity
from telethon.sync import TelegramClient
from playwright.async_api import async_playwright
from poe_api_wrapper import PoeApi

data = ''

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

def find_ad_with_href(jsonl_data, href_to_find):
    """
    Search for an ad with a specific href in the preloaded JSONL data.

    :param jsonl_data: list of dicts, the preloaded JSONL data
    :param href_to_find: str, the href value to search for
    :return: dict or None, the JSON object containing the href or None if not found
    """
    for ad in jsonl_data:
        if ad['ad_link'] == href_to_find:
            return ad
    return None

def cleanse(response_text):
    # Split the text into lines
    lines = response_text.splitlines()

    # Ensure there are at least two lines to remove
    if len(lines) >= 2:
        # Remove the first and last lines
        lines = lines[1:-1]

    # Join the remaining lines back into a single string
    cleaned_text = '\n'.join(lines)

    return cleaned_text

# Cleanse and save data
def save_data(data, area):
    # Strip whitespace that might be at the start/end of the string
    data = data.strip()
    
    # Define the filename for the results
    filename = f'./results/results_{area}.jsonl'
    
    # Make sure the directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    try:
        # Try to parse the string into JSON
        new_data = json.loads(data)
    except json.JSONDecodeError:
        # If it fails, raise an error
        raise ValueError("New data is not valid JSON and cannot be appended")
    
    # Open the file in append mode and write the new JSON object
    with open(filename, 'a', encoding='utf-8') as f:
        # Write the JSON data as a single line
        f.write(json.dumps(new_data, ensure_ascii=False) + "\n")

# async def send_message_with_retry(client, bot, message, chat_id="", max_retries=3):
#     attempt = 0
#     chunk = None  # Define chunk outside of the try block to make it accessible in the entire function scope
#     while attempt < max_retries:
#         try:
#             for chunk in client.send_message(bot, message, chat_id):
#                 pass  # Assuming send_message is an iterable that returns chunks

#             # If send_message is successful and chunk is not None, return the text from the last chunk
#             if chunk is not None:
#                 return chunk["text"]

#         except RuntimeError as e:
#             if 'Server Error' in str(e):
#                 attempt += 1
#                 # Todo 1 - Totest - Cancel message if chunk exists and not to overload the server
#                 if chunk is not None:
#                     client.cancel_message(chunk)
#                 print(f"Server Error encountered. Retry attempt {attempt}/{max_retries}.")
#                 # Wait for 20 seconds before retrying
#                 await asyncio.sleep(20)
#             else:
#                 raise e  # Reraise the exception if it's not a Server Error

#     print(f"Failed to send message after {max_retries} retries. Skipping message.")


async def send_message_with_retry(message, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            print('Running query...')
            response = None
            for chunk in perplexity.search(message):
                response = chunk  # Assuming the last chunk contains the answer
            
            # After iterating over the generator, check if the response contains 'answer'
            if response and 'answer' in response:
                print(response['answer'])
                return response['answer']

        except RuntimeError as e:
            if 'Server Error' in str(e):
                attempt += 1
                print(f"Server Error encountered. Retry attempt {attempt}/{max_retries}.")
                # Since this is an async function, we still need to wait asynchronously.
                await asyncio.sleep(20)
            else:
                raise e

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break  # Break on unexpected errors

    print(f"Failed to send message after {max_retries} retries. Skipping message.")

async def scrape_funda(area, url, domain, ad_selector, next_button_selector, cookie_modal_selector, page_number=1):
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

        url = url.format(area=area, page_number=page_number)
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
            print("No cookie modal defined in config, continuing")

        try:
            print(f"-- Scraping page {page_number}--")
            # Wait for the page to load fully
            await page.wait_for_load_state()
                        
            # Extract data from the page
            ads = await page.query_selector_all(ad_selector)

            # Todo 2 - case of Domica loads the page but not yet loading the selectors and review Pararius scraping
            if not ads:
                print(f'wait_for_selector({ad_selector})')
                ads = await page.wait_for_selector(ad_selector)
                print(f'ads found: {ads}')

            for ad in ads:
                    text = await ad.inner_text()
                    # print(f"-- Extracting data from {text}")

                    # Taking in consideration every website has an anchor for the ad details/content - find the href for the ad_link
                    href_regex = re.compile(r'\bhref=["\']([^\'" >]+)')
                    # Get the outer HTML of the ad element
                    outer_html = await ad.inner_html()
                    
                    # Search for hrefs within the HTML using the regex
                    matches = href_regex.findall(outer_html)
                    if matches:
                        # Just an example to print or process the first found URL
                        href = matches[0]

                        # Check whether missing domain url
                        if domain not in href:
                            href = domain + href
                        print(f'Processing ad - {href}')

                        # Todo last - to improve through all sites?
                        # Define any query parameters you want to send
                        params = {
                            'ad_link': href
                        }

                        # Send a GET request with the query parameters
                        response = requests.get(api_url, params=params)

                        # Check if the request was successful
                        if response.status_code == 200 and response.json():
                            # Parse the response JSON into a Python dictionary
                            print(f'Found data! - Skipping call to AI')
                            continue
                        else:
                            ## Call Poe ##

                            # Create a new context with a different user agent for each ad
                            new_user_agent = userAgentStrings[random.randint(0, len(userAgentStrings) - 1)]
                            ad_context = await browser.new_context(user_agent=new_user_agent)

                            ad_page = await ad_context.new_page()

                            # Click the ad using the selector within the new page
                            await ad_page.goto(f"{href}")
                            await ad_page.wait_for_load_state()

                            # Reading the whole body because might be the AI can cross-find some information
                            # from other boxes present in the page rather the description only
                            page_text = await ad_page.inner_text('body')

                            # print(f'single ad: {text}')
                            message = """
                            From this text, cleanse it and convert the information (if there) to a JSON object matching this schema: 

                            {
                                "address":"",
                                "price":"",
                                "area":"",
                                "bedrooms":"",
                                "energy_label":"",
                                "broker":""
                            }

                            Field explenation:
                            address - a string, must be formatted in: street, postal code, city
                            price - a string, number only, must exclude other chars 
                            area - a string, number only, must exclude other chars 
                            bedrooms - a string, bedrooms number only
                            energy_label - a string
                            broker - a string

                            Note: Limit responses to valid JSON, with no explanatory text. Never truncate the JSON with an ellipsis. Always srurround the values with double quotes and escape quotes with \\. Always omit trailing commas. 

                            Text:
                            """
                            message += text + "\n" + page_text
                            # print(f'message: {message}')
                            # response_text = await send_message_with_retry(client, bot, message, 270446664) # chinchilla
                            response_text = await send_message_with_retry(message) # Perplexity
                            # Add a new field with the key 'ad_link' and the value of href
                            response_text = cleanse(response_text)
                            response_data = json.loads(response_text)
                            print(response_data)
                            id = generate_md5_hash(response_data)
                            # response_data['id'] = id
                            response_data['ad_link'] = href
                            updated_response_text = json.dumps(response_data, ensure_ascii=False)

                            # response_text = await send_message_with_retry(client, bot, message, 262252582) # a2
                            # print(f'Response text: {response_text}')

                            save_data(updated_response_text, area)
                            # print(f"Data - page {page_number}: {data}")
                            
                            # Send notification
                            
                            notification_message = """
                            🏄 Found new ad!
                            {address} - €{price} p/m - {bedrooms} bedroom(s) - {area} m2
                            {ad_link}
                            """

                            format_msg_lines = [line.strip() for line in notification_message.format(
                                address=response_data['address'],
                                price=response_data['price'],
                                bedrooms=response_data['bedrooms'],
                                area=response_data['area'],
                                ad_link=response_data['ad_link']
                            ).splitlines()]

                            # Join the stripped lines back into a single string
                            format_msg = "\n".join(format_msg_lines)

                            async with TelegramClient(session_file, tg_api_id, tg_api_hash) as tg_client:
                                await tg_client.send_message(tg_phone_number, format_msg)
                            # Close the ad page and context after processing
                            await ad_page.close()
                            await ad_context.close()
                    else:
                        print("No URL found in the HTML of this ad.")
                
                    # TODO - Handle pagination if required
                    # next_button = await page.query_selector(next_button_selector)
                    # print("Next Page btn:", next_button)
                    # if next_button:
                    #     print(f"Another page for {area}")     
                    #     await scrape_funda(area, url, ad_selector, next_button_selector, page_number + 1)
        except Exception as e:
            print(f"There was an error processing this ad - {href} - Error: {e}")  # Re-raise the exception after saving
        finally:
            await browser.close()

    print(f'Saved into {filename}')
    print(f"-- End {broker['name']} --")

if __name__ == "__main__":
    area = None
    if len(sys.argv) > 1 and sys.argv[1] == "-area":
        if len(sys.argv) > 2:
            area = sys.argv[2]

    def setup_connection_to_poe(api_key):
        client = PoeApi(api_key)
        bot = "acouchy"
        # bot = "chinchilla_instruct"
        # bot = "a2"
        return client, bot

    # Function to load configurations
    def load_config(config_file):
        with open(config_file, 'r') as file:
            return json.load(file)

    # Function to get broker info
    def get_broker_info(broker_name, config):
        for broker in config.get('brokers', []):
            if broker['name'] == broker_name:
                return broker
        return None

    # Config
    # Read API key from a file and pass it to the function
    api_info = load_config('./utilities/api_key.json')
    api_key = api_info["key"]
    # client, bot = setup_connection_to_poe(api_key) Poe
    # Replacing with Perplexity
    perplexity = Perplexity()
        
    # Setup Telegram
    tg_api_id = api_info["tg_api_id"]
    tg_api_hash = api_info["tg_api_hash"]
    tg_phone_number = api_info["tg_phone_number"]
    session_file = 'session'
    
    config = load_config('./utilities/brokers.json')
    filename = re.sub(r",", "_", f'./results/results_{area}.jsonl')
    # Define the API endpoint
    api_url = 'http://localhost:5000/ads'

    # Loop through all the brokers in the config
    for broker in config['brokers']:
        print(f"Scraping {broker['name']}")
        domain = broker['domain']
        url = broker['url']
        ad_selector = broker['ad_selector']
        next_button_selector = broker['next_button_selector']
        cookie_modal_selector = broker['cookie_modal_selector']
        
        try:
            # Call scrape function for the current broker
            # asyncio.run(scrape_funda(client, bot, area, url, domain, ad_selector, next_button_selector, cookie_modal_selector)) Poe
            asyncio.run(scrape_funda(area, url, domain, ad_selector, next_button_selector, cookie_modal_selector))
        except Exception as e:
            print(f"An error occurred while scraping {broker['name']} for area {area}: {e}")
    
    # Close perplexity connection
    perplexity.close()