import requests
import json
import math
import time
import os
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Database Configuration ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}
TABLE_NAME = 'cgr'

def fetch_and_store_results(year: str, cursor: mysql.connector.cursor.MySQLCursor):
    """
    Fetches all paginated results for a given year from the Contraloria search API.
    It first determines the total number of pages and then iterates through
    each one to collect all search hits.
    """
    print(f"--- Starting Contraloria Search API Scrape for year {year} ---")
    url = 'https://www.contraloria.cl/apibusca/search/dictamenes'

    headers = {
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://www.contraloria.cl',
        'Pragma': 'no-cache',
        'Referer': 'https://www.contraloria.cl/portalweb/web/cgr/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    # Note: Cookies are often session-specific and may expire.
    # For a robust script, you might need to fetch fresh cookies first.
    cookies = {
        'COOKIE_SUPPORT': 'true',
        'GUEST_LANGUAGE_ID': 'es_ES',
    }

    json_data = {
        'search': '',
        'exact_search': False,
        'options': [
            {
                "type": "force_obj",
                "field": "year_doc_id",
                "value": year,
                "inner_id": "av2"
            }
        ],
        'order': 'date',
        'date_name': 'fecha_documento',
        'source': 'dictamenes',
        'page': 0,
    }

    # --- 1. Make the first request to get total hits and the first page ---
    print("Fetching page 1 to determine total results...")
    response = requests.post(url, headers=headers, cookies=cookies, json=json_data, timeout=15)
    response.raise_for_status()

    response_data = response.json()
    hits_data = response_data.get('hits', {})
    
    # Safely get the total number of results
    total_value = hits_data.get('total', {}).get('value', 0)
    if total_value == 0:
        print("No results found. Exiting.")
        return # Exit for this year

    print(f"Total hits found: {total_value}")

    # The API returns a max of 20 results per page.
    results_per_page = 20
    num_pages = math.ceil(total_value / results_per_page)
    print(f"Calculated pages to fetch: {num_pages}\n")

    # --- 2. Loop through the remaining pages ---
    all_documents = []
    
    # Add results from the first page
    all_documents.extend(hits_data.get('hits', []))

    # Start loop from the second page (page index 1)
    for page_num in range(1, num_pages):
        print(f"Fetching page {page_num + 1} of {num_pages}...")
        json_data['page'] = page_num
        
        try:
            response = requests.post(url, headers=headers, cookies=cookies, json=json_data, timeout=15)
            response.raise_for_status()
            page_hits = response.json().get('hits', {}).get('hits', [])
            all_documents.extend(page_hits)
            time.sleep(0.5) # Be a good web citizen
        except requests.exceptions.RequestException as e:
            print(f"  -> Error fetching page {page_num + 1}: {e}")

    # --- 3. Process collected documents to extract required fields ---
    print("\n--- Processing collected documents ---")
    processed_documents = []
    source_keys_to_extract = [
        'carácter', 'documento_completo', 'complementado', 'is_accion',
        'destinatarios', 'reconsiderado_parcialmente', 'aplicado',
        'fuentes legales', 'confirmado', 'fecha_documento', 'reconsiderado',
        'relevante', 'descriptores', "origen_", "_tipo", "aclarado", "nuevo",
        "criterio", "materia", "recurso_proteccion", "boletin", "reactivado",
        "alterado"
    ]

    for doc in all_documents:
        processed_doc = {}

        # Extract top-level _id
        processed_doc['_id'] = doc.get('_id')

        # Extract specified fields from the nested _source object
        source_data = doc.get('_source', {})
        for key in source_keys_to_extract:
            value = source_data.get(key)
            # Clean the value if it's a string.
            if isinstance(value, str):
                # Trim whitespace for accurate comparison
                cleaned_value = value.strip()
                # Check for exact "SI" or "NO" for boolean conversion
                if cleaned_value.upper() == 'SI':
                    processed_doc[key] = True
                elif cleaned_value.upper() == 'NO':
                    processed_doc[key] = False
                elif cleaned_value.upper() == 'NP':
                    processed_doc[key] = False # Treat 'NP' as a typo for 'NO'
                else:
                    # If not a boolean, apply standard text cleaning for newlines/whitespace
                    processed_doc[key] = ' '.join(cleaned_value.split())
            else:
                # If it's not a string (e.g., a list or None), keep it as is.
                processed_doc[key] = value

        processed_documents.append(processed_doc)

    # --- 4. Insert data into the database ---
    print(f"--- Inserting/updating {len(processed_documents)} documents into the database ---")
    inserted_count = 0
    skipped_count = 0
    for doc in processed_documents:
        try:
            # Prepare for SQL: handle list types by converting them to JSON strings
            for key, value in doc.items():
                if isinstance(value, list):
                    doc[key] = json.dumps(value)

            columns = ', '.join(f'`{k}`' for k in doc.keys())
            placeholders = ', '.join(['%s'] * len(doc))
            insert_query = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"
            
            cursor.execute(insert_query, list(doc.values()))
            inserted_count += 1
        except mysql.connector.IntegrityError:
            # This error (1062, duplicate entry) is expected if the _id already exists.
            skipped_count += 1
        except Error as e:
            print(f"  -> Database error inserting doc {doc.get('_id', 'N/A')}: {e}")

    # --- 5. Final Output ---
    print(f"\n--- All pages scraped and processed for year {year} ---")
    print(f"Collected: {len(processed_documents)}. Inserted: {inserted_count}. Skipped: {skipped_count}.")

if __name__ == "__main__":
    connection = None
    cursor = None
    try:
        # --- Database Setup ---
        print(f"Connecting to database '{DB_CONFIG['database']}'...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        print(f"Ensuring table '{TABLE_NAME}' exists...")
        # Note: Using backticks for column names with special characters like `carácter`
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                `_id` VARCHAR(255) PRIMARY KEY,
                `carácter` VARCHAR(255), `documento_completo` TEXT, `complementado` BOOLEAN,
                `is_accion` TEXT, `destinatarios` TEXT, `reconsiderado_parcialmente` BOOLEAN,
                `aplicado` BOOLEAN, `fuentes legales` TEXT, `confirmado` BOOLEAN,
                `fecha_documento` VARCHAR(255), `reconsiderado` BOOLEAN, `relevante` VARCHAR(255),
                `descriptores` TEXT, `origen_` VARCHAR(255), `_tipo` VARCHAR(255),
                `aclarado` BOOLEAN, `nuevo` BOOLEAN, `criterio` TEXT, `materia` LONGTEXT,
                `recurso_proteccion` TEXT, `boletin` VARCHAR(255), `reactivado` BOOLEAN,
                `alterado` BOOLEAN,
                `scraped_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        print(f"Table '{TABLE_NAME}' is ready.")

        # Wipe the table before starting a new scrape
        print(f"Wiping all data from table '{TABLE_NAME}'...")
        cursor.execute(f"TRUNCATE TABLE {TABLE_NAME}")
        print("Table wiped.")

        start_year = 1949
        current_year = datetime.now().year
        print(f"--- Starting full scrape from {start_year} to {current_year} ---")

        for year_to_scrape in range(start_year, current_year + 1):
            fetch_and_store_results(year=str(year_to_scrape), cursor=cursor)
            connection.commit() # Commit transactions after each year is fully processed
            if year_to_scrape < current_year:
                print(f"\nFinished scraping for {year_to_scrape}. Waiting 5 seconds before next year...\n")
                time.sleep(5)

        print(f"\n--- Full scrape completed for all years. ---")

    except Error as e:
        print(f"A database error occurred: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("Database connection closed.")
