import asyncio
import random
import json
import re
import sys
import hashlib
import os
from playwright.async_api import async_playwright
from poe_api_wrapper import PoeApi

data = []

# Utilities func
def create_text_hash(text):
    # Create a hash  of the complete text
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_existing_ids(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Create a set of hashes for all existing entries
            return {item['id'] for item in data}
    except FileNotFoundError:
        return set()
    
# Function to save data
def save_data(data, area):
    filename = f'./results/results_{area}.json'
    # Make sure the directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def send_message_with_retry(client, bot, message, chat_id="", max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            for chunk in client.send_message(bot, message, chat_id):
                pass
            return chunk["text"]
        except RuntimeError as e:
            if 'Server Error' in str(e):
                attempt += 1
                print(f"Server Error encountered. Retry attempt {attempt}/{max_retries}.")
                await asyncio.sleep(20) # Wait for 20 seconds before retrying
            else:
                raise e
    print(f"Failed to send message after {max_retries} retries. Skipping {message}")

async def scrape_funda(client, bot, area, url, domain, ad_selector, next_button_selector, cookie_modal_selector, page_number=1):
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

        # Todo check for removal - Remove cookie dialog for cleaning up page
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
            for ad in ads:
                    text = await ad.inner_text()
                    # print(f"-- Extracting data from {text}")
                    # Taking in consideration every website has an anchor for the ad details/content
                    anchor = await ad.query_selector('a')
                    
                    # Todo - Check if the data is not already saved
                    # if ad_data['id'] not in existinclassg_ids:
                    #     data.append(ad_data)  # Add the ad's data to the list
                    #     existing_ids.add(ad_data['id'])
                        
                    if anchor:
                        href = await anchor.get_attribute('href')
                        if href:

                            #Check whether missing domain url
                            if domain not in href:
                                href = domain + href
                            
                            print(f"Ad link: {href}")

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
                                "address": "",
                                "price": "",
                                "area": "",
                                "bedrooms": "",
                                "energy_label": "",
                                "broker": "",
                                "ad_link": ""
                            }

                            Field explenation:
                            address - a string, must be formatted street, postal code, city
                            price - an int, price only, must exclude other chars 
                            area - an int, area only, must exclude other chars 
                            bedrooms - an int  -  bedrooms number 
                            energy_label - a string  -  energy label 
                            broker - a string  -  broker name 

                            Note: Limit responses to valid JSON, with no explanatory text. Never truncate the JSON with an ellipsis. Always srurround the values with double quotes and escape quotes with \\. Always omit trailing commas. 

                            Text:
                            """
                            message += text + "\n" + page_text
                            # print(f'message: {message}')
                            response_text = await send_message_with_retry(client, bot, message, 270446664) # chinchilla
                            # response_text = await send_message_with_retry(client, bot, message, 262252582) # a2
                            print(response_text)

                            data.append(response_text)
                            save_data(data, area)
                            # print(f"Data - page {page_number}: {data}")

                            # Close the ad page and context after processing
                            await ad_page.close()
                            await ad_context.close()
                        else:
                            print("No href found! Skipping")
                
                    # TODO - Handle pagination if required
                    # next_button = await page.query_selector(next_button_selector)
                    # print("Next Page btn:", next_button)
                    # if next_button:
                    #     print(f"Another page for {area}")     
                    #     await scrape_funda(area, url, ad_selector, next_button_selector, page_number + 1)
        except Exception as e:
            # Save before re-raising the exception
            save_data(data, area)
            print(f"There was an error processing this ad - {text} - Error: {e}")  # Re-raise the exception after saving
        finally:
            await browser.close()

    # Write data to JSON file
    parsed_data = [json.loads(ad) for ad in data]

    filename = re.sub(r",", "_", area)
    with open(f'./results/results_{filename}.json', 'w', encoding='utf-8') as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=4)

    print(f'Saved into results_{filename}.json')
    print("-- End --")


if __name__ == "__main__":
    area = None
    if len(sys.argv) > 1 and sys.argv[1] == "-area":
        if len(sys.argv) > 2:
            area = sys.argv[2]

    def setup_connection_to_poe(api_key):
        client = PoeApi(api_key)
        bot = "chinchilla_instruct"
        # bot = "a2"
        return client, bot

    # Read API key from a file and pass it to the function
    with open('./utilities/api_key.json', 'r') as file:
        api_key = json.load(file)["key"]
        client, bot = setup_connection_to_poe(api_key)

    # Read brokers 
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

    # Usage
    config = load_config('./utilities/brokers.json')

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
            asyncio.run(scrape_funda(client, bot, area, url, domain, ad_selector, next_button_selector, cookie_modal_selector))
        except Exception as e:
            print(f"An error occurred while scraping {broker['name']} for area {area}: {e}")