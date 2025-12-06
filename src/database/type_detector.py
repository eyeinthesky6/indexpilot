"""Database type detection for multi-database support

This module provides low-level database type detection utilities.
It is used by the adapter factory (detector.py) and other modules that need
to know the database type for strategy selection.
"""

import logging

from src.db import get_connection

logger = logging.getLogger(__name__)

# Database types
DATABASE_POSTGRESQL = "postgresql"
DATABASE_MYSQL = "mysql"
DATABASE_SQLSERVER = "sqlserver"
DATABASE_SQLITE = "sqlite"
DATABASE_UNKNOWN = "unknown"


def detect_database_type() -> str:
    """
    Detect the database type from connection.

    Returns:
        str: Database type (postgresql, mysql, sqlserver, sqlite, unknown)
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Try PostgreSQL-specific query
                cursor.execute("SELECT version()")
                result = cursor.fetchone()
                if result and result[0]:
                    version = result[0].lower()
                    if "postgresql" in version or "postgres" in version:
                        return DATABASE_POSTGRESQL

                # Try MySQL-specific query
                cursor.execute("SELECT VERSION()")
                result = cursor.fetchone()
                if result and result[0]:
                    version = result[0].lower()
                    if "mysql" in version or "mariadb" in version:
                        return DATABASE_MYSQL

                # Try SQL Server-specific query
                cursor.execute("SELECT @@VERSION")
                result = cursor.fetchone()
                if result and result[0]:
                    version = result[0].lower()
                    if "microsoft sql server" in version or "sql server" in version:
                        return DATABASE_SQLSERVER

            except Exception:
                # Try SQLite
                try:
                    cursor.execute("SELECT sqlite_version()")
                    return DATABASE_SQLITE
                except Exception:
                    pass

            finally:
                cursor.close()

    except Exception as e:
        logger.warning(f"Could not detect database type: {e}")

    return DATABASE_UNKNOWN


def has_native_query_cache(database_type: str | None = None) -> bool:
    """
    Check if database has native query plan caching.

    Args:
        database_type: Database type (auto-detected if None)

    Returns:
        bool: True if database has good native caching
    """
    if database_type is None:
        database_type = detect_database_type()

    # PostgreSQL has excellent query plan caching
    if database_type == DATABASE_POSTGRESQL:
        return True

    # MySQL has query cache (deprecated in 8.0) and plan cache
    # MySQL 8.0+ has good plan caching, but not as robust as PostgreSQL
    if database_type == DATABASE_MYSQL:
        return True  # MySQL 8.0+ has plan cache

    # SQL Server has excellent plan cache
    if database_type == DATABASE_SQLSERVER:
        return True

    # SQLite has limited caching
    if database_type == DATABASE_SQLITE:
        return False  # SQLite has basic caching but not production-grade

    # Unknown - assume no good caching
    return False


def get_recommended_cache_strategy(database_type: str | None = None) -> str:
    """
    Get recommended caching strategy for database type.

    Args:
        database_type: Database type (auto-detected if None)

    Returns:
        str: 'native' (use database cache) or 'application' (use app cache)
    """
    if database_type is None:
        database_type = detect_database_type()

    # PostgreSQL: Use native cache (best)
    if database_type == DATABASE_POSTGRESQL:
        return "native"

    # MySQL 8.0+: Native cache is good, but application cache can help
    if database_type == DATABASE_MYSQL:
        return "hybrid"  # Can use both

    # SQL Server: Native cache is excellent
    if database_type == DATABASE_SQLSERVER:
        return "native"

    # SQLite: Application cache recommended
    if database_type == DATABASE_SQLITE:
        return "application"

    # Unknown: Use application cache as fallback
    return "application"


# Global cache for database type
_detected_database_type: str | None = None


def get_database_type() -> str:
    """Get cached database type (detects once)"""
    global _detected_database_type
    if _detected_database_type is None:
        _detected_database_type = detect_database_type()
        logger.info(f"Detected database type: {_detected_database_type}")
    return _detected_database_type
