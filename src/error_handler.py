"""Error handling with graceful degradation and audit trail"""

import logging
import traceback
from functools import wraps

from src.audit import log_audit_event
from src.monitoring import get_monitoring
from src.type_definitions import JSONValue

logger = logging.getLogger(__name__)


class IndexPilotError(Exception):
    """
    Base exception for IndexPilot errors.

    All custom exceptions in the IndexPilot system inherit from this class.
    """

    pass


class ConnectionError(IndexPilotError):
    """
    Connection-related errors.

    Raised when database connection operations fail, including:
    - Connection pool exhaustion
    - Connection timeout
    - Network errors
    - Authentication failures
    """

    pass


class IndexCreationError(IndexPilotError):
    """
    Index creation errors.

    Raised when index creation operations fail, including:
    - Lock acquisition failures
    - Index creation timeouts
    - Invalid index definitions
    - Resource constraints
    """

    pass


class QueryError(IndexPilotError):
    """
    Query execution errors.

    Raised when query execution fails, including:
    - SQL syntax errors
    - Query timeouts
    - Permission errors
    - Invalid parameters
    """

    pass


class QueryBlockedError(QueryError):
    """
    Query blocked by interceptor.

    Raised when a query is proactively blocked before execution because
    it was identified as harmful (e.g., expensive sequential scan, high cost).
    """

    def __init__(
        self, message: str, reason: str | None = None, details: dict[str, JSONValue] | None = None
    ):
        super().__init__(message)
        self.reason = reason
        self.details = details or {}


def handle_errors(operation_name, default_return=None, log_error=True):
    """
    Decorator for error handling with graceful degradation.

    Args:
        operation_name: Name of the operation for logging
        default_return: Value to return on error (None = raise exception)
        log_error: Whether to log errors
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ConnectionError as e:
                if log_error:
                    # Security: Don't log full error details that might contain credentials
                    error_msg = str(e)
                    # Remove potential credential leakage
                    if "password" in error_msg.lower() or "credential" in error_msg.lower():
                        error_msg = "Connection error (credentials redacted)"
                    logger.error(f"{operation_name} failed: Connection error - {error_msg}")

                # Send to host error tracker via adapter (if configured)
                try:
                    from src.adapters import get_error_handler_adapter

                    adapter = get_error_handler_adapter()
                    adapter.capture_exception(
                        e,
                        tags={"operation": operation_name, "error_type": "ConnectionError"},
                        extra={"error_msg": error_msg},
                    )
                except Exception:
                    # Don't fail if adapter not available or fails
                    pass

                # Log to audit trail
                log_audit_event(
                    "CONNECTION_ERROR",
                    details={
                        "operation": operation_name,
                        "error_type": "ConnectionError",
                        "message": error_msg,
                    },
                    severity="critical",
                )

                monitoring = get_monitoring()
                # Security: Sanitize alert messages
                monitoring.alert("critical", f"Database connection error in {operation_name}")

                if default_return is not None:
                    return default_return
                raise
            except IndexCreationError as e:
                if log_error:
                    # Enhanced error message with context
                    error_msg = str(e)
                    error_type = "IndexCreationError"
                    
                    # Provide more specific error messages based on error content
                    if "lock" in error_msg.lower():
                        detailed_msg = f"Index creation failed: Could not acquire lock. {error_msg}"
                        error_type = "IndexCreationError.LockAcquisitionFailed"
                    elif "timeout" in error_msg.lower():
                        detailed_msg = f"Index creation failed: Operation timed out. {error_msg}"
                        error_type = "IndexCreationError.Timeout"
                    elif "duplicate" in error_msg.lower() or "already exists" in error_msg.lower():
                        detailed_msg = f"Index creation failed: Index already exists. {error_msg}"
                        error_type = "IndexCreationError.DuplicateIndex"
                    elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
                        detailed_msg = f"Index creation failed: Permission denied. {error_msg}"
                        error_type = "IndexCreationError.PermissionDenied"
                    else:
                        detailed_msg = f"Index creation failed: {error_msg}"
                    
                    logger.error(f"{operation_name} failed: {detailed_msg}")

                # Send to host error tracker via adapter (if configured)
                try:
                    from src.adapters import get_error_handler_adapter

                    adapter = get_error_handler_adapter()
                    adapter.capture_exception(
                        e, tags={"operation": operation_name, "error_type": error_type}
                    )
                except Exception:
                    # Don't fail if adapter not available or fails
                    pass

                # Log to audit trail
                log_audit_event(
                    "INDEX_CREATION_FAILED",
                    details={
                        "operation": operation_name,
                        "error_type": error_type,
                        "message": detailed_msg if log_error else str(e),
                    },
                    severity="error",
                )

                monitoring = get_monitoring()
                monitoring.alert("warning", f"Index creation failed in {operation_name}: {detailed_msg if log_error else str(e)}")

                if default_return is not None:
                    return default_return
                raise
            except Exception as e:
                if log_error:
                    logger.error(f"{operation_name} failed: {type(e).__name__} - {e}")
                    logger.debug(traceback.format_exc())

                # Send to host error tracker via adapter (if configured)
                try:
                    from src.adapters import get_error_handler_adapter

                    adapter = get_error_handler_adapter()
                    adapter.capture_exception(
                        e, tags={"operation": operation_name, "error_type": type(e).__name__}
                    )
                except Exception:
                    # Don't fail if adapter not available or fails
                    pass

                monitoring = get_monitoring()
                monitoring.record_metric("error_rate", 1.0)
                monitoring.alert("warning", f"Unexpected error in {operation_name}: {e}")

                if default_return is not None:
                    return default_return
                raise

        return wrapper

    return decorator


def safe_execute(operation, *args, default_return=None, **kwargs):
    """
    Safely execute an operation with error handling.

    Args:
        operation: Function to execute
        *args: Positional arguments
        default_return: Value to return on error
        **kwargs: Keyword arguments
    """
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        logger.error(f"Operation {operation.__name__} failed: {e}")
        monitoring = get_monitoring()
        monitoring.record_metric("error_rate", 1.0)

        if default_return is not None:
            return default_return
        raise


class GracefulDegradation:
    """Context manager for graceful degradation"""

    def __init__(self, operation_name, fallback_func=None):
        self.operation_name = operation_name
        self.fallback_func = fallback_func
        self.error_occurred = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_occurred = True
            logger.warning(f"{self.operation_name} failed, attempting graceful degradation")

            if self.fallback_func:
                try:
                    return self.fallback_func()
                except Exception as e:
                    logger.error(f"Fallback for {self.operation_name} also failed: {e}")

            # Don't suppress the exception, just log it
            return False

        return False
