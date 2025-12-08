"""Database connection helpers with connection pooling"""

import logging
import os
import threading
import time
from contextlib import contextmanager, suppress

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError

from src.type_definitions import JSONValue

logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()


def get_db_config():
    """
    Get database configuration from environment variables.

    Supports both:
    1. Supabase connection string (SUPABASE_DB_URL)
    2. Individual environment variables (DB_HOST, DB_PORT, etc.)

    Security: Requires DB_PASSWORD environment variable - no hardcoded defaults.
    In production, all credentials must be provided via environment variables.

    Returns:
        dict: Database configuration

    Raises:
        ValueError: If required credentials are missing
    """
    # Check for Supabase connection string first
    supabase_url = os.getenv("SUPABASE_DB_URL")
    if supabase_url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(supabase_url)

            config = {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": parsed.path[1:]
                if parsed.path.startswith("/")
                else parsed.path,  # Remove leading /
                "user": parsed.username,
                "password": parsed.password,
                "sslmode": "require",  # Supabase requires SSL
            }

            logger.info("Using Supabase connection string")
            return config
        except Exception as e:
            logger.warning(
                f"Failed to parse Supabase connection string: {e}, falling back to individual env vars"
            )

    # Fallback to individual environment variables
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "indexpilot")
    user = os.getenv("DB_USER", "indexpilot")
    password = os.getenv("DB_PASSWORD")

    # Security: Require password in production (allow default only for development)
    is_production = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    if is_production and not password:
        raise ValueError(
            "DB_PASSWORD environment variable is required in production. "
            "Never use hardcoded passwords."
        )

    # Use default only for development/testing
    if not password:
        password = "indexpilot"  # Development default only
        logger.warning(
            "Using default password. Set DB_PASSWORD environment variable in production."
        )

    config = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
    }

    # Enforce SSL in production
    if is_production:
        config["sslmode"] = "require"
        logger.info("SSL/TLS required for database connections in production")

    return config


def init_connection_pool(min_conn=2, max_conn=20):
    """
    Initialize the connection pool.

    Security: Enforces maximum connection limits to prevent DoS attacks.

    Note: For Supabase deployments, consider smaller pool sizes (1-5 connections)
    as Supabase provides connection pooling via PgBouncer.

    PostgreSQL's query plan cache is shared per connection, so connection pooling
    helps share cached plans across requests.

    Args:
        min_conn: Minimum number of connections in pool
        max_conn: Maximum number of connections in pool

    Raises:
        ValueError: If pool configuration is invalid
    """
    global _connection_pool

    # Validate pool configuration
    if min_conn < 1:
        raise ValueError(f"min_conn must be >= 1, got {min_conn}")
    if max_conn < min_conn:
        raise ValueError(f"max_conn ({max_conn}) must be >= min_conn ({min_conn})")
    if max_conn > 100:
        logger.warning(f"max_conn ({max_conn}) is very high, consider reducing for production")

    with _pool_lock:
        if _connection_pool is None:
            config = get_db_config()
            try:
                _connection_pool = pool.ThreadedConnectionPool(min_conn, max_conn, **config)
                logger.info(f"Connection pool initialized: {min_conn}-{max_conn} connections")
            except Exception as e:
                # Security: Don't log connection details that might contain credentials
                error_msg = str(e)
                # Redact potential credential information
                if "password" in error_msg.lower() or "credential" in error_msg.lower():
                    error_msg = "Connection failed (credentials redacted)"
                logger.error(f"Failed to initialize connection pool: {error_msg}")
                raise
        return _connection_pool


def get_connection_pool():
    """Get or initialize the connection pool"""
    global _connection_pool

    if _connection_pool is None:
        init_connection_pool()

    return _connection_pool


