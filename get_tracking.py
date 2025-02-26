import json
import requests
from utils.auth_utils import *
from utils.gsheet_utils import setup_google_sheets
from dotenv import load_dotenv

load_dotenv()

def get_order_by_customer_order_number(customer_order_number, headers):
    url = f"{API_BASE_URL}/order/{customer_order_number}"
    params = {
        "by": "customer_order_number",
        "select": "order_number,customer_order_number,ec_order_number,state,tracking_numbers,order_notes,documents"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def update_sheet_with_tracking(sheet, headers):
    rows = sheet.get_all_values()  # get all rows from the sheet

    # loop over each row in the sheet
    for i, row in enumerate(rows[1:], start=2):
        customer_order_number = row[0].strip() if len(row) > 0 else ""  # col A: customer order number
        carrier = row[2].strip() if len(row) > 2 else ""                # col C: carrier (shipping method)
        tracking_number = row[3].strip() if len(row) > 3 else ""        # col D: tracking number

        if customer_order_number and not tracking_number:
            print(f"\nFinding tracking for order number: {customer_order_number}")
            try:
                #get order details using the customer order number
                order_response = get_order_by_customer_order_number(customer_order_number, headers)
                
                print("Full API response:")
                print(json.dumps(order_response, indent=4))
                
                order = order_response.get('_embedded', {}).get('order')
                if order:
                    # get tracking numbers from the order
                    tracking_numbers = order.get("tracking_numbers", [])
                    
                    # check document for tracking info
                    if not tracking_numbers:
                        documents = order.get("documents", [])
                        for doc in documents:
                            tracking = doc.get("tracking")
                            if tracking:
                                tracking_numbers.append(tracking)
                    
                    print("Extracted tracking_numbers:", tracking_numbers)
                    
                    # get the shipping method name from documents
                    if not carrier:
                        documents = order.get("documents", [])
                        for doc in documents:
                            method = doc.get("shipping_method_name")
                            if method:
                                carrier = method
                                break
                    
                    # take the first tracking number
                    if tracking_numbers:
                        tracking_number = tracking_numbers[0]
                    else:
                        tracking_number = ""
                        print(f"No tracking number found for order: {customer_order_number}")
                    
                    # print order notes
                    order_notes = order.get("order_notes", "")
                    print("Order notes:", order_notes)
                    
                    # update sheet with shipping method and tracking number
                    sheet.update_cell(i, 3, carrier)       # col C: carrier/shipping method
                    sheet.update_cell(i, 4, tracking_number) # col D: tracking number
                    print(f"Updated row {i}: Carrier: {carrier}, Tracking Number: {tracking_number}")
                else:
                    print(f"Order not found for customer order number: {customer_order_number}")
            except Exception as e:
                print(f"Error processing order {customer_order_number}: {str(e)}")

def get_tracking():
    token = get_jwt()
    headers = {'Authorization': f'Bearer {token}'}

    sheet = setup_google_sheets()
    update_sheet_with_tracking(sheet, headers)

if __name__ == '__main__':
    get_tracking()
