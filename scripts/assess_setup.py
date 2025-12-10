#!/usr/bin/env python3
"""
IndexPilot Setup Assessment Tool

Assesses the current state of the host codebase and guides users through
first-run setup, especially when multiple databases are detected.

Usage:
    python scripts/assess_setup.py
    python scripts/assess_setup.py --interactive
"""

import os
import sys
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def get_db_config_from_env() -> dict[str, Any] | None:
    """Get database configuration from environment variables."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")

    # Check for connection string
    supabase_url = os.getenv("SUPABASE_DB_URL")
    if supabase_url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(supabase_url)
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path[1:] if parsed.path.startswith("/") else parsed.path,
                "user": parsed.username or user,
                "password": parsed.password or password,
            }
        except Exception:
            pass

    indexpilot_url = os.getenv("INDEXPILOT_DATABASE_URL")
    if indexpilot_url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(indexpilot_url)
            return {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path[1:] if parsed.path.startswith("/") else parsed.path,
                "user": parsed.username or user,
                "password": parsed.password or password,
            }
        except Exception:
            pass

    if not database:
        return None

    return {
        "host": host,
        "port": int(port) if port.isdigit() else 5432,
        "database": database,
        "user": user,
        "password": password or "",
    }


def list_databases(host: str, port: int, user: str, password: str) -> list[dict[str, Any]]:
    """List all databases on the PostgreSQL server."""
    try:
        # Connect to postgres database to list all databases
        conn = psycopg2.connect(
            host=host,
            port=port,
            database="postgres",  # Connect to default database to list others
            user=user,
            password=password,
            connect_timeout=5,
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get list of databases (excluding system databases)
        cursor.execute(
            """
            SELECT 
                datname as name,
                pg_size_pretty(pg_database_size(datname)) as size,
                datacl as permissions
            FROM pg_database
            WHERE datistemplate = false
            ORDER BY datname
        """
        )
        databases = cursor.fetchall()

        cursor.close()
        conn.close()

        return [dict(db) for db in databases]
    except Exception as e:
        # Silently fail - will be handled by caller
        return []


def check_connection(config: dict[str, Any]) -> tuple[bool, str]:
    """Test database connection."""
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=5,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return True, str(version)
    except psycopg2.OperationalError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def check_indexpilot_initialized(config: dict[str, Any]) -> dict[str, Any]:
    """Check if IndexPilot metadata tables exist."""
    result = {
        "connected": False,
        "metadata_tables_exist": False,
        "genome_catalog_bootstrapped": False,
        "schema_discovered": False,
        "tables": [],
        "metadata_tables": [],
    }

    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=5,
        )
        result["connected"] = True
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check for IndexPilot metadata tables
        metadata_tables = {
            "genome_catalog",
            "expression_profile",
            "mutation_log",
            "query_stats",
        }

        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        )
        all_tables = [row["table_name"] for row in cursor.fetchall()]
        result["tables"] = all_tables

        found_metadata = [t for t in all_tables if t in metadata_tables]
        result["metadata_tables"] = found_metadata
        result["metadata_tables_exist"] = len(found_metadata) > 0

        # Check if genome_catalog has data (bootstrapped)
        if "genome_catalog" in found_metadata:
            cursor.execute("SELECT COUNT(*) as count FROM genome_catalog")
            count = cursor.fetchone()["count"]
            result["genome_catalog_bootstrapped"] = count > 0

        # Check if there are business tables (schema discovered)
        business_tables = [
            t
            for t in all_tables
            if t not in metadata_tables and not t.startswith("pg_")
        ]
        result["schema_discovered"] = len(business_tables) > 0

        cursor.close()
        conn.close()
    except Exception as e:
        result["error"] = str(e)

    return result


def print_assessment(config: dict[str, Any] | None, interactive: bool = False):
    """Print assessment of current setup."""
    print("\n" + "=" * 80)
    print("IndexPilot Setup Assessment")
    print("=" * 80 + "\n")

    # Check environment configuration
    print("1. Environment Configuration:")
    if config:
        print(f"   [OK] Database configured:")
        print(f"      Host: {config['host']}")
        print(f"      Port: {config['port']}")
        print(f"      Database: {config['database']}")
        print(f"      User: {config['user']}")
    else:
        print("   [WARN] No database configured in environment variables")
        print("      Set DB_NAME, DB_HOST, DB_USER, DB_PASSWORD")
        print("      Or set INDEXPILOT_DATABASE_URL or SUPABASE_DB_URL")
        return

    # Test connection
    print("\n2. Database Connection:")
    connected, message = check_connection(config)
    if connected:
        print(f"   [OK] Connected successfully")
        print(f"      {message[:60]}...")
    else:
        print(f"   [ERROR] Connection failed: {message}")
        print("\n   Troubleshooting:")
        print("   - Check if PostgreSQL is running")
        print("   - Verify DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        print("   - Check firewall/network settings")
        return

    # List databases if interactive
    if interactive:
        print("\n3. Available Databases:")
        try:
            databases = list_databases(config["host"], config["port"], config["user"], config["password"])
            if databases:
                print(f"   Found {len(databases)} database(s):")
                for db in databases:
                    marker = " <- CURRENT" if db["name"] == config["database"] else ""
                    size = db.get("size", "unknown")
                    print(f"      - {db['name']} ({size}){marker}")
            else:
                print("   [WARN] Could not list databases")
        except Exception as e:
            print(f"   [WARN] Could not list databases: {e}")

    # Check IndexPilot initialization
    print("\n4. IndexPilot Initialization Status:")
    status = check_indexpilot_initialized(config)

    if status["metadata_tables_exist"]:
        print("   [OK] Metadata tables exist")
        print(f"      Found: {', '.join(status['metadata_tables'])}")
    else:
        print("   [WARN] Metadata tables not found")
        print("      IndexPilot metadata tables need to be created")

    if status.get("genome_catalog_bootstrapped"):
        print("   [OK] Genome catalog bootstrapped")
    else:
        print("   [WARN] Genome catalog not bootstrapped")
        print("      Schema needs to be discovered and genome catalog initialized")

    if status.get("schema_discovered"):
        business_tables = [
            t for t in status["tables"] if t not in status["metadata_tables"] and not t.startswith("pg_")
        ]
        print(f"   [OK] Business schema found ({len(business_tables)} tables)")
        print(f"      Tables: {', '.join(business_tables[:10])}")
        if len(business_tables) > 10:
            print(f"      ... and {len(business_tables) - 10} more")
    else:
        print("   [WARN] No business tables found")
        print("      Database appears empty or schema not discovered")

    # Recommendations
    print("\n5. Recommendations:")
    needs_init = not status["metadata_tables_exist"]
    needs_bootstrap = not status.get("genome_catalog_bootstrapped", False)
    needs_schema = not status.get("schema_discovered", False)

    if needs_init:
        print("   [ACTION] Run schema initialization:")
        print("      python -c \"from src.schema import init_schema; init_schema()\"")

    if needs_bootstrap:
        if needs_schema:
            print("   [ACTION] Discover schema and bootstrap genome catalog:")
            print("      python -c \"from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()\"")
        else:
            print("   [ACTION] Bootstrap genome catalog from existing schema:")
            print("      python -c \"from src.genome import bootstrap_genome_catalog; bootstrap_genome_catalog()\"")

    if not needs_init and not needs_bootstrap and not needs_schema:
        print("   [OK] IndexPilot is fully initialized and ready to use!")
        print("\n   Next steps:")
        print("   - Run in advisory mode: python -c \"from src.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()\"")
        print("   - Check mutation_log for candidate indexes")
        print("   - Set INDEXPILOT_AUTO_INDEXER_MODE=apply to enable index creation")

    print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Assess IndexPilot setup status")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode: list available databases",
    )
    args = parser.parse_args()

    config = get_db_config_from_env()
    print_assessment(config, interactive=args.interactive)


if __name__ == "__main__":
    main()

