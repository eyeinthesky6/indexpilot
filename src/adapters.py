"""
Utility adapters for host codebase integration.

This module provides adapters that allow IndexPilot to integrate with
host application utilities (monitoring, database, audit, logging, error handling)
while maintaining backward compatibility with internal utilities.

QUICK START:
    from src.adapters import configure_adapters
    import datadog
    import sentry_sdk

    configure_adapters(
        monitoring=datadog.statsd,      # Host monitoring (CRITICAL for production)
        database=host_db_pool,          # Host database connection pool
        error_tracker=sentry_sdk        # Host error tracking
    )

WHY USE ADAPTERS?
    - ⚠️ CRITICAL: Internal monitoring loses alerts on restart
    - 💰 Efficiency: Reuse host database connections
    - 📊 Observability: Unified monitoring and error tracking
    - ✅ Compliance: Unified audit trail

FULL DOCUMENTATION:
    See docs/ADAPTERS_USAGE_GUIDE.md for complete integration guide.

BACKWARD COMPATIBILITY:
    All adapters are optional. System works without any adapters configured.
"""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Thread safety for global adapter instances
_adapter_lock = threading.Lock()

# Fallback metrics tracking
_fallback_metrics: dict[str, int] = {}
_fallback_metrics_lock = threading.Lock()


@runtime_checkable
class MonitoringProtocol(Protocol):
    """Protocol for monitoring implementations"""

    def alert(self, level: str, message: str, **kwargs: Any) -> None:
        ...

    def event(self, title: str, text: str, alert_type: str, **kwargs: Any) -> None:
        ...

    def gauge(self, metric_name: str, value: float, **kwargs: Any) -> None:
        ...

    def record(
        self, metric_name: str, value: float, timestamp: float | None, **kwargs: Any
    ) -> None:
        ...

    def inc(self, metric_name: str, **kwargs: Any) -> None:
        ...


@runtime_checkable
class DatabasePoolProtocol(Protocol):
    """Protocol for database connection pool implementations"""

    def get_connection(self) -> Any:
        ...

    def getconn(self) -> Any:
        ...

    def putconn(self, conn: Any) -> None:
        ...


@runtime_checkable
class AuditProtocol(Protocol):
    """Protocol for audit system implementations"""

    def log(self, event_type: str, **kwargs: Any) -> None:
        ...

    def log_event(self, event_type: str, **kwargs: Any) -> None:
        ...


@runtime_checkable
class ErrorTrackerProtocol(Protocol):
    """Protocol for error tracking implementations"""

    def capture_exception(self, exception: Exception, **kwargs: Any) -> None:
        ...

    def capture_message(self, message: str, level: str, **kwargs: Any) -> None:
        ...

    def report_exc_info(
        self,
        exc_info: tuple[type[BaseException] | None, BaseException | None, Any] | None,
        **kwargs: Any,
    ) -> None:
        ...


def _record_fallback(adapter_name: str) -> None:
    """Record adapter fallback usage for metrics"""
    with _fallback_metrics_lock:
        _fallback_metrics[adapter_name] = _fallback_metrics.get(adapter_name, 0) + 1


def _get_fallback_metrics() -> dict[str, int]:
    """Get fallback metrics"""
    with _fallback_metrics_lock:
        return _fallback_metrics.copy()


def _reset_fallback_metrics() -> None:
    """Reset fallback metrics (for testing)"""
    with _fallback_metrics_lock:
        _fallback_metrics.clear()


class UtilityAdapter:
    """Base adapter class for host utilities"""

    def __init__(self, host_impl: Any = None):
        """
        Initialize adapter.

        Args:
            host_impl: Host implementation (optional) - can be any third-party object
        """
        self.host_impl = host_impl
        self.use_host = host_impl is not None

    def is_healthy(self) -> bool:
        """
        Check if adapter is working correctly.

        Returns:
            bool: True if adapter is healthy, False otherwise
        """
        if not self.use_host:
            return True  # Internal adapter always works
        return self.host_impl is not None


