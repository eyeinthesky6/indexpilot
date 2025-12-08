"""Type stubs for src.db - Database connection helpers"""

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg2.connection import connection
else:
    # Runtime: use object to avoid import errors
    connection = object  # type: ignore[assignment, misc]

def get_connection(
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> AbstractContextManager["connection"]:
    """
    Context manager for database connections from pool.
    
    Returns:
        Context manager that yields a psycopg2 connection
    """
    ...
