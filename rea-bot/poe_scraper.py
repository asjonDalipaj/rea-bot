import asyncio
import random
import json
import re
import sys
import hashlib
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

async def scrape_funda(client, bot, area, url, ad_qry, next_button_qry, page_number=1):
    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True) 

        userAgentStrings = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.2227.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.2228.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.3497.92 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        ];

        context = await browser.new_context(
            user_agent=userAgentStrings[random.randint(0, len(userAgentStrings) - 1)]
        )

        page = await context.new_page()
        
        url = url.format(area=area, page_number=page_number)
        await page.goto(url)

        print(f"-- Scraping page {page_number}--")
        # Wait for the page to load fully
        await page.wait_for_load_state()
        
        # Extract data from the page
        ads = await page.query_selector_all(ad_qry)

        for ad in ads:
            text = await ad.inner_text()
            # Here click into the element (ad and extract the page text)
            # await ad.click(force=True)
            # current_url = page.url
            # print(f"The current URL after clicking the ad is: {current_url}")

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
            message += text
            # print(f'message: {message}')
            response_text = await send_message_with_retry(client, bot, message, 270446664)
            print(response_text)

            data.append(response_text)
            # print(f"Data - page {page_number}: {data}")
            
        # Handle pagination if required
        next_button = await page.query_selector(next_button_qry)
        # print("Next Page btn:", next_button)
        # if next_button:
        #     print(f"Another page for {area}")     
        #     # await page.screenshot(path="screenshot2.png")
        #     await scrape_funda(area, url, ad_qry, next_button_qry, page_number + 1)

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
        bot = "a2"
        return client, bot

    # Read API key from a file and pass it to the function
    with open('api_key.txt', 'r') as file:
        api_key = file.read().strip()  # .strip() removes any leading/trailing whitespace
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
    broker_info = get_broker_info('Funda', config)

    if broker_info:
        print(f"Scraping {broker_info['name']}")
        url = broker_info['url']
        ad_qry = broker_info['ad_qry']
        next_button_qry = broker_info['next_button_qry']
    else:
        print("Broker not found.")

    # existing_addresses = load_existing_ids('results.json')

    asyncio.run(scrape_funda(client, bot, area, url, ad_qry, next_button_qry))