class MonitoringAdapter(UtilityAdapter):
    """
    Adapter for monitoring systems.

    CRITICAL: This adapter is required for production deployments to prevent
    alert loss. In-memory monitoring loses alerts on restart.

    Supports:
    - Datadog, Prometheus, New Relic, etc.
    - Custom monitoring implementations
    """

    def alert(
        self,
        level: str,
        message: str,
        metric: str | None = None,
        value: float | None = None,
        **kwargs: Any,
    ):
        """
        Send an alert.

        Args:
            level: Alert level ('info', 'warning', 'error', 'critical')
            message: Alert message
            metric: Optional metric name
            value: Optional metric value
            **kwargs: Additional alert metadata
        """
        # Always send to host monitoring if available
        if self.use_host and self.host_impl is not None:
            try:
                # Try standard interface
                if hasattr(self.host_impl, "alert"):
                    self.host_impl.alert(level, message, metric=metric, value=value, **kwargs)
                    return
                # Try Datadog-style interface
                elif hasattr(self.host_impl, "event"):
                    self.host_impl.event(
                        title=message,
                        text=f"Metric: {metric}, Value: {value}" if metric else message,
                        alert_type=level,
                        **kwargs,
                    )
                    return
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(level, message, metric=metric, value=value, **kwargs)
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host monitoring implementation doesn't match expected interface. "
                        f"Expected: alert() or event() method, or callable. "
                        f"Got: {type(self.host_impl).__name__} with methods: "
                        f"{[m for m in dir(self.host_impl) if not m.startswith('_')]}"
                    )
            except Exception as e:
                logger.error(f"Failed to send alert to host monitoring: {e}")
                _record_fallback("monitoring.alert")
        else:
            # Log warning if no host monitoring in production
            is_production = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
            if is_production:
                logger.warning(
                    f"ALERT [{level}]: {message} "
                    "(no host monitoring configured - alerts may be lost on restart)"
                )

    def record_metric(
        self, metric_name: str, value: float, timestamp: float | None = None, **kwargs: Any
    ):
        """
        Record a metric value.

        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
            **kwargs: Additional metric metadata (tags, etc.)
        """
        # Send to host monitoring if available
        if self.use_host and self.host_impl is not None:
            try:
                # Try standard interface
                if hasattr(self.host_impl, "gauge"):
                    self.host_impl.gauge(metric_name, value, **kwargs)
                    return
                elif hasattr(self.host_impl, "record"):
                    self.host_impl.record(metric_name, value, timestamp=timestamp, **kwargs)
                    return
                # Try Prometheus-style
                elif hasattr(self.host_impl, "inc") and value == 1:
                    self.host_impl.inc(metric_name, **kwargs)
                    return
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(metric_name, value, timestamp=timestamp, **kwargs)
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host monitoring implementation doesn't match expected interface for record_metric. "
                        f"Expected: gauge(), record(), or inc() method, or callable. "
                        f"Got: {type(self.host_impl).__name__}"
                    )
            except Exception as e:
                logger.error(f"Failed to record metric to host monitoring: {e}")
                _record_fallback("monitoring.record_metric")
        # Note: Internal monitoring is handled by MonitoringSystem.record_metric()
        # which calls this adapter. We don't call back to avoid recursion.

    def gauge(self, metric_name: str, value: float, **kwargs: Any):
        """Record a gauge metric (alias for record_metric)"""
        self.record_metric(metric_name, value, **kwargs)

    def counter(self, metric_name: str, value: float = 1, **kwargs: Any):
        """Record a counter metric"""
        self.record_metric(metric_name, value, **kwargs)

    def is_healthy(self) -> bool:
        """
        Check if monitoring adapter is working correctly.

        Returns:
            bool: True if adapter is healthy, False otherwise
        """
        if not self.use_host:
            return True  # Internal adapter always works

        if self.host_impl is None:
            return False

        try:
            # Try a test operation
            if hasattr(self.host_impl, "gauge"):
                # Test with a no-op metric
                self.host_impl.gauge("_health_check", 1.0)
            elif callable(self.host_impl):
                # Test with callable
                self.host_impl("_health_check", 1.0)
            return True
        except Exception:
            return False


