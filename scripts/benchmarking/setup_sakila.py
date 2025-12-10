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

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import psycopg2  # noqa: E402

from src.db import get_db_config  # noqa: E402

DATASETS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarking"


def get_db_connection(dbname: str | None = None):
    """Get a database connection, optionally to a specific database"""
    config = get_db_config()
    if dbname:
        config = config.copy()
        config["database"] = dbname
    return psycopg2.connect(**config)


SAKILA_SQL = DATASETS_DIR / "sakila-complete.sql"
DB_NAME = "sakila_test"


def safe_print(text):
    """Print text safely handling unicode errors"""
    try:
        print(text)
    except UnicodeEncodeError:
        text = text.replace("✅", "[OK]").replace("⚠️", "[WARN]").replace("❌", "[ERROR]")
        print(text)

def download_sakila():
    """Download Sakila database if not present"""
    if SAKILA_ZIP.exists():
        safe_print(f"✅ Sakila archive found: {SAKILA_ZIP}")
        return True

    safe_print("⚠️  Sakila database not found. Please download manually:")
    print("   1. Visit: https://www.postgresqltutorial.com/postgresql-sample-database/")
    print("   2. Download 'dvdrental.zip'")
    print(f"   3. Save to: {SAKILA_ZIP}")
    return False


def extract_sakila():
    """Extract Sakila database"""
    if not SAKILA_ZIP.exists():
        return False

    print(f"Extracting {SAKILA_ZIP}...")
    with zipfile.ZipFile(SAKILA_ZIP, "r") as zip_ref:
        zip_ref.extractall(DATASETS_DIR)

    # Find the SQL file (could be dvdrental.sql or sakila-pg.sql)
    sql_files = list(DATASETS_DIR.rglob("*.sql"))
    if sql_files:
        safe_print(f"✅ Found SQL file: {sql_files[0]}")
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
        safe_print(f"✅ Database '{DB_NAME}' created")
    except Exception as e:
        safe_print(f"⚠️  Error creating database: {e}")
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
    env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "indexpilot")

    cmd = [
        "psql",
        "-h",
        os.getenv("DB_HOST", "localhost"),
        "-p",
        os.getenv("DB_PORT", "5432"),
        "-U",
        os.getenv("DB_USER", "indexpilot"),
        "-d",
        DB_NAME,
        "-f",
        str(sql_file),
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            safe_print("✅ SQL imported successfully")
            return True
        else:
            safe_print(f"⚠️  Import error: {result.stderr}")
            return False
    except FileNotFoundError:
        safe_print("⚠️  psql not found. Trying alternative method...")
        # Alternative: use Python to execute SQL
        return import_sql_python(sql_file)


def import_sql_python(sql_file):
    """Import SQL using Python (fallback)"""
    print("Using Python to import SQL...")
    conn = get_db_connection(dbname=DB_NAME)
    cursor = conn.cursor()

    try:
        with open(sql_file, encoding="utf-8") as f:
            sql_content = f.read()

        # Execute SQL (may need to split by semicolons)
        cursor.execute(sql_content)
        conn.commit()
        safe_print("✅ SQL imported successfully")
        return True
    except Exception as e:
        safe_print(f"⚠️  Import error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    """Main setup function"""
    print("=" * 60)
    print("Sakila Database Setup for IndexPilot")
    print("=" * 60)

    # Step 1: Check for SQL file
    sql_file = SAKILA_SQL
    if not sql_file.exists():
        safe_print("\n⚠️  Sakila SQL file not found. Please run download script first:")
        print("   bash scripts/benchmarking/download_datasets.sh")
        return 1

    safe_print(f"✅ Using SQL file: {sql_file}")

    # Step 2: Create database
    if not create_database():
        safe_print("\n⚠️  Failed to create database")
        return 1

    # Step 3: Import SQL
    if not import_sql(sql_file):
        safe_print("\n⚠️  Failed to import SQL")
        return 1

    print("\n" + "=" * 60)
    safe_print("✅ Sakila database setup complete!")
    print("=" * 60)
    print(f"\nDatabase: {DB_NAME}")
    print("\nNext steps:")
    print("  1. Create schema config: python scripts/create_sakila_config.py")
    print("  2. Run IndexPilot analysis: python -m src.auto_indexer")
    print("  3. See docs/testing/benchmarking/DATASET_SETUP.md for details")

    return 0


if __name__ == "__main__":
    sys.exit(main())
