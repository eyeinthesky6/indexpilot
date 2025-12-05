"""Database adapter detector and factory

This module provides the high-level adapter factory that uses low-level
type detection to create appropriate database adapters.
"""

import logging

from src.database.adapters.base import DatabaseAdapter
from src.database.adapters.postgresql import PostgreSQLAdapter
from src.database.type_detector import DATABASE_POSTGRESQL, detect_database_type

logger = logging.getLogger(__name__)

# Global adapter cache
_cached_adapter: DatabaseAdapter | None = None


def get_database_adapter(force_detect: bool = False) -> DatabaseAdapter:
    """
    Get appropriate database adapter for current database.

    Args:
        force_detect: Force re-detection even if adapter is cached

    Returns:
        DatabaseAdapter: Appropriate adapter for current database
    """
    global _cached_adapter

    if _cached_adapter is not None and not force_detect:
        return _cached_adapter

    # Detect database type
    db_type = detect_database_type()

    # Create appropriate adapter
    if db_type == DATABASE_POSTGRESQL:
        adapter = PostgreSQLAdapter()
    else:
        # Default to PostgreSQL for now (other adapters not yet implemented)
        logger.warning(
            f"Database type {db_type} not fully supported, using PostgreSQL adapter"
        )
        adapter = PostgreSQLAdapter()

    _cached_adapter = adapter
    logger.info(f"Using {adapter.get_database_type()} database adapter")

    return adapter

