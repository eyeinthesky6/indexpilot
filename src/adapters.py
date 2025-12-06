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

logger = logging.getLogger(__name__)

# Thread safety for global adapter instances
_adapter_lock = threading.Lock()


class UtilityAdapter:
    """Base adapter class for host utilities"""

    def __init__(self, host_impl=None):
        """
        Initialize adapter.

        Args:
            host_impl: Host implementation (optional) - can be any third-party object
        """
        self.host_impl = host_impl
        self.use_host = host_impl is not None


class MonitoringAdapter(UtilityAdapter):
    """
    Adapter for monitoring systems.

    CRITICAL: This adapter is required for production deployments to prevent
    alert loss. In-memory monitoring loses alerts on restart.

    Supports:
    - Datadog, Prometheus, New Relic, etc.
    - Custom monitoring implementations
    """

    def alert(self, level: str, message: str, metric: str | None = None,
              value: float | None = None, **kwargs):
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
                if hasattr(self.host_impl, 'alert'):
                    self.host_impl.alert(level, message, metric=metric, value=value, **kwargs)
                # Try Datadog-style interface
                elif hasattr(self.host_impl, 'event'):
                    self.host_impl.event(
                        title=message,
                        text=f"Metric: {metric}, Value: {value}" if metric else message,
                        alert_type=level,
                        **kwargs
                    )
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(level, message, metric=metric, value=value, **kwargs)
            except Exception as e:
                logger.error(f"Failed to send alert to host monitoring: {e}")
        else:
            # Log warning if no host monitoring in production
            is_production = os.getenv('ENVIRONMENT', '').lower() in ('production', 'prod')
            if is_production:
                logger.warning(
                    f"ALERT [{level}]: {message} "
                    "(no host monitoring configured - alerts may be lost on restart)"
                )

    def record_metric(self, metric_name: str, value: float, timestamp: float | None = None, **kwargs):
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
                if hasattr(self.host_impl, 'gauge'):
                    self.host_impl.gauge(metric_name, value, **kwargs)
                elif hasattr(self.host_impl, 'record'):
                    self.host_impl.record(metric_name, value, timestamp=timestamp, **kwargs)
                # Try Prometheus-style
                elif hasattr(self.host_impl, 'inc') and value == 1:
                    self.host_impl.inc(metric_name, **kwargs)
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(metric_name, value, timestamp=timestamp, **kwargs)
            except Exception as e:
                logger.error(f"Failed to record metric to host monitoring: {e}")
        # Note: Internal monitoring is handled by MonitoringSystem.record_metric()
        # which calls this adapter. We don't call back to avoid recursion.

    def gauge(self, metric_name: str, value: float, **kwargs):
        """Record a gauge metric (alias for record_metric)"""
        self.record_metric(metric_name, value, **kwargs)

    def counter(self, metric_name: str, value: float = 1, **kwargs):
        """Record a counter metric"""
        self.record_metric(metric_name, value, **kwargs)


class DatabaseAdapter(UtilityAdapter):
    """
    Adapter for database connections.

    Allows reusing host application's database connection pool to avoid
    resource waste (separate connection pools).
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
                if hasattr(self.host_impl, 'get_connection'):
                    with self.host_impl.get_connection() as conn:
                        yield conn
                    return
                # Try psycopg2 pool interface (getconn/putconn)
                elif hasattr(self.host_impl, 'getconn') and hasattr(self.host_impl, 'putconn'):
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
                                logger.error(f"Failed to return connection to host pool: {put_error}")
                    return
            except Exception as e:
                logger.error(f"Failed to get connection from host pool: {e}, falling back to own pool")

        # Fallback to own connection pool
        from src.db import get_connection as get_own_connection
        with get_own_connection() as conn:  # pyright: ignore[reportGeneralTypeIssues]
            yield conn


class AuditAdapter(UtilityAdapter):
    """
    Adapter for audit trail systems.

    Allows writing audit events to both internal mutation_log and host audit system
    for unified compliance tracking.
    """

    def log_event(self, event_type: str, **kwargs):
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
                if hasattr(self.host_impl, 'log'):
                    self.host_impl.log(event_type, **kwargs)
                elif hasattr(self.host_impl, 'log_event'):
                    self.host_impl.log_event(event_type, **kwargs)
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(event_type, **kwargs)
            except Exception as e:
                logger.error(f"Failed to log to host audit system: {e}")


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

    def capture_exception(self, exception: Exception, **kwargs):
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
                if hasattr(self.host_impl, 'capture_exception'):
                    self.host_impl.capture_exception(exception, **kwargs)
                # Try Rollbar-style interface
                elif hasattr(self.host_impl, 'report_exc_info'):
                    import sys
                    self.host_impl.report_exc_info(sys.exc_info(), **kwargs)
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(exception, **kwargs)
            except Exception as e:
                logger.error(f"Failed to send exception to host error tracker: {e}")

    def capture_message(self, message: str, level: str = 'error', **kwargs):
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
                if hasattr(self.host_impl, 'capture_message'):
                    self.host_impl.capture_message(message, level=level, **kwargs)
                # Try generic callable
                elif callable(self.host_impl):
                    self.host_impl(message, level=level, **kwargs)
            except Exception as e:
                logger.error(f"Failed to send message to host error tracker: {e}")


# Global adapter instances
_monitoring_adapter: MonitoringAdapter | None = None
_database_adapter: DatabaseAdapter | None = None
_audit_adapter: AuditAdapter | None = None
_logger_adapter: LoggerAdapter | None = None
_error_handler_adapter: ErrorHandlerAdapter | None = None


def configure_adapters(
    monitoring=None,
    database=None,
    audit=None,
    logger_config=None,
    error_tracker=None
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

    with _adapter_lock:
        _monitoring_adapter = MonitoringAdapter(monitoring)
        _database_adapter = DatabaseAdapter(database)
        _audit_adapter = AuditAdapter(audit)
        _logger_adapter = LoggerAdapter(None)  # No host impl needed, just config
        _error_handler_adapter = ErrorHandlerAdapter(error_tracker)

        # Configure logger if config provided
        if logger_config:
            _logger_adapter.configure(logger_config)

    logger.info("Utility adapters configured")

    # Warn if critical adapters not configured in production
    is_production = os.getenv('ENVIRONMENT', '').lower() in ('production', 'prod')
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


def get_host_database_adapter() -> DatabaseAdapter:
    """
    Get host database adapter for connection integration.

    This adapter allows IndexPilot to use the host application's database
    connection pool instead of creating its own. This is different from
    get_database_adapter() in src.database which returns the actual database
    adapter (PostgreSQL, MySQL, etc.) for database operations.

    Returns:
        DatabaseAdapter: Host database connection adapter (creates default if not configured, thread-safe)
    """
    global _database_adapter
    if _database_adapter is None:
        with _adapter_lock:
            # Double-check pattern to avoid race condition
            if _database_adapter is None:
                _database_adapter = DatabaseAdapter()
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