class HostDatabaseAdapter(UtilityAdapter):
    """
    Adapter for host database connection pools.

    Allows reusing host application's database connection pool to avoid
    resource waste (separate connection pools).

    Note: This is different from DatabaseAdapter in src.database.adapters.base
    which is for database type abstraction (PostgreSQL, MySQL, etc.).
    """

    @contextmanager
    def get_connection(self):
        """
        Get a database connection.

        Yields:
            Database connection (from host pool or own pool)
        """
        if self.use_host:
            if self.host_impl is None:
                raise ConnectionError("Host database adapter not configured")
            try:
                # Try standard context manager interface
                if hasattr(self.host_impl, "get_connection"):
                    with self.host_impl.get_connection() as conn:
                        yield conn
                    return
                # Try psycopg2 pool interface (getconn/putconn)
                elif hasattr(self.host_impl, "getconn") and hasattr(self.host_impl, "putconn"):
                    conn = None
                    try:
                        conn = self.host_impl.getconn()
                        if conn is None:
                            raise ConnectionError("Host pool returned None connection")
                        yield conn
                    finally:
                        if conn is not None:
                            try:
                                self.host_impl.putconn(conn)
                            except Exception as put_error:
                                logger.error(
                                    f"Failed to return connection to host pool: {put_error}"
                                )
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host database pool doesn't match expected interface. "
                        f"Expected: get_connection() context manager or getconn()/putconn() methods. "
                        f"Got: {type(self.host_impl).__name__} with methods: "
                        f"{[m for m in dir(self.host_impl) if not m.startswith('_')]}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get connection from host pool: {e}, falling back to own pool"
                )
                _record_fallback("database.get_connection")
                # Alert if fallback happens frequently
                fallback_count = _get_fallback_metrics().get("database.get_connection", 0)
                if fallback_count > 10:  # Alert after 10 fallbacks
                    try:
                        from src.monitoring import get_monitoring

                        monitoring = get_monitoring()
                        monitoring.alert(
                            "warning",
                            f"Database adapter fallback triggered {fallback_count} times. "
                            "Check host database pool configuration.",
                            metric="adapter.fallback.count",
                            value=float(fallback_count),
                        )
                    except Exception:
                        pass  # Don't fail if monitoring not available

        # Fallback to own connection pool
        from src.db import get_connection as get_own_connection

        with get_own_connection() as conn:  # pyright: ignore[reportGeneralTypeIssues]
            yield conn

    def is_healthy(self) -> bool:
        """
        Check if database adapter is working correctly.

        Returns:
            bool: True if adapter is healthy, False otherwise
        """
        if not self.use_host:
            return True  # Internal adapter always works

        if self.host_impl is None:
            return False

        try:
            # Try to get a connection (test operation)
            if hasattr(self.host_impl, "get_connection"):
                with self.host_impl.get_connection() as conn:
                    # Test connection
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
            elif hasattr(self.host_impl, "getconn"):
                conn = self.host_impl.getconn()
                if conn is None:
                    return False
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                finally:
                    self.host_impl.putconn(conn)
            else:
                return False
            return True
        except Exception:
            return False


# Backward compatibility alias
DatabaseAdapter = HostDatabaseAdapter


class AuditAdapter(UtilityAdapter):
    """
    Adapter for audit trail systems.

    Allows writing audit events to both internal mutation_log and host audit system
    for unified compliance tracking.
    """

    def log_event(self, event_type: str, **kwargs: Any):
        """
        Log an audit event to host audit system.

        Note: This is called FROM log_audit_event() after internal logging is complete.
        Do NOT call log_audit_event() from here to avoid recursion.

        Args:
            event_type: Type of event (e.g., 'CREATE_INDEX', 'MUTATION')
            **kwargs: Event details (tenant_id, table_name, field_name, details, etc.)
        """
        # Only log to host audit system (internal logging already done by caller)
        if self.use_host:
            if self.host_impl is None:
                return
            try:
                # Try standard interface
                if hasattr(self.host_impl, "log"):
                    self.host_impl.log(event_type, **kwargs)
                    return
                elif hasattr(self.host_impl, "log_event"):
                    self.host_impl.log_event(event_type, **kwargs)
                    return
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(event_type, **kwargs)
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host audit implementation doesn't match expected interface. "
                        f"Expected: log() or log_event() method, or callable. "
                        f"Got: {type(self.host_impl).__name__}"
                    )
            except Exception as e:
                logger.error(f"Failed to log to host audit system: {e}")
                _record_fallback("audit.log_event")

    def is_healthy(self) -> bool:
        """
        Check if audit adapter is working correctly.

        Returns:
            bool: True if adapter is healthy, False otherwise
        """
        if not self.use_host:
            return True  # Internal adapter always works

        # Audit adapters are typically fire-and-forget, so we just check if impl exists
        return self.host_impl is not None


class LoggerAdapter(UtilityAdapter):
    """
    Adapter for logger configuration.

    Allows host application to configure logging (levels, handlers, formatters)
    while maintaining module-specific loggers.
    """

    def configure(self, config: dict[str, str | int | float | bool | None]):
        """
        Configure logging from host application.

        Args:
            config: Logging configuration dict (compatible with logging.config.dictConfig)
        """
        if config:
            try:
                import logging.config

                logging.config.dictConfig(config)
                logger.info("Logger configured from host application")
            except Exception as e:
                logger.error(f"Failed to configure logger from host: {e}")


