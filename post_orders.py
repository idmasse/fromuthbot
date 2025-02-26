from utils.ftp_utils import *
from utils.auth_utils import *
from utils.email_utils import send_email
from utils.gsheet_utils import setup_google_sheets, add_po_num_fromuth_num_to_sheet
from dotenv import load_dotenv
import requests
import shutil
import os
import csv

load_dotenv()

def get_order(po_num, headers):
    url = f'{API_BASE_URL}/order/{po_num}'
    params = {'by': 'customer_order_number'}
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if response.ok:
        return data.get('_embedded', {}).get('order')
    elif response.status_code == 404:
        return None
    else:
        raise APIError(data)

def place_order(po_num, order_data, headers):
    shipping_info = order_data['shipping_info']
    payload = {
        'customer_order_number': po_num,
        'shipping_method': 1,
        'shipping_address': {
            'fullname': f"{shipping_info['fname']} {shipping_info['lname']}",
            'line_1': shipping_info['address1'],
            'line_2': shipping_info.get('address2', ''),
            'city': shipping_info['city'],
            'postal_code': shipping_info['zip'],
            'state': shipping_info['state'],
            'country': 'US'
        },
        'items': []
    }

    for item in order_data['items']:
        payload['items'].append({
            'itemcode': item['sku'],
            'quantity': item['quantity']
        })

    url = f'{API_BASE_URL}/order'
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    if response.ok:
        return data.get('data')
    else:
        raise APIError(data)

def process_order_file(file, headers, archive_dir, successful_orders, failed_orders):
    sheet = setup_google_sheets()

    file_path = os.path.join(LOCAL_ORDERS_DIR, file)
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        orders_data = list(reader)

    # group orders by PO number
    grouped_orders = {}
    for row in orders_data:
        po_num = row['PO_num']
        if po_num not in grouped_orders:
            grouped_orders[po_num] = {
                'shipping_info': {
                    'fname': row['First Name'],
                    'lname': row['Last Name'],
                    'address1': row['Ship To Address'],
                    'address2': row.get('Ship To Address 2', ''),
                    'city': row['Ship To City'],
                    'state': row['Ship To State'],
                    'zip': row['Ship To Zip']
                },
                'items': []
            }
        grouped_orders[po_num]['items'].append({
            'sku': row['SKU'],
            'quantity': int(row['QTY'])
        })

    for po_num, order in grouped_orders.items():
        try:
            existing_order = get_order(po_num, headers)
            if existing_order:
                print(f'Order {po_num} has already been placed.')
                continue

            print('placing orders...')
            order_response = place_order(po_num, order, headers)
            print(f"Successfully placed order. Fromuth Order Number: {order_response.get('order_number')}; "
                  f"Flip Order Number: {order_response.get('customer_order_number')}.")
            
            warnings = order_response.get("warnings")
            if warnings:
                warning_msgs = " ; ".join([f"[{w.get('code')}] {w.get('title')}" for w in warnings])
                print("Warnings:", warning_msgs)
            
            # add the order number to a google sheet for shipment tracking
            print('adding order info to google sheet')
            fromuth_order_num = order_response.get('order_number')
            if fromuth_order_num:
                add_po_num_fromuth_num_to_sheet(sheet, po_num, fromuth_order_num, po_num_col=1, fromuth_num_col=2)
            else:
                print('order number not found')

            successful_orders.append((file, po_num))

        except Exception as e:
            print(f"Error processing order {po_num} from file {file}: {str(e)}")
            failed_orders.append((file, po_num, str(e)))
            send_email("Fromuth Order Processing Error", f"Error processing order {po_num} from file {file}: {str(e)}")

    # archive the processed file
    try:
        shutil.move(file_path, os.path.join(archive_dir, file))
        print(f"Moved {file} to archive")
    except Exception as e:
        print(f"Failed to move {file} to archive: {str(e)}")
