"""Database connection helpers with connection pooling"""

import logging
import os
import threading
import time
from contextlib import contextmanager, suppress

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError

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
    supabase_url = os.getenv('SUPABASE_DB_URL')
    if supabase_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(supabase_url)

            config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:] if parsed.path.startswith('/') else parsed.path,  # Remove leading /
                'user': parsed.username,
                'password': parsed.password,
                'sslmode': 'require'  # Supabase requires SSL
            }

            logger.info("Using Supabase connection string")
            return config
        except Exception as e:
            logger.warning(f"Failed to parse Supabase connection string: {e}, falling back to individual env vars")

    # Fallback to individual environment variables
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'indexpilot')
    user = os.getenv('DB_USER', 'indexpilot')
    password = os.getenv('DB_PASSWORD')

    # Security: Require password in production (allow default only for development)
    is_production = os.getenv('ENVIRONMENT', '').lower() in ('production', 'prod')
    if is_production and not password:
        raise ValueError(
            "DB_PASSWORD environment variable is required in production. "
            "Never use hardcoded passwords."
        )

    # Use default only for development/testing
    if not password:
        password = 'indexpilot'  # Development default only
        logger.warning(
            "Using default password. Set DB_PASSWORD environment variable in production."
        )

    config = {
        'host': host,
        'port': port,
        'database': database,
        'user': user,
        'password': password,
    }

    # Enforce SSL in production
    if is_production:
        config['sslmode'] = 'require'
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
                _connection_pool = pool.ThreadedConnectionPool(
                    min_conn, max_conn, **config
                )
                logger.info(f"Connection pool initialized: {min_conn}-{max_conn} connections")
            except Exception as e:
                # Security: Don't log connection details that might contain credentials
                error_msg = str(e)
                # Redact potential credential information
                if 'password' in error_msg.lower() or 'credential' in error_msg.lower():
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
def get_connection(max_retries: int = 3, retry_delay: float = 0.1):
    """
    Context manager for database connections from pool.

    This function will use the database adapter if configured, which allows
    reusing host application's connection pool. Otherwise, it uses the internal pool.

    Args:
        max_retries: Maximum number of retries if connection fails
        retry_delay: Delay between retries in seconds
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
    for attempt in range(max_retries):
        try:
            conn = pool.getconn()
            if conn:
                # Check if connection is still alive (properly close cursor)
                try:
                    test_cursor = conn.cursor()
                    test_cursor.execute('SELECT 1')
                    test_cursor.close()
                except Exception:
                    # Connection is dead, close it and get a new one
                    with suppress(Exception):
                        pool.putconn(conn, close=True)
                    conn = pool.getconn()

                break
        except PoolError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                logger.warning(f"Connection pool exhausted, retrying ({attempt + 1}/{max_retries})...")
            else:
                logger.error(f"Failed to get connection from pool after {max_retries} attempts: {e}")
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
        error_msg = str(e)
        # Redact sensitive information patterns
        sensitive_patterns = ['password', 'credential', 'secret', 'token', 'key']
        if any(pattern in error_msg.lower() for pattern in sensitive_patterns):
            error_msg = "Database error (sensitive information redacted)"
        logger.error(f"Database error: {error_msg}")
        raise
    finally:
        if pool is not None and conn is not None:
            try:
                pool.putconn(conn)
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
            'min_conn': _connection_pool.minconn,
            'max_conn': _connection_pool.maxconn,
            'status': 'active'
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return None


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
