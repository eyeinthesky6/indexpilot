"""Rate limiting to prevent abuse and DoS attacks"""

import logging
import threading
import time

from src.config_loader import ConfigLoader
from src.type_definitions import BoolFloatTuple, JSONDict

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


class RateLimiter:
    """
    Thread-safe rate limiter to prevent abuse.

    Implements token bucket algorithm for efficient rate limiting.
    """

    def __init__(self, max_requests: int = 100, time_window: float = 60.0):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.buckets: dict[str, tuple[float, int]] = {}  # key -> (reset_time, tokens)
        self.lock = threading.Lock()

    def is_allowed(self, key: str, cost: int = 1) -> BoolFloatTuple:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique identifier for rate limiting (e.g., tenant_id, IP address)
            cost: Cost of the request (default: 1)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        current_time = time.time()

        with self.lock:
            if key not in self.buckets:
                # Initialize bucket
                self.buckets[key] = (current_time + self.time_window, self.max_requests)

            reset_time, tokens = self.buckets[key]

            # Reset bucket if time window expired
            if current_time >= reset_time:
                reset_time = current_time + self.time_window
                tokens = self.max_requests

            # Check if enough tokens available
            if tokens >= cost:
                tokens -= cost
                self.buckets[key] = (reset_time, tokens)
                return True, 0.0
            else:
                # Rate limit exceeded
                retry_after = reset_time - current_time
                return False, retry_after

    def reset(self, key: str | None = None):
        """
        Reset rate limit for a key or all keys.

        Args:
            key: Key to reset (None = reset all)
        """
        with self.lock:
            if key is None:
                self.buckets.clear()
            elif key in self.buckets:
                del self.buckets[key]

    def get_stats(self, key: str) -> JSONDict:
        """
        Get rate limit statistics for a key.

        Args:
            key: Key to get stats for

        Returns:
            dict with remaining tokens, reset time, etc.
        """
        with self.lock:
            if key not in self.buckets:
                return {
                    'remaining': self.max_requests,
                    'reset_in': self.time_window,
                    'limit': self.max_requests
                }

            reset_time, tokens = self.buckets[key]
            current_time = time.time()

            if current_time >= reset_time:
                return {
                    'remaining': self.max_requests,
                    'reset_in': self.time_window,
                    'limit': self.max_requests
                }

            return {
                'remaining': tokens,
                'reset_in': reset_time - current_time,
                'limit': self.max_requests
            }


# Global rate limiters for different operations (loaded from config)
_query_rate_limiter = RateLimiter(
    max_requests=_config_loader.get_int('features.rate_limiter.query.max_requests', 1000),
    time_window=_config_loader.get_float('features.rate_limiter.query.time_window_seconds', 60.0)
)
_index_creation_limiter = RateLimiter(
    max_requests=_config_loader.get_int('features.rate_limiter.index_creation.max_requests', 10),
    time_window=_config_loader.get_float('features.rate_limiter.index_creation.time_window_seconds', 3600.0)
)
_connection_limiter = RateLimiter(
    max_requests=_config_loader.get_int('features.rate_limiter.connection.max_requests', 100),
    time_window=_config_loader.get_float('features.rate_limiter.connection.time_window_seconds', 60.0)
)


def check_query_rate_limit(tenant_id: str | None = None) -> tuple[bool, float]:
    """
    Check if query is allowed under rate limit.

    Args:
        tenant_id: Tenant ID for per-tenant rate limiting

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
    from src.audit import log_audit_event

    key = f"query:{tenant_id}" if tenant_id else "query:global"
    allowed, retry_after = _query_rate_limiter.is_allowed(key)

    # Log rate limit violations to audit trail
    if not allowed:
        log_audit_event(
            'RATE_LIMIT_EXCEEDED',
            tenant_id=int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
            details={
                'limit_type': 'query',
                'retry_after_seconds': retry_after,
                'key': key
            },
            severity='warning'
        )

    return allowed, retry_after


def check_index_creation_rate_limit(table_name: str) -> tuple[bool, float]:
    """
    Check if index creation is allowed under rate limit.

    Args:
        table_name: Table name for per-table rate limiting

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
    key = f"index:{table_name}"
    return _index_creation_limiter.is_allowed(key, cost=1)


def check_connection_rate_limit(identifier: str = "global") -> tuple[bool, float]:
    """
    Check if connection is allowed under rate limit.

    Args:
        identifier: Unique identifier (e.g., IP address, user ID)

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
    key = f"connection:{identifier}"
    return _connection_limiter.is_allowed(key)


def reset_rate_limits(operation: str | None = None):
    """
    Reset rate limits for an operation or all operations.

    Args:
        operation: Operation to reset ('query', 'index', 'connection', or None for all)
    """
    if operation == 'query':
        _query_rate_limiter.reset()
    elif operation == 'index':
        _index_creation_limiter.reset()
    elif operation == 'connection':
        _connection_limiter.reset()
    else:
        _query_rate_limiter.reset()
        _index_creation_limiter.reset()
        _connection_limiter.reset()

