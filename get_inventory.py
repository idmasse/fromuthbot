from utils.ftp_utils import connect_ftp, upload_files
from utils.auth_utils import *
import requests
import sys
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "inventory.csv")
PAGE_SIZE = 500

def get_inventory_page(token, page_no=0, page_size=PAGE_SIZE):
    """
    Retrieve a single page of inventory items.
    Only items that are active are returned.
    """
    items_url = f"{API_BASE_URL}/item"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # filter: active = true and inventory >= 0
    params = {
        "select": "itemcode,sku,name,color,upc,size,sizeNum,ModelCode,GroupCode,active,description,brand,url,images,inventory,prices",
        "page_no": page_no,
        "page_size": page_size,
        "filter": "(active,eq,true)and(inventory,ge,0)"
    }
    
    try:
        response = requests.get(items_url, headers=headers, params=params)
        response.raise_for_status()
    except requests.RequestException as err:
        sys.exit(f"Failed to retrieve inventory page {page_no}: {err}")
    
    return response.json()

def parse_prices(prices):
    """
    Convert a list of price objects into a dictionary.
    It tries to grab the price using either "key" or "Key" and similarly for the value.
    """
    pricing = {}
    for price in prices:
        key = price.get("key") or price.get("Key", "")
        if key:
            key = key.strip()
        value = price.get("value") or price.get("Value", "")
        pricing[key] = value
    return pricing

def get_large_images(images_obj):
    """
    Extract all available large image URLs from the images object.
    Only images under the "LARGE" key are returned.
    """
    if images_obj and "LARGE" in images_obj:
        urls = images_obj["LARGE"]
        if isinstance(urls, list):
            return urls
    return []

def export_inventory_to_csv(items, filename):
    """
    Exports the list of items to CSV.
    The CSV will include:
      - Common fields: itemcode, sku, name, color, upc, size, sizeNum, ModelCode, GroupCode, active, description, brand, url, inventory.
      - One column per unique price key found across all items.
      - One column per large image (image1, image2, …) based on the maximum number of large images.
    """
    processed_items = []
    all_price_keys = set()
    max_image_count = 0

    for item in items:
        price_dict = parse_prices(item.get("prices", []))
        all_price_keys.update(price_dict.keys())
        
        # get large imgs
        large_images = get_large_images(item.get("images", {}))
        if len(large_images) > max_image_count:
            max_image_count = len(large_images)
        
        processed_items.append({
            "itemcode": item.get("itemcode", ""),
            "sku": item.get("sku", ""),
            "name": item.get("name", ""),
            "color": item.get("color", ""),
            "upc": item.get("upc", ""),
            "size": item.get("size", ""),
            "sizeNum": item.get("sizeNum", ""),
            "ModelCode": item.get("ModelCode", ""),
            "GroupCode": item.get("GroupCode", ""),
            "active": item.get("active", ""),
            "description": item.get("description", ""),
            "brand": item.get("brand", ""),
            "url": item.get("url", ""),
            "inventory": item.get("inventory", ""),
            "prices": price_dict,
            "large_images": large_images
        })

    # sorted list of unique price keys for consistent ordering
    price_columns = sorted(all_price_keys)
    
    #csv headers
    fieldnames = [
        "itemcode", "sku", "name", "color", "upc", "size", "sizeNum",
        "ModelCode", "GroupCode", "active", "description", "brand", "url", "inventory"
    ]
    fieldnames.extend(price_columns)
    for i in range(max_image_count):
        fieldnames.append(f"image{i+1}")

    try:
        with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for processed_item in processed_items:
                row = {}
                # fields
                for key in ["itemcode", "sku", "name", "color", "upc", "size", "sizeNum",
                            "ModelCode", "GroupCode", "active", "description", "brand", "url", "inventory"]:
                    row[key] = processed_item.get(key, "")
                # prices
                for price_key in price_columns:
                    row[price_key] = processed_item["prices"].get(price_key, "")
                # images
                large_images = processed_item["large_images"]
                for i in range(max_image_count):
                    col_name = f"image{i+1}"
                    row[col_name] = large_images[i] if i < len(large_images) else ""
                writer.writerow(row)
    except IOError as err:
        sys.exit(f"Error writing CSV file: {err}")

def fetch_all_inventory(token):
    """
    Iterate through all pages to fetch every available inventory item that matches the filter.
    """
    all_items = []
    page_no = 0

    while True:
        print(f"Fetching page {page_no}...")
        response = get_inventory_page(token, page_no)
        items = response.get("_embedded", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)
        if len(items) < PAGE_SIZE:
            break
        page_no += 1

    return all_items

def get_inventory():
    print("Authenticating with the API...")
    token = get_jwt()
    
    print("Fetching all inventory pages for active items with inventory >= 0 units")
    all_items = fetch_all_inventory(token)
    
    if not all_items:
        print("No items found in the API response.")
        return
    
    print(f"Total items fetched: {len(all_items)}")
    
    export_inventory_to_csv(all_items, OUTPUT_CSV)
    print(f"Inventory data exported successfully to '{OUTPUT_CSV}'.")

    ftp = connect_ftp()
    if ftp:
        try:
            remote_filename = os.path.basename(OUTPUT_CSV)
            upload_files(ftp, OUTPUT_CSV, remote_filename)
        finally:
            ftp.quit()
            print('ftp connection closed')
    else:
        print('could not connect to ftp')
        return

if __name__ == "__main__":
    get_inventory()
    get_inventory_success = get_inventory()
    sys.exit(0 if get_inventory_success else 1)