class ErrorHandlerAdapter(UtilityAdapter):
    """
    Adapter for error tracking systems.

    Allows sending errors to host error tracking (Sentry, Rollbar, etc.)
    while maintaining internal error handling.
    """

    def capture_exception(self, exception: Exception, **kwargs: Any):
        """
        Capture an exception for error tracking.

        Args:
            exception: Exception to capture
            **kwargs: Additional context (tags, user, etc.)
        """
        if self.use_host:
            if self.host_impl is None:
                return
            try:
                # Try Sentry-style interface
                if hasattr(self.host_impl, "capture_exception"):
                    self.host_impl.capture_exception(exception, **kwargs)
                    return
                # Try Rollbar-style interface
                elif hasattr(self.host_impl, "report_exc_info"):
                    import sys

                    self.host_impl.report_exc_info(sys.exc_info(), **kwargs)
                    return
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(exception, **kwargs)
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host error tracker doesn't match expected interface. "
                        f"Expected: capture_exception() or report_exc_info() method, or callable. "
                        f"Got: {type(self.host_impl).__name__}"
                    )
            except Exception as e:
                logger.error(f"Failed to send exception to host error tracker: {e}")
                _record_fallback("error_handler.capture_exception")

    def capture_message(self, message: str, level: str = "error", **kwargs: Any):
        """
        Capture a message for error tracking.

        Args:
            message: Message to capture
            level: Message level ('error', 'warning', 'info')
            **kwargs: Additional context
        """
        if self.use_host:
            if self.host_impl is None:
                return
            try:
                # Try Sentry-style interface
                if hasattr(self.host_impl, "capture_message"):
                    self.host_impl.capture_message(message, level=level, **kwargs)
                    return
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(message, level=level, **kwargs)
                    return
                else:
                    # Interface mismatch - log warning
                    logger.warning(
                        f"Host error tracker doesn't match expected interface for capture_message. "
                        f"Expected: capture_message() method, or callable. "
                        f"Got: {type(self.host_impl).__name__}"
                    )
            except Exception as e:
                logger.error(f"Failed to send message to host error tracker: {e}")
                _record_fallback("error_handler.capture_message")

    def is_healthy(self) -> bool:
        """
        Check if error handler adapter is working correctly.

        Returns:
            bool: True if adapter is healthy, False otherwise
        """
        if not self.use_host:
            return True  # Internal adapter always works

        # Error trackers are typically fire-and-forget, so we just check if impl exists
        return self.host_impl is not None


# Global adapter instances
_monitoring_adapter: MonitoringAdapter | None = None
_database_adapter: HostDatabaseAdapter | None = None
_audit_adapter: AuditAdapter | None = None
_logger_adapter: LoggerAdapter | None = None
_error_handler_adapter: ErrorHandlerAdapter | None = None


def _validate_monitoring_interface(monitoring: Any) -> bool:
    """Validate monitoring interface"""
    if monitoring is None:
        return True
    return (
        hasattr(monitoring, "alert")
        or hasattr(monitoring, "event")
        or hasattr(monitoring, "gauge")
        or callable(monitoring)
    )


def _validate_database_interface(database: Any) -> bool:
    """Validate database pool interface"""
    if database is None:
        return True
    return hasattr(database, "get_connection") or (
        hasattr(database, "getconn") and hasattr(database, "putconn")
    )


def _validate_audit_interface(audit: Any) -> bool:
    """Validate audit interface"""
    if audit is None:
        return True
    return hasattr(audit, "log") or hasattr(audit, "log_event") or callable(audit)


def _validate_error_tracker_interface(error_tracker: Any) -> bool:
    """Validate error tracker interface"""
    if error_tracker is None:
        return True
    return (
        hasattr(error_tracker, "capture_exception")
        or hasattr(error_tracker, "report_exc_info")
        or hasattr(error_tracker, "capture_message")
        or callable(error_tracker)
    )


