import requests
from bs4 import BeautifulSoup
import time
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Database Configuration ---
# Credentials are loaded from the .env file.
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}
TABLE_NAME = 'dt'

# The URL of the page you want to scrape
URL = "https://www.dt.gob.cl/legislacion/1624/w3-propertyname-2310.html"

connection = None
cursor = None
try:
    # --- Database Setup ---
    print(f"Connecting to database '{DB_CONFIG['database']}'...")
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    # Create table if it doesn't exist. A UNIQUE constraint prevents duplicate URLs.
    print(f"Ensuring table '{TABLE_NAME}' exists...")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            url VARCHAR(2048) NOT NULL,            
            branch VARCHAR(255),
            epigrafe TEXT,
            titulo TEXT,
            fecha VARCHAR(255),
            abstract TEXT,
            hidden_text TEXT,
            body_text LONGTEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url(255))
        )
    """)

    # --- Schema Migration: Add columns if they don't exist ---
    # This prevents errors if the table was created by an older version of the script.
    print("Checking and updating table schema...")
    columns_to_add = {
        'branch': 'VARCHAR(255)', 'epigrafe': 'TEXT', 'titulo': 'TEXT',
        'fecha': 'VARCHAR(255)', 'abstract': 'TEXT', 'hidden_text': 'TEXT',
        'body_text': 'LONGTEXT'
    }
    for col_name, col_type in columns_to_add.items():
        try:
            cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col_name} {col_type}")
        except mysql.connector.Error as err:
            if err.errno != 1060: # 1060 is 'Duplicate column name'
                raise # Re-raise the error if it's not a duplicate column error
    print(f"Table '{TABLE_NAME}' is ready.")

    # Wipe the table before starting a new scrape
    print(f"Wiping all data from table '{TABLE_NAME}'...")
    cursor.execute(f"TRUNCATE TABLE {TABLE_NAME}")
    print("Table wiped.")

    # --- Main Scraping Logic ---
    print(f"\nFetching data from: {URL}")
    # Send an HTTP GET request to the URL
    # It's good practice to add a timeout
    response = requests.get(URL, timeout=10)

    # Raise an exception for bad status codes (4xx or 5xx)
    response.raise_for_status()

    # Parse the HTML content of the page with BeautifulSoup
    # 'lxml' is a very fast parser, but 'html.parser' is built-in
    soup = BeautifulSoup(response.content, "html.parser")

    print("Page content successfully loaded. Starting scrape...")

    # --- Scraping logic starts here ---

    # First, find the container div by its unique ID
    container_div = soup.find('div', id='i__w3_pc_SelectorAnios_normativa_1')

    if container_div:
        # Now, find the <ul> within that specific div
        item_list = container_div.find('ul')
        if item_list:
            # Find all <li> (list item) tags within the list
            list_items = item_list.find_all('li')
            print(f"\nFound {len(list_items)} items. Extracting links...")

            # Initialize an empty list to store the links
            extracted_links = []

            for item in list_items:
                # Find the <a> tag within the <li>
                link_tag = item.find('a')
                # Check if the <a> tag and its href attribute exist
                if link_tag and 'href' in link_tag.attrs:
                    relative_link = link_tag['href']
                    # Construct the absolute URL by joining the base URL with the relative link
                    absolute_link = requests.compat.urljoin(URL, relative_link)
                    extracted_links.append(absolute_link)

            print(f"Successfully saved {len(extracted_links)} links to the 'extracted_links' variable.")
            # You can now work with the list. For example, let's print the first 5 links:
            print(extracted_links[:5])

    else:
        print("Could not find the container div with id 'i__w3_pc_SelectorAnios_normativa_1'.")
        extracted_links = [] # Ensure the list exists even if scraping fails

    # --- Stage 2: Scrape the content from each extracted link ---

    if extracted_links:
        print("\n--- Starting to scrape individual pages ---")
        scraped_data = []
        final_document_links = []

        # Scrape all extracted links from the first stage
        for link_url in extracted_links:
            print(f"Scraping detail page: {link_url}")
            try:
                # Use the same request logic for the detail page
                detail_response = requests.get(link_url, timeout=10)
                detail_response.raise_for_status()

                detail_soup = BeautifulSoup(detail_response.content, "html.parser")

                # Find the main content div on the detail page
                content_div = detail_soup.find('div', id="i__w3_pa_SubValores_1")
                page_data = {'url': link_url, 'table_links': []}

                if content_div:
                    # Find all link tags within the table's container div
                    table_links = content_div.find_all('a', href=True)
                    
                    if table_links:
                        print(f"  -> Found {len(table_links)} links in the table.")
                        for link_tag in table_links:
                            relative_link = link_tag['href']
                            # Construct the absolute URL
                            absolute_link = requests.compat.urljoin(URL, relative_link)
                            # Add the link to the dictionary for this page
                            page_data['table_links'].append(absolute_link)
                        # Also, add all found links to our final master list
                        final_document_links.extend(page_data['table_links'])
                    else:
                        print("  -> No links found in the table.")

                else:
                    print("  -> Warning: Could not find div with id 'i__w3_pa_SubValores_1'.")
                
                scraped_data.append(page_data)

                # Be a good web citizen: wait a second between requests
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                print(f"  -> Error scraping {link_url}: {e}")

        print("\n--- All second-level scraping complete ---")
        print(f"Collected a total of {len(final_document_links)} final document URLs.")
        print("Here are the first 5:")
        print(final_document_links[:5])

    # --- Stage 3: Scrape the final document links from the third-level pages ---

    if final_document_links:
        print("\n--- Starting to scrape third-level pages for final links ---")
        all_final_links = []
        
        # Process all document links from the second stage
        for doc_url in final_document_links:
            print(f"Scraping final document page: {doc_url}")
            try:
                doc_response = requests.get(doc_url, timeout=10)
                doc_response.raise_for_status()

                doc_soup = BeautifulSoup(doc_response.content, "html.parser")

                # Find all <p> tags that include the class "titulo"
                title_paragraphs = doc_soup.find_all('p', class_='titulo')
                
                if title_paragraphs:
                    print(f"  -> Found {len(title_paragraphs)} title paragraph(s). Extracting hrefs...")
                    for p_tag in title_paragraphs:
                        link_tag = p_tag.find('a', href=True)
                        if link_tag:
                            final_href = requests.compat.urljoin(doc_url, link_tag['href'])
                            
                            # --- Scrape and print final page content for verification ---
                            print(f"    -> Scraping content from: {final_href}")
                            content_response = requests.get(final_href, timeout=10)
                            content_response.raise_for_status()
                            content_soup = BeautifulSoup(content_response.content, "html.parser")

                            # Find the div with the specified class
                            content_div = content_soup.find('div', id='article_i__w3_ar_ArticuloCompleto_presentacion_1')
                            
                            if content_div:
                                print("\n--- EXTRACTED DETAILS ---")
                                # Helper function to safely find and get text
                                def get_text_safely(parent, tag, **kwargs):
                                    element = parent.find(tag, **kwargs)
                                    return element.get_text(strip=True) if element else "Not Found"

                                # Scrape each requested parameter
                                data = {
                                    "branch": get_text_safely(content_div, 'span', class_='pv-branch'),
                                    "epigrafe": get_text_safely(content_div, 'p', class_='epigrafe'),
                                    "titulo": get_text_safely(content_div, 'h3', class_='titulo'),
                                    "fecha": get_text_safely(content_div, 'p', class_='fecha'),
                                    "abstract": get_text_safely(content_div, 'p', class_='abstract'),
                                    "hidden_text": get_text_safely(content_div, 'div', style='display:none'),
                                    "body_text": get_text_safely(content_soup, 'div', id='article_i__w3_ar_ArticuloCompleto_cuerpo_1')
                                }

                                # --- Insert structured data into MySQL ---
                                try:
                                    columns = ', '.join(data.keys())
                                    placeholders = ', '.join(['%s'] * len(data))
                                    # Add the URL to the query
                                    insert_query = f"INSERT INTO {TABLE_NAME} (url, {columns}) VALUES (%s, {placeholders})"
                                    
                                    # Prepare values tuple, ensuring order matches columns
                                    values_tuple = (final_href,) + tuple(data.values())
                                    
                                    cursor.execute(insert_query, values_tuple)
                                    connection.commit() # Commit after each successful insert
                                    print(f"    -> INSERTED: {final_href}")
                                except mysql.connector.IntegrityError:
                                    print(f"    -> SKIPPED (already exists): {final_href}") # No commit needed for skips
                            else:
                                print("      -> WARNING: Content div not found on this page.")
                            
                else:
                    print("  -> No '<p>' tags with class 'titulo' found on this page.")

                time.sleep(1) # Be polite
            except requests.exceptions.RequestException as e:
                print(f"  -> Error scraping {doc_url}: {e}")

        print(f"\n--- All scraping complete! ---")

except Error as e:
    print(f"A database error occurred: {e}")
except requests.exceptions.RequestException as e:
    print(f"A network error occurred: {e}")
finally:
    # Ensure the database connection is always closed
    if connection and connection.is_connected():
        cursor.close()
        connection.close()
        print("Database connection closed.")