# Fromuth Order & Inventory Automation

This repo contains an automation suite that integrates with the Fromuth API, an FTP server, and Google Sheets to:

- **Automatically download and process order CSVs** from an FTP drop.
- **Place orders via the Fromuth API** and log results.
- **Sync shipment tracking numbers** back into a Google Sheet.
- **Export inventory data to CSV** and upload it to FTP for downstream systems.

The main entrypoint is `main.py`, which orchestrates the full end-to-end workflow.

This automation was built as a method of integrating the proprietary ERP/ecom platform that the sports equipment distributor Fromuth uses with the dropshipping app Flip Shop.

---

## Features

- **Order ingestion from FTP**
  - Connects to an FTP server and downloads `.csv` order files from `/out/orders`.
  - Archives processed order files into `/out/orders/archive` on the FTP server and into a local `processed` folder.

- **Order creation via API**
  - Groups CSV lines by PO number.
  - Calls the Fromuth API to place orders.
  - Skips orders that have already been placed.
  - Records Flip PO / Fromuth order number mappings into a Google Sheet for tracking.

- **Tracking number sync**
  - Reads a Google Sheet of orders.
  - For orders without tracking, looks up the order via API and updates carrier + tracking number columns.
  - Handles cancelled orders explicitly.

- **Inventory export**
  - Paginates through the API to fetch all active items with inventory ≥ 0.
  - Normalizes price structures and image URLs into a flat CSV.
  - Uploads the resulting `inventory.csv` to an FTP folder (`/in/inventory`).

- **Email notifications**
  - Sends email alerts on critical failures (auth issues, order processing errors).
  - Sends a summary email after each batch of order processing.

- **Runs Scheduled by launchd**
  - `com.fromuth.plist` dictates how to run `main.py` via `launchd` on a schedule (every hour).

---

## Project Structure

- **`main.py`**
  - Top-level script that:
    - Downloads order CSVs from FTP.
    - Archives them on FTP.
    - Authenticates with the API.
    - Processes orders via `post_orders.process_order_file`.
    - Sends a success/failure summary email.
    - Triggers `get_tracking()` and `get_inventory()` at the end of the run.

- **`post_orders.py`**
  - Core order-processing logic:
    - Reads CSVs from `LOCAL_ORDERS_DIR`.
    - Groups rows by `PO_num`.
    - Builds API payloads and calls the order endpoint.
    - Adds Flip PO and Fromuth order numbers to the Google Sheet (`fromuth tracking`).
    - Tracks successes/failures and sends error emails when an order fails.

- **`get_tracking.py`**
  - Reads all rows from the tracking Google Sheet.
  - For rows with a Flip order number but no tracking:
    - Calls the order API using `customer_order_number`.
    - Determines carrier and tracking number from `tracking_numbers` or `documents`.
    - Handles cancelled orders by marking both carrier and tracking as `CANCELLED`.
  - Performs a batch update of carrier + tracking columns in the sheet.

- **`get_inventory.py`**
  - Authenticates against the API.
  - Paginates through `/item` to fetch active items with inventory ≥ 0.
  - Normalizes:
    - Core fields (itemcode, sku, name, brand, etc.).
    - All unique price keys across items.
    - All large image URLs into `image1`, `image2`.
  - Writes to `inventory.csv`.
  - Uploads the CSV to FTP (inventory directory) and closes the connection.

- **`utils/auth_utils.py`**
  - Loads API configuration from environment (`.env`).
  - Provides:
    - `API_BASE_URL`, `API_STAGING_URL`
    - `API_USERNAME`, `API_PASSWORD`, `API_STAGING_PASSWORD`
    - `LOCAL_ORDERS_DIR`
  - Defines `APIError` and `get_jwt()` for API authentication.

- **`utils/ftp_utils.py`**
  - Handles FTP connectivity and file operations:
    - `connect_ftp()` – login using FTP host/user/pass.
    - `download_files()` – fetches order CSVs from `/out/orders` into `LOCAL_ORDERS_DIR`.
    - `archive_files_on_ftp()` – moves processed orders into `/out/orders/archive`.
    - `upload_files()` – uploads files (e.g. `inventory.csv`) to `/in/inventory`.

- **`utils/email_utils.py`**
  - Sends email via SMTP (Gmail by default) using credentials from `.env`.
  - Used for:
    - Auth failure notifications.
    - Order processing error notifications.
    - Post-run summary emails.

- **`utils/gsheet_utils.py`**
  - Google Sheets integration:
    - `setup_google_sheets()` – authenticates using `utils/gsheet_creds.json` and opens the `fromuth tracking` sheet.
    - `add_po_num_fromuth_num_to_sheet()` – appends a new row containing PO and Fromuth order number.

- **`orders/`**
  - Example and processed order CSVs.
  - `orders/processed/` contains archived copies of files that have already been processed.

- **`requirements.txt`**
  - Python dependencies (requests, python-dotenv, gspread, google-auth, etc.).

- **`.gitignore`**
  - Ignores:
    - `dev_tools/`
    - `orders/`
    - `venv/`
    - `.env`
    - `utils/gsheet_creds.json`
    - `.DS_store`

- **`com.fromuth.plist`**
  - Example macOS `launchd` config to run `main.py` on an interval, with stdout/stderr logged to files.

---

## Prerequisites

- **Python**: 3.9+ recommended.
- **Fromuth API credentials**:
  - Username, password, and base URLs for production and/or staging.
- **FTP server access**:
  - Host, username, password, and expected directory structure.
- **Google Cloud service account**:
  - Service account JSON key for Google Sheets API.
  - The `fromuth tracking` Google Sheet shared with that service account.
- **SMTP account (Gmail or similar)**:
  - Email address and password/app password for sending notifications.

---

## Usage

### Run the full pipeline

Runs: download orders → place orders → send summary email → update tracking sheet → export & upload inventory.

```bash
source venv/bin/activate
python main.py
```

### Just update tracking

If you only want to sync tracking numbers into the Google Sheet:

```bash
source venv/bin/activate
python get_tracking.py
```

### Just export and upload inventory

If you only want to generate `inventory.csv` and upload it to FTP:

```bash
source venv/bin/activate
python get_inventory.py
```

---

## Automation with launchd (macOS)

To run `main.py` automatically on a schedule on macOS:

- Use `com.fromuth.plist` as a template.
- Update:
  - Python interpreter path.
  - Path to `main.py`.
  - Log file paths.
- Load into `launchd`:

```bash
cp com.fromuth.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fromuth.plist
```

