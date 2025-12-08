"""Type stubs for src.db - Database connection helpers"""

from collections.abc import Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg2.connection import connection
else:
    # Runtime: use object to avoid import errors
    connection = object  # type: ignore[assignment, misc]

def get_connection(
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> Generator["connection", None, None]:
    """
    Context manager for database connections from pool.
    
    Returns:
        Generator that yields a psycopg2 connection (used as context manager)
    """
    ...
