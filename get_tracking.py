import json
import requests
from utils.auth_utils import get_jwt, API_BASE_URL
from utils.gsheet_utils import setup_google_sheets
from dotenv import load_dotenv
import sys

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
    updated_data = []  # store updated values for batch write to gsheets later

    # Loop over each data row (skip header, starting at row 2)
    for i, row in enumerate(rows[1:], start=2):
        customer_order_number = row[0].strip() if len(row) > 0 else ""  # col A: customer order number
        carrier = row[2].strip() if len(row) > 2 else ""                # col C: carrier (shipping method)
        tracking_number = row[3].strip() if len(row) > 3 else ""          # col D: tracking number

        if customer_order_number and not tracking_number:
            print(f"\nFinding tracking for order number: {customer_order_number}")
            try:
                # Get order details using the customer order number
                order_response = get_order_by_customer_order_number(customer_order_number, headers)
                print("Full API response:")
                print(json.dumps(order_response, indent=4))
                
                order = order_response.get('_embedded', {}).get('order')
                if order:
                    order_state = order.get("state", "")
                    if order_state.upper() == "CANCELLED":
                        carrier = "CANCELLED"
                        tracking_number = "CANCELLED"
                        print(f"Order {customer_order_number} is cancelled. Setting carrier and tracking to 'cancelled'")
                    else:
                        # For non-cancelled orders, process tracking numbers
                        tracking_numbers = order.get("tracking_numbers", [])
                        # Check documents for tracking info if none exist
                        if not tracking_numbers:
                            for doc in order.get("documents", []):
                                tracking = doc.get("tracking")
                                if tracking:
                                    tracking_numbers.append(tracking)
                        print("Extracted tracking_numbers:", tracking_numbers)
                        
                        # Get the shipping method name from documents if not already set
                        if not carrier:
                            for doc in order.get("documents", []):
                                method = doc.get("shipping_method_name")
                                if method:
                                    carrier = method
                                    break
                        
                        # Take the first tracking number if available
                        if tracking_numbers:
                            tracking_number = tracking_numbers[0]
                        else:
                            tracking_number = ""
                            print(f"No tracking number found for order: {customer_order_number}")
                        
                        # Print order notes for debugging
                        order_notes = order.get("order_notes", "")
                        print("Order notes:", order_notes)
                    
                    print(f"Updated row {i}: Carrier: {carrier}, Tracking Number: {tracking_number}")
                else:
                    print(f"Order not found for customer order number: {customer_order_number}")
            except Exception as e:
                print(f"Error processing order {customer_order_number}: {str(e)}")

        updated_data.append([carrier, tracking_number])
    
    end_row = len(rows)
    range_str = f"C2:D{end_row}"
    print(f"\nPerforming batch update to range {range_str} with {len(updated_data)} rows.")
    sheet.update(range_str, updated_data)
    print("Batch update complete!")

def get_tracking():
    token = get_jwt()
    headers = {'Authorization': f'Bearer {token}'}
    sheet = setup_google_sheets()
    update_sheet_with_tracking(sheet, headers)

if __name__ == '__main__':
    get_tracking_success = get_tracking()
    sys.exit(0 if get_tracking_success else 1)