def configure_adapters(
    monitoring: Any = None,
    database: Any = None,
    audit: Any = None,
    logger_config: dict[str, Any] | None = None,
    error_tracker: Any = None,
    validate: bool = True,
):
    """
    Configure host utility adapters.

    This function allows host applications to provide their own utility
    implementations. The system will use host utilities when provided,
    and fall back to internal utilities when not.

    This function is thread-safe and idempotent - can be called multiple times.

    Args:
        monitoring: Host monitoring client (Datadog, Prometheus, etc.)
        database: Host database connection pool
        audit: Host audit system
        logger_config: Host logger configuration dict
        error_tracker: Host error tracking client (Sentry, Rollbar, etc.)
        validate: If True, validate host implementations before use (default: True)

    Example:
        from src.adapters import configure_adapters
        import datadog
        import sentry_sdk

        configure_adapters(
            monitoring=datadog.statsd,
            database=host_db_pool,
            audit=host_audit_system,
            logger_config={'version': 1, 'handlers': {...}},
            error_tracker=sentry_sdk
        )
    """
    global _monitoring_adapter, _database_adapter, _audit_adapter
    global _logger_adapter, _error_handler_adapter

    # Validate interfaces if requested
    if validate:
        if monitoring is not None and not _validate_monitoring_interface(monitoring):
            logger.warning(
                f"Monitoring implementation may not match expected interface: {type(monitoring).__name__}"
            )
        if database is not None and not _validate_database_interface(database):
            logger.warning(
                f"Database pool may not match expected interface: {type(database).__name__}"
            )
        if audit is not None and not _validate_audit_interface(audit):
            logger.warning(
                f"Audit implementation may not match expected interface: {type(audit).__name__}"
            )
        if error_tracker is not None and not _validate_error_tracker_interface(error_tracker):
            logger.warning(
                f"Error tracker may not match expected interface: {type(error_tracker).__name__}"
            )

    with _adapter_lock:
        _monitoring_adapter = MonitoringAdapter(monitoring)
        _database_adapter = HostDatabaseAdapter(database)
        _audit_adapter = AuditAdapter(audit)
        _logger_adapter = LoggerAdapter(None)  # No host impl needed, just config
        _error_handler_adapter = ErrorHandlerAdapter(error_tracker)

        # Configure logger if config provided
        if logger_config:
            _logger_adapter.configure(logger_config)

    logger.info("Utility adapters configured")

    # Warn if critical adapters not configured in production
    is_production = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    if is_production and not monitoring:
        logger.warning(
            "CRITICAL: No host monitoring configured in production. "
            "Alerts may be lost on restart. Consider configuring monitoring adapter."
        )


def get_monitoring_adapter() -> MonitoringAdapter:
    """Get monitoring adapter (creates default if not configured, thread-safe)"""
    global _monitoring_adapter
    if _monitoring_adapter is None:
        with _adapter_lock:
            # Double-check pattern to avoid race condition
            if _monitoring_adapter is None:
                _monitoring_adapter = MonitoringAdapter()
    return _monitoring_adapter


def get_host_database_adapter() -> HostDatabaseAdapter:
    """
    Get host database adapter for connection integration.

    This adapter allows IndexPilot to use the host application's database
    connection pool instead of creating its own. This is different from
    get_database_adapter() in src.database which returns the actual database
    adapter (PostgreSQL, MySQL, etc.) for database operations.

    Returns:
        HostDatabaseAdapter: Host database connection adapter (creates default if not configured, thread-safe)
    """
    global _database_adapter
    if _database_adapter is None:
        with _adapter_lock:
            # Double-check pattern to avoid race condition
            if _database_adapter is None:
                _database_adapter = HostDatabaseAdapter()
    return _database_adapter


def get_audit_adapter() -> AuditAdapter:
    """Get audit adapter (creates default if not configured, thread-safe)"""
    global _audit_adapter
    if _audit_adapter is None:
        with _adapter_lock:
            # Double-check pattern to avoid race condition
            if _audit_adapter is None:
                _audit_adapter = AuditAdapter()
    return _audit_adapter


def get_error_handler_adapter() -> ErrorHandlerAdapter:
    """Get error handler adapter (creates default if not configured, thread-safe)"""
    global _error_handler_adapter
    if _error_handler_adapter is None:
        with _adapter_lock:
            # Double-check pattern to avoid race condition
            if _error_handler_adapter is None:
                _error_handler_adapter = ErrorHandlerAdapter()
    return _error_handler_adapter


def get_adapter_fallback_metrics() -> dict[str, int]:
    """
    Get adapter fallback metrics.

    Returns metrics showing how many times adapters fell back to internal utilities
    due to host implementation failures.

    Returns:
        dict[str, int]: Dictionary mapping adapter operation names to fallback counts
    """
    return _get_fallback_metrics()


def reset_adapter_fallback_metrics() -> None:
    """
    Reset adapter fallback metrics.

    Useful for testing or periodic metric resets.
    """
    _reset_fallback_metrics()
