"""Automatic retry logic for index creation failures"""

import logging
import time
from typing import Any

from src.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_retry_enabled() -> bool:
    """Check if automatic retry is enabled"""
    return _config_loader.get_bool("features.index_retry.enabled", True)


def get_retry_config() -> dict[str, Any]:
    """Get retry configuration"""
    return {
        "enabled": is_retry_enabled(),
        "max_retries": _config_loader.get_int("features.index_retry.max_retries", 3),
        "initial_delay_seconds": _config_loader.get_float(
            "features.index_retry.initial_delay_seconds", 5.0
        ),
        "max_delay_seconds": _config_loader.get_float(
            "features.index_retry.max_delay_seconds", 60.0
        ),
        "backoff_multiplier": _config_loader.get_float(
            "features.index_retry.backoff_multiplier", 2.0
        ),
        "retryable_errors": _config_loader.get_list(
            "features.index_retry.retryable_errors",
            [
                "timeout",
                "connection",
                "lock",
                "deadlock",
                "temporary",
                "resource",
            ],
        ),
    }


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.

    Args:
        error: Exception to check

    Returns:
        True if error is retryable
    """
    if not is_retry_enabled():
        return False

    error_str = str(error).lower()
    config = get_retry_config()
    retryable_keywords = config.get("retryable_errors", [])

    # Check if error message contains retryable keywords
    for keyword in retryable_keywords:
        if keyword in error_str:
            return True

    # Check for specific exception types
    error_type = type(error).__name__.lower()
    return bool(any(keyword in error_type for keyword in ["timeout", "connection", "lock"]))


def calculate_retry_delay(attempt: int, config: dict[str, Any] | None = None) -> float:
    """
    Calculate delay before retry using exponential backoff.

    Args:
        attempt: Retry attempt number (0-based)
        config: Retry configuration (optional)

    Returns:
        Delay in seconds
    """
    if config is None:
        config = get_retry_config()

    initial_delay = config.get("initial_delay_seconds", 5.0)
    max_delay = config.get("max_delay_seconds", 60.0)
    backoff = config.get("backoff_multiplier", 2.0)

    delay = initial_delay * (backoff**attempt)
    return min(delay, max_delay)


def retry_index_creation(
    create_func,
    table_name: str,
    field_name: str,
    *args,
    **kwargs,
) -> dict[str, Any]:
    """
    Retry index creation with exponential backoff.

    Args:
        create_func: Function that creates the index
        table_name: Table name
        field_name: Field name
        *args: Additional arguments for create_func
        **kwargs: Additional keyword arguments for create_func

    Returns:
        dict with creation result and retry information
    """
    if not is_retry_enabled():
        # If retry is disabled, just call the function once
        try:
            result = create_func(*args, **kwargs)
            return {
                "success": True,
                "result": result,
                "retries": 0,
                "total_attempts": 1,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "retries": 0,
                "total_attempts": 1,
            }

    config = get_retry_config()
    max_retries = config.get("max_retries", 3)
    last_error = None
    attempts = []

    for attempt_num in range(max_retries + 1):  # +1 for initial attempt
        try:
            start_time = time.time()
            result = create_func(*args, **kwargs)
            duration = time.time() - start_time

            attempts.append(
                {
                    "attempt": attempt_num + 1,
                    "success": True,
                    "duration_seconds": duration,
                }
            )

            if attempt_num > 0:
                logger.info(
                    f"Index creation succeeded on retry {attempt_num} "
                    f"for {table_name}.{field_name} after {attempt_num} failures"
                )

            return {
                "success": True,
                "result": result,
                "retries": attempt_num,
                "total_attempts": attempt_num + 1,
                "attempts": attempts,
            }

        except Exception as e:
            last_error = e
            duration = time.time() - start_time if "start_time" in locals() else 0

            attempts.append(
                {
                    "attempt": attempt_num + 1,
                    "success": False,
                    "error": str(e),
                    "duration_seconds": duration,
                }
            )

            # Check if error is retryable
            if not is_retryable_error(e):
                logger.warning(
                    f"Index creation failed with non-retryable error for {table_name}.{field_name}: {e}"
                )
                return {
                    "success": False,
                    "error": str(e),
                    "retries": attempt_num,
                    "total_attempts": attempt_num + 1,
                    "attempts": attempts,
                    "non_retryable": True,
                }

            # If this was the last attempt, don't wait
            if attempt_num >= max_retries:
                logger.error(
                    f"Index creation failed after {max_retries} retries "
                    f"for {table_name}.{field_name}: {e}"
                )
                break

            # Calculate delay and wait
            delay = calculate_retry_delay(attempt_num, config)
            logger.warning(
                f"Index creation failed for {table_name}.{field_name} "
                f"(attempt {attempt_num + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)

    # All retries exhausted
    return {
        "success": False,
        "error": str(last_error) if last_error else "Unknown error",
        "retries": max_retries,
        "total_attempts": max_retries + 1,
        "attempts": attempts,
    }


def get_retry_statistics() -> dict[str, Any]:
    """
    Get statistics on retry attempts.

    Returns:
        dict with retry statistics
    """
    # This would track retry statistics in a production system
    # For now, return empty stats
    return {
        "total_retries": 0,
        "successful_retries": 0,
        "failed_retries": 0,
        "average_retries_per_creation": 0.0,
    }
