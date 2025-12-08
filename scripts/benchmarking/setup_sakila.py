#!/usr/bin/env python3
"""
Setup Sakila database for IndexPilot testing
Date: 08-12-2025
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db import get_db_connection

DATASETS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarking"
SAKILA_ZIP = DATASETS_DIR / "sakila-pg.zip"
SAKILA_DIR = DATASETS_DIR / "sakila"
DB_NAME = "sakila_test"

def download_sakila():
    """Download Sakila database if not present"""
    if SAKILA_ZIP.exists():
        print(f"✅ Sakila archive found: {SAKILA_ZIP}")
        return True

    print("⚠️  Sakila database not found. Please download manually:")
    print("   1. Visit: https://www.postgresqltutorial.com/postgresql-sample-database/")
    print("   2. Download 'dvdrental.zip'")
    print(f"   3. Save to: {SAKILA_ZIP}")
    return False

def extract_sakila():
    """Extract Sakila database"""
    if not SAKILA_ZIP.exists():
        return False

    print(f"Extracting {SAKILA_ZIP}...")
    with zipfile.ZipFile(SAKILA_ZIP, 'r') as zip_ref:
        zip_ref.extractall(DATASETS_DIR)

    # Find the SQL file (could be dvdrental.sql or sakila-pg.sql)
    sql_files = list(DATASETS_DIR.rglob("*.sql"))
    if sql_files:
        print(f"✅ Found SQL file: {sql_files[0]}")
        return sql_files[0]

    return None

def create_database():
    """Create Sakila test database"""
    print(f"Creating database '{DB_NAME}'...")

    # Connect to postgres database to create new database
    conn = get_db_connection(dbname="postgres")
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Drop if exists
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"✅ Database '{DB_NAME}' created")
    except Exception as e:
        print(f"⚠️  Error creating database: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

    return True

def import_sql(sql_file):
    """Import SQL file into database"""
    print(f"Importing {sql_file} into {DB_NAME}...")

    # Use psql to import
    env = os.environ.copy()
    env['PGPASSWORD'] = os.getenv('DB_PASSWORD', 'indexpilot')

    cmd = [
        'psql',
        '-h', os.getenv('DB_HOST', 'localhost'),
        '-p', os.getenv('DB_PORT', '5432'),
        '-U', os.getenv('DB_USER', 'indexpilot'),
        '-d', DB_NAME,
        '-f', str(sql_file)
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ SQL imported successfully")
            return True
        else:
            print(f"⚠️  Import error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("⚠️  psql not found. Trying alternative method...")
        # Alternative: use Python to execute SQL
        return import_sql_python(sql_file)

def import_sql_python(sql_file):
    """Import SQL using Python (fallback)"""
    print("Using Python to import SQL...")
    conn = get_db_connection(dbname=DB_NAME)
    cursor = conn.cursor()

    try:
        with open(sql_file, encoding='utf-8') as f:
            sql_content = f.read()

        # Execute SQL (may need to split by semicolons)
        cursor.execute(sql_content)
        conn.commit()
        print("✅ SQL imported successfully")
        return True
    except Exception as e:
        print(f"⚠️  Import error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def main():
    """Main setup function"""
    print("=" * 60)
    print("Sakila Database Setup for IndexPilot")
    print("=" * 60)

    # Step 1: Download
    if not download_sakila():
        print("\n⚠️  Please download Sakila database manually and run again")
        return 1

    # Step 2: Extract
    sql_file = extract_sakila()
    if not sql_file:
        print("\n⚠️  Could not find SQL file in archive")
        return 1

    # Step 3: Create database
    if not create_database():
        print("\n⚠️  Failed to create database")
        return 1

    # Step 4: Import SQL
    if not import_sql(sql_file):
        print("\n⚠️  Failed to import SQL")
        return 1

    print("\n" + "=" * 60)
    print("✅ Sakila database setup complete!")
    print("=" * 60)
    print(f"\nDatabase: {DB_NAME}")
    print("\nNext steps:")
    print("  1. Create schema config: python scripts/create_sakila_config.py")
    print("  2. Run IndexPilot analysis: python -m src.auto_indexer")
    print("  3. See docs/testing/DATASET_SETUP.md for details")

    return 0

if __name__ == "__main__":
    sys.exit(main())

