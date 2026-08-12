import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import pandas as pd
import zipfile
import requests
from datetime import datetime

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
GITHUB_CONFIG = {
    'token': os.getenv('GITHUB_TOKEN'),
    'repo': os.getenv('GITHUB_REPO')
}

DT_TABLE = 'dt'
CGR_TABLE = 'cgr'

def export_table_to_xlsx(connection: mysql.connector.MySQLConnection, table_name: str, file_path: str):
    """
    Selects all data from a table and exports it to an Excel (.xlsx) file.
    
    Args:
        connection: The active database connection object.
        table_name: The name of the table to export.
        file_path: The path for the output .xlsx file.
    """
    print(f"\nAttempting to export data from table '{table_name}' to '{file_path}'...")
    try:
        # Use pandas to read directly from the SQL query
        df = pd.read_sql(f"SELECT * FROM `{table_name}`", connection)
        
        # Export the DataFrame to an Excel file
        df.to_excel(file_path, index=False, engine='openpyxl')
            
        print(f"-> Success: Exported {len(df)} rows to {file_path}.")
        
    except (Error, pd.errors.EmptyDataError) as e:
        print(f"-> Error exporting table '{table_name}' to Excel: {e}")
    except ImportError:
        print("-> Error: The 'pandas' and 'openpyxl' libraries are required for Excel export.")
        print("-> Please install them using: pip install pandas openpyxl")

def export_table_to_sql(cursor: mysql.connector.cursor.MySQLCursor, table_name: str, file_path: str):
    """
    Selects all data from a table and exports it as SQL INSERT statements.
    
    Args:
        cursor: The database cursor object.
        table_name: The name of the table to export.
        file_path: The path for the output .sql file.
    """
    print(f"\nAttempting to export data from table '{table_name}' to '{file_path}'...")
    try:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        
        headers = [i[0] for i in cursor.description]
        rows = cursor.fetchall()

        with open(file_path, 'w', encoding='utf-8') as sqlfile:
            # Helper to format values for SQL statements
            def format_sql_value(value):
                if value is None:
                    return 'NULL'
                elif isinstance(value, (int, float)):
                    return str(value)
                else:
                    # Escape single quotes for SQL strings
                    escaped_value = str(value).replace("'", "''")
                    return f"'{escaped_value}'"

            # Write a header for clarity
            sqlfile.write(f"-- Data dump for table `{table_name}`\n")
            sqlfile.write(f"-- Total rows: {len(rows)}\n\n")

            if not rows:
                sqlfile.write(f"-- Table `{table_name}` is empty.\n")
                print(f"-> Success: Exported 0 rows to {file_path} (table is empty).")
                return

            # Create the base INSERT statement
            column_str = ', '.join([f"`{h}`" for h in headers])
            
            # Write an INSERT statement for each row
            for row in rows:
                values_str = ', '.join([format_sql_value(val) for val in row])
                sqlfile.write(f"INSERT INTO `{table_name}` ({column_str}) VALUES ({values_str});\n")

        print(f"-> Success: Exported {len(rows)} INSERT statements to {file_path}.")

    except Error as e:
        print(f"-> Error exporting table '{table_name}' to SQL: {e}")

def create_zip_archive(file_list: list, zip_path: str):
    """
    Creates a zip archive from a list of files and then deletes the original files.
    
    Args:
        file_list: A list of file paths to include in the archive.
        zip_path: The path for the output zip file.
    """
    print(f"\nCreating zip archive: '{zip_path}'...")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_list:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
                    print(f"  -> Added '{file_path}' to archive.")
                else:
                    print(f"  -> Warning: File not found, skipping: '{file_path}'")
        print(f"-> Success: Created '{zip_path}'.")
        return True
    except Exception as e:
        print(f"-> Error creating zip archive: {e}")
        return False
    finally:
        # Clean up the original files
        print("Cleaning up individual export files...")
        for file_path in file_list:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"  -> Removed '{file_path}'.")

def create_github_release(tag_name: str, release_name: str):
    """Creates a new release on GitHub and returns the upload URL for assets."""
    if not all(GITHUB_CONFIG.values()):
        print("-> GitHub token or repo not configured in .env file. Skipping release.")
        return None

    print(f"\nCreating GitHub release '{release_name}' with tag '{tag_name}'...")
    url = f"https://api.github.com/repos/{GITHUB_CONFIG['repo']}/releases"
    headers = {
        "Authorization": f"token {GITHUB_CONFIG['token']}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "tag_name": tag_name,
        "name": release_name,
        "body": f"Automated data export from {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "draft": False,
        "prerelease": False
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        release_data = response.json()
        print(f"-> Success: Created release. URL: {release_data['html_url']}")
        return release_data['upload_url']
    except requests.exceptions.RequestException as e:
        print(f"-> Error creating GitHub release: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")
        return None

def upload_release_asset(upload_url: str, file_path: str):
    """Uploads a file as an asset to a GitHub release."""
    print(f"Uploading asset '{os.path.basename(file_path)}' to release...")
    asset_name = os.path.basename(file_path)
    url = upload_url.split('{')[0] + f"?name={asset_name}"
    headers = {
        "Authorization": f"token {GITHUB_CONFIG['token']}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/zip"
    }
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        response = requests.post(url, headers=headers, data=data, timeout=60)
        response.raise_for_status()
        print(f"-> Success: Uploaded '{asset_name}'.")
    except requests.exceptions.RequestException as e:
        print(f"-> Error uploading asset: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")

def main():
    """
    Main function to connect to the database and trigger the export for each table.
    """
    connection = None
    zip_files_to_upload = []
    try:
        print(f"Connecting to database '{DB_CONFIG['database']}'...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        print("Database connection successful.")

        tables_to_process = [DT_TABLE, CGR_TABLE]
        for table in tables_to_process:
            print(f"\n--- Processing table: {table} ---")
            export_files = [f"{table}_export.xlsx", f"{table}_export.sql"]
            zip_path = f"{table}.zip"

            export_table_to_xlsx(connection, table, export_files[0])
            export_table_to_sql(cursor, table, export_files[1])

            if create_zip_archive(export_files, zip_path):
                zip_files_to_upload.append(zip_path)

        # --- Upload to GitHub ---
        if zip_files_to_upload:
            tag = datetime.now().strftime("data-export-%Y-%m-%d-%H%M%S")
            release_name = datetime.now().strftime("%Y.%m")
            upload_url = create_github_release(tag, release_name)

            if upload_url:
                for zip_file in zip_files_to_upload:
                    upload_release_asset(upload_url, zip_file)
                    os.remove(zip_file) # Clean up the local zip file after upload

    except Error as e:
        print(f"A database connection error occurred: {e}")
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("\nProcess finished. Database connection closed.")

if __name__ == "__main__":
    main()