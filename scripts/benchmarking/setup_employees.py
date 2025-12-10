#!/usr/bin/env python3
"""
Setup Employees database for IndexPilot testing
Date: 08-12-2025
"""

import os
import subprocess
import sys
import tarfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import psycopg2  # noqa: E402

from src.db import get_db_config  # noqa: E402


def get_db_connection(dbname: str | None = None):
    """Get a database connection, optionally to a specific database"""
    config = get_db_config()
    if dbname:
        config = config.copy()
        config["database"] = dbname
    return psycopg2.connect(**config)


DATASETS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarking"
def safe_print(text):
    """Print text safely handling unicode errors"""
    try:
        print(text)
    except UnicodeEncodeError:
        text = text.replace("✅", "[OK]").replace("⚠️", "[WARN]").replace("❌", "[ERROR]")
        print(text)

EMPLOYEES_ARCHIVE = DATASETS_DIR / "employees_db.zip"
DB_NAME = "employees_test"


def download_employees():
    """Download Employees database if not present"""
    if EMPLOYEES_ARCHIVE.exists():
        safe_print(f"✅ Employees archive found: {EMPLOYEES_ARCHIVE}")
        return True

    safe_print("⚠️  Employees database not found. Please download manually:")
    print("   1. Visit: https://github.com/datacharmer/test_db")
    print("   2. Download zip")
    print(f"   3. Save to: {EMPLOYEES_ARCHIVE}")
    return False


def extract_employees():
    """Extract Employees database"""
    if not EMPLOYEES_ARCHIVE.exists():
        return None

    print(f"Extracting {EMPLOYEES_ARCHIVE}...")
    try:
        if str(EMPLOYEES_ARCHIVE).endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(EMPLOYEES_ARCHIVE, "r") as zip_ref:
                zip_ref.extractall(DATASETS_DIR)
        else:
             with tarfile.open(EMPLOYEES_ARCHIVE, "r:bz2") as tar:
                tar.extractall(DATASETS_DIR)

        # Find employees.sql file
        sql_file = DATASETS_DIR / "test_db-master" / "employees.sql"
        if not sql_file.exists():
            # Try alternative location
            sql_files = list(DATASETS_DIR.rglob("employees.sql"))
            if sql_files:
                sql_file = sql_files[0]
            else:
                safe_print("⚠️  Could not find employees.sql")
                return None

        safe_print(f"✅ Found SQL file: {sql_file}")
        return sql_file
    except Exception as e:
        safe_print(f"⚠️  Extraction error: {e}")
        return None


def create_database():
    """Create Employees test database"""
    print(f"Creating database '{DB_NAME}'...")

    conn = get_db_connection(dbname="postgres")
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        safe_print(f"✅ Database '{DB_NAME}' created")
        return True
    except Exception as e:
        safe_print(f"⚠️  Error creating database: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def import_sql(sql_file):
    """Import SQL file into database"""
    print(f"Importing {sql_file} into {DB_NAME}...")

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
        # Check if psql is available
        try:
             subprocess.run(["psql", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
             safe_print("⚠️  psql not found or error. Using Python import...")
             return import_sql_python(sql_file)

        # We need to change cwd to the directory of sql_file because it might source other files
        cwd = sql_file.parent

        result = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
        if result.returncode == 0:
            safe_print("✅ SQL imported successfully")
            return True
        else:
            safe_print(f"⚠️  Import error: {result.stderr}")
            # Try loading data files if they exist
            return import_data_files()
    except Exception as e:
        safe_print(f"⚠️  Import error: {e}")
        return import_sql_python(sql_file)


def import_data_files():
    """Import data files (employees_db has separate data files)"""
    data_dir = DATASETS_DIR / "test_db-master"
    load_sql = data_dir / "load_employees.dump"  # or similar

    if load_sql.exists():
        print("Found data load script, importing...")
        return import_sql(load_sql)

    print("⚠️  Data files not found. Database structure created but may be empty.")
    return True


def import_sql_python(sql_file):
    """Import SQL using Python (fallback)"""
    print("Using Python to import SQL...")
    conn = get_db_connection(dbname=DB_NAME)
    cursor = conn.cursor()

    try:
        with open(sql_file, encoding="utf-8") as f:
            sql_content = f.read()

        # Execute SQL
        cursor.execute(sql_content)
        conn.commit()
        print("✅ SQL imported successfully")
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
    print("Employees Database Setup for IndexPilot")
    print("=" * 60)

    # Step 1: Download
    if not download_employees():
        safe_print("\n⚠️  Please download Employees database manually and run again")
        return 1

    # Step 2: Extract
    sql_file = extract_employees()
    if not sql_file:
        safe_print("\n⚠️  Could not find SQL file")
        return 1

    # Step 3: Create database
    if not create_database():
        safe_print("\n⚠️  Failed to create database")
        return 1

    # Step 4: Import SQL
    if not import_sql(sql_file):
        safe_print("\n⚠️  Failed to import SQL")
        return 1

    print("\n" + "=" * 60)
    safe_print("✅ Employees database setup complete!")
    print("=" * 60)
    print(f"\nDatabase: {DB_NAME}")
    print("\nNext steps:")
    print("  1. Create schema config: python scripts/create_employees_config.py")
    print("  2. Run IndexPilot analysis")

    return 0


if __name__ == "__main__":
    sys.exit(main())
