from utils.ftp_utils import *
from utils.auth_utils import *
from utils.email_utils import send_email
from post_orders import *
from get_tracking import get_tracking
from get_inventory import get_inventory
from dotenv import load_dotenv
import os

load_dotenv()

def main():
    # setup local archive directory
    archive_dir = os.path.join(LOCAL_ORDERS_DIR, 'processed')
    os.makedirs(archive_dir, exist_ok=True)

    # download files from FTP
    ftp = connect_ftp()
    downloaded_files = []
    if ftp:
        try:
            downloaded_files = download_files(ftp)
        finally:
            if downloaded_files:
                archive_files_on_ftp(ftp, downloaded_files)
            ftp.quit()
            print("FTP connection closed")
    else:
        print("Could not connect to FTP")
        return

    if not downloaded_files:
        print("No files to download")
        return

    # authenticate with API
    try:
        token = get_jwt()
    except APIError as e:
        error_message = f"Failed to authenticate with API: {str(e)}"
        print(error_message)
        send_email("Fromuth Authentication Error", error_message)
        return

    headers = {'Authorization': f'Bearer {token}'}

    successful_orders = []
    failed_orders = []

    # process downloaded order files & place the orders
    for file in downloaded_files:
        try:
            process_order_file(file, headers, archive_dir, successful_orders, failed_orders)
        except Exception as e:
            error_message = f"Error processing file {file}: {str(e)}"
            print(error_message)
            send_email("Fromuth Order File Failed", error_message)

    # send summary email
    print('sending summary email')
    subject = "Fromuth Order Summary"
    successful_msg = ', '.join(f'{po_num} ({f})' for f, po_num in successful_orders) if successful_orders else "None"
    failed_msg = ', '.join(f'{po_num} ({f})' for f, po_num, _ in failed_orders) if failed_orders else "None"
    # failed_msg = ', '.join(f'{po_num} ({f}): {e}' for f, po_num, e in failed_orders) if failed_orders else "None"

    body = f"""
        Successful orders: {len(successful_orders)}
        {successful_msg}

        Failed orders: {len(failed_orders)}
        {failed_msg}
        """
    send_email(subject, body)

if __name__ == '__main__':
    main()
    get_tracking()
    get_inventory()