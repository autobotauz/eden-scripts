import requests, csv, json, urllib.parse, argparse, re

# Set up argument parser
parser = argparse.ArgumentParser(description='Fetch item data and save to CSV')
parser.add_argument('--realm', default='', help='Realm: albion/alb (1), midgard/mid (2), hib/hibernia (3)')
parser.add_argument('--item', default='', help='Item name to search for')
parser.add_argument('--price', default=0, help='Max price')
parser.add_argument('--min_utility', default=0, help='Minimum utility')
parser.add_argument('--max_utility', default=200, help='Maximum utility')
parser.add_argument('--search_url', default='', help='Specific Eden search response url')
parser.add_argument('--append', action='store_true', help='Append to CSV - if not used a new csv will be created')
args = parser.parse_args()

# Map realm string to corresponding realm id
realm_map = {
    'albion': '1', 'alb': '1',
    'midgard': '2', 'mid': '2',
    'hibernia': '3', 'hib': '3'
}
realm_id = realm_map.get(args.realm.lower(), '2')  # Default to midgard (2) if invalid - because I'm playing mid right meow

# URL-encode the item name because we care
item_encoded = urllib.parse.quote(args.item)

# Base eden market seach URL
base_url = f"https://eden-daoc.net/itm/market_search.php?r={realm_id}&c=22"
# add item encoded string
if args.item:
    base_url += f"&s={item_encoded}"

# override base_url with user search_url if provided 
if args.search_url:
    base_url = args.search_url

# Headers from cURL
headers = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://eden-daoc.net/items",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest"
}

# Cookies from cURL
cookies = {
    "eden_daoc_u": "", # add your eden_daoc_u value
    "eden_daoc_sid": "" # add your eden_daoc_sid value here
}

# Convert QoL price format to copper
def price_to_copper(price_str):
    pattern = re.compile(r'(?:(\d+)p)?(?:(\d+)g)?(?:(\d+)s)?(?:(\d+)c)?', re.IGNORECASE)
    match = pattern.fullmatch(price_str.strip())
    if not match:
        raise ValueError(f"Invalid price string format: {price_str}")

    platinum = int(match.group(1) or 0)
    gold = int(match.group(2) or 0)
    silver = int(match.group(3) or 0)
    copper = int(match.group(4) or 0)

    total_copper = (
        platinum * 10000000 +
        gold * 10000 +
        silver * 100 +
        copper
    )
    return total_copper

# CSV headers that I think are to be true to the response
csvheaders = [
    'houseNumber', 'marketId', 'itemPrice', 'quality', 'con', 'durability',
    'unknown1', 'itemName', 'unknown2', 'model', 'unknown4',
    'utility', 'unknown5', 'unknown6', 'unknown7', 'unknown8', 'unknown9', 'unknown10', 'url'
]

# Initialize CSV file - append or writer based on append flag
csvfile = open('items.csv', 'a' if args.append else 'w', newline='', encoding='utf-8')
writer = csv.writer(csvfile)
# Don't write rows again if we're appending
if not args.append:
    writer.writerow(csvheaders)  # Write headers

# Initialize page counter because I couldn't find a pagination value in the response
page = 0
# If we find a low utility, lets break out of our loop and not hit Eden APIs anymore - we're nice like that
lowUtilFound = False
while True:
    # Update page number
    url = f"{base_url}&p={page}"
    print(f"Fetching page {page}: {url}")

    # Send GET request to get our items
    response = requests.get(url, headers=headers, cookies=cookies)

    # Check if request was successful
    if response.status_code == 200:
        # Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"Failed to parse JSON on page {page}. Status code: {response.status_code}")
            break

        # Extract the "l" key - list of items
        items = data.get('l', [])

        # Break if no items found i.e at last page
        if len(items) == 0:
            print(f"No more items found on page {page}. Stopping.")
            break

        # Process each item in the "l" list
        for item in items:
            # Split the item string by commas
            item_data = item.split(',')
            # Ensure item_data has enough fields
            if len(item_data) < 12:
                print(f"Skipping malformed item on page {page}: {item}")
                continue
            # Append the market url for the item using marketID
            item_data.append(f'https://eden-daoc.net/items?m=market&mid={item_data[1]}')
            try:
                # Get copper from user price
                new_price = price_to_copper(args.price) if args.price else float('inf')
                # Item values to be used
                item_price = int(item_data[2])
                item_utility = float(item_data[11])
                # Found our item, write to file
                if item_utility <= float(args.max_utility) and item_utility >= float(args.min_utility) and item_price <= new_price:
                    writer.writerow(item_data)
                # I believe items are provided desc order on utility value. Break iteration if we find utility less than what we want
                if float(item_utility) < float(args.min_utility):
                    lowUtilFound = True
            except (ValueError, IndexError) as e:
                print(f"Error processing item on page {page}: {item}. Error: {e}")
                continue
        if lowUtilFound:
            print("Found a low utility item, stopping the search.")
            break
        # Increment page
        page += 1
    else:
        print(f"Failed to fetch data on page {page}. Status code: {response.status_code}")
        break

# Close CSV file
csvfile.close()