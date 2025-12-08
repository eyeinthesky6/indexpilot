"""
Query timeout management with security validation.

NOTE: This module is reserved for future use. Currently not integrated into the codebase.
Functions are available but not called anywhere. To use, import and call:
    from src.query_timeout import query_timeout, set_connection_timeout
"""

import logging
from contextlib import contextmanager

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.production_config import get_config
from src.validation import validate_numeric_input

logger = logging.getLogger(__name__)

# Security bounds (correctly hardcoded to prevent DoS)
MAX_TIMEOUT_SECONDS = 3600  # 1 hour maximum
MIN_TIMEOUT_SECONDS = 0.1  # 100ms minimum

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def _get_default_query_timeout() -> float:
    """Get default query timeout from config or production_config or default"""
    # Try config file first
    timeout = _config_loader.get_float("features.query_timeout.default_query_timeout_seconds", 0.0)
    if timeout > 0:
        return timeout
    # Fall back to production_config
    prod_config = get_config()
    timeout = prod_config.get_float("QUERY_TIMEOUT", 30.0)
    return timeout


def _get_default_statement_timeout() -> float:
    """Get default statement timeout from config or default"""
    return _config_loader.get_float("features.query_timeout.default_statement_timeout_seconds", 60.0)


@contextmanager
def query_timeout(timeout_seconds=None):
    """
    Context manager to set query timeout for a connection.

    Args:
        timeout_seconds: Timeout in seconds (validated and clamped to safe range). If None, uses config default.
    """
    if timeout_seconds is None:
        timeout_seconds = _get_default_query_timeout()
    # Validate and sanitize timeout value
    timeout_ms = validate_numeric_input(
        timeout_seconds * 1000,
        min_value=MIN_TIMEOUT_SECONDS * 1000,
        max_value=MAX_TIMEOUT_SECONDS * 1000,
        default_value=int(_get_default_query_timeout() * 1000),
    )

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Use parameterized query to prevent SQL injection
            # PostgreSQL SET statement_timeout accepts integer milliseconds
            cursor.execute("SET statement_timeout = %s", (int(timeout_ms),))
            conn.commit()
            yield conn
        except Exception as e:
            logger.error(f"Query timeout error: {type(e).__name__}")
            raise
        finally:
            try:
                # Reset timeout
                cursor.execute("SET statement_timeout = DEFAULT")
                conn.commit()
            except Exception:
                pass
            finally:
                cursor.close()


def set_connection_timeout(conn, timeout_seconds=None):
    """
    Set timeout for a connection.

    Args:
        conn: Database connection
        timeout_seconds: Timeout in seconds (validated and clamped to safe range). If None, uses config default.
    """
    if timeout_seconds is None:
        timeout_seconds = _get_default_statement_timeout()
    # Validate and sanitize timeout value
    timeout_ms = validate_numeric_input(
        timeout_seconds * 1000,
        min_value=MIN_TIMEOUT_SECONDS * 1000,
        max_value=MAX_TIMEOUT_SECONDS * 1000,
        default_value=int(_get_default_statement_timeout() * 1000),
    )

    cursor = conn.cursor()
    try:
        # Use parameterized query to prevent SQL injection
        cursor.execute("SET statement_timeout = %s", (int(timeout_ms),))
        conn.commit()
    finally:
        cursor.close()