@contextmanager
def get_connection(
    max_retries: int = 3, retry_delay: float = 0.1, timeout_seconds: float | None = None
):
    """
    Context manager for database connections from pool.

    This function will use the database adapter if configured, which allows
    reusing host application's connection pool. Otherwise, it uses the internal pool.

    Args:
        max_retries: Maximum number of retries if connection fails
        retry_delay: Delay between retries in seconds
        timeout_seconds: Optional query timeout in seconds (uses query_timeout module if available)
    """
    # Try adapter first (if configured with host database)
    try:
        from src.adapters import get_host_database_adapter

        adapter = get_host_database_adapter()
        if adapter.use_host:
            # Use host database connection via adapter
            with adapter.get_connection() as conn:
                yield conn
            return
    except Exception as e:
        # Fallback to own pool if adapter fails
        logger.debug(f"Could not use database adapter: {e}, using own pool")

    # Fallback to own connection pool
    pool = get_connection_pool()
    conn = None
    last_error = None

    if pool is None:
        raise ConnectionError("Connection pool not initialized")

    # Check if shutdown is in progress - don't try to get connections during shutdown
    try:
        from src.graceful_shutdown import is_shutting_down

        if is_shutting_down():
            raise ConnectionError("Database connection unavailable: system is shutting down")
    except ImportError:
        # graceful_shutdown not available, continue
        pass

    for attempt in range(max_retries):
        try:
            conn = pool.getconn()
            if conn:
                # Check if connection is still alive (properly close cursor)
                try:
                    test_cursor = conn.cursor()
                    test_cursor.execute("SELECT 1")
                    test_cursor.close()
                except Exception:
                    # Connection is dead, close it and get a new one
                    with suppress(Exception):
                        pool.putconn(conn, close=True)
                    conn = pool.getconn()

                # Set query timeout if specified
                if timeout_seconds is not None:
                    try:
                        from src.query_timeout import set_connection_timeout

                        set_connection_timeout(conn, timeout_seconds=timeout_seconds)
                    except Exception as e:
                        logger.debug(
                            f"Could not set query timeout: {e}, continuing without timeout"
                        )

                break
        except PoolError as e:
            last_error = e
            error_str = str(e).lower()
            # Check if pool is closed (common error messages)
            if "closed" in error_str or "connection pool" in error_str:
                raise ConnectionError("Database connection pool is closed") from e
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                logger.warning(
                    f"Connection pool exhausted, retrying ({attempt + 1}/{max_retries})..."
                )
            else:
                logger.error(
                    f"Failed to get connection from pool after {max_retries} attempts: {e}"
                )
                raise ConnectionError(f"Database connection pool exhausted: {e}") from e
        except Exception:
            # Other error, re-raise immediately
            raise

    if conn is None:
        if last_error is not None:
            raise ConnectionError("Failed to get database connection") from last_error
        else:
            raise ConnectionError("Failed to get database connection")

    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Security: Sanitize error messages to prevent information leakage
        error_msg = str(e) if e else "Unknown error"
        error_type = type(e).__name__
        # Redact sensitive information patterns
        sensitive_patterns = ["password", "credential", "secret", "token", "key"]
        if any(pattern in error_msg.lower() for pattern in sensitive_patterns):
            error_msg = "Database error (sensitive information redacted)"
        # Log with error type for better debugging
        logger.error(f"Database error ({error_type}): {error_msg}")
        raise
    finally:
        if pool is not None and conn is not None:
            try:
                pool.putconn(conn)
            except PoolError as e:
                # Pool might be closed - just close the connection directly
                error_str = str(e).lower()
                if "closed" in error_str:
                    logger.debug("Connection pool is closed, closing connection directly")
                    with suppress(Exception):
                        conn.close()  # Connection already closed or invalid
                else:
                    logger.error(f"Error returning connection to pool: {e}")
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")


@contextmanager
def get_cursor():
    """Context manager for database cursors with dict-like results"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()


def get_pool_stats():
    """Get connection pool statistics"""
    if _connection_pool is None:
        return None

    try:
        # Get pool state (approximate)
        # Note: psycopg2.pool doesn't expose stats directly, so we estimate
        return {
            "min_conn": _connection_pool.minconn,
            "max_conn": _connection_pool.maxconn,
            "status": "active",
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return None


def safe_get_row_value(
    row: dict[str, JSONValue] | tuple[JSONValue, ...] | list[JSONValue] | None,
    key_or_index: str | int,
    default: JSONValue = None,
) -> JSONValue:
    """
    Safely extract a value from a database query result row.

    **REQUIRED**: Use this function instead of direct tuple index access (e.g., row[0]).
    This prevents "tuple index out of range" errors.

    Handles both dict (RealDictCursor) and tuple/list results safely.

    Args:
        row: Database query result row (dict, tuple, list, or None)
        key_or_index: For dict: key name (str). For tuple/list: index (int)
        default: Default value if key/index doesn't exist or row is None

    Returns:
        Value from row, or default if not found

    Examples:
        # With RealDictCursor (dict result)
        row = {"id": 1, "name": "test"}
        value = safe_get_row_value(row, "name", "")  # Returns "test"

        # With regular cursor (tuple result)
        row = (1, "test", 42)
        value = safe_get_row_value(row, 0, 0)  # Returns 1
        value = safe_get_row_value(row, 5, None)  # Returns None (index out of range)

        # With None/empty row
        value = safe_get_row_value(None, "name", "")  # Returns ""
    """
    if row is None:
        return default

    if isinstance(row, dict):
        # RealDictCursor result - use key lookup
        if isinstance(key_or_index, str):
            return row.get(key_or_index, default)
        else:
            # If key is int but row is dict, try to convert to string key
            return row.get(str(key_or_index), default)
    elif isinstance(row, tuple | list):
        # Regular cursor result - use index lookup with bounds checking
        if isinstance(key_or_index, int):
            if 0 <= key_or_index < len(row):
                return row[key_or_index]
            else:
                return default
        else:
            # If key is str but row is tuple/list, can't use string key
            return default


def safe_get_row_values(
    row: dict[str, JSONValue] | tuple[JSONValue, ...] | list[JSONValue] | None,
    *keys_or_indices: str | int,
    default: JSONValue = None,
) -> tuple[JSONValue, ...]:
    """
    Safely extract multiple values from a database query result row.

    Args:
        row: Database query result row
        *keys_or_indices: Multiple keys (for dict) or indices (for tuple/list)
        default: Default value for missing keys/indices

    Returns:
        Tuple of extracted values

    Example:
        row = {"id": 1, "name": "test", "age": 25}
        id_val, name_val = safe_get_row_values(row, "id", "name", default=0)
    """
    return tuple(safe_get_row_value(row, key_or_index, default) for key_or_index in keys_or_indices)


def close_connection_pool():
    """Close all connections in the pool"""
    global _connection_pool

    with _pool_lock:
        if _connection_pool:
            try:
                _connection_pool.closeall()
                logger.info("Connection pool closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}")
            finally:
                _connection_pool = None
