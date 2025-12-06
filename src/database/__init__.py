"""Database abstraction layer for IndexPilot"""

from src.database.adapters.base import DatabaseAdapter
from src.database.adapters.postgresql import PostgreSQLAdapter
from src.database.detector import get_database_adapter
from src.database.type_detector import (
    DATABASE_MYSQL,
    DATABASE_POSTGRESQL,
    DATABASE_SQLITE,
    DATABASE_SQLSERVER,
    DATABASE_UNKNOWN,
    detect_database_type,
    get_database_type,
    get_recommended_cache_strategy,
    has_native_query_cache,
)

__all__ = [
    "DatabaseAdapter",
    "PostgreSQLAdapter",
    "get_database_adapter",
    "detect_database_type",
    "get_database_type",
    "has_native_query_cache",
    "get_recommended_cache_strategy",
    "DATABASE_POSTGRESQL",
    "DATABASE_MYSQL",
    "DATABASE_SQLSERVER",
    "DATABASE_SQLITE",
    "DATABASE_UNKNOWN",
]
