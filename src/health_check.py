"""Comprehensive health check system for production"""

import logging
import time

from src.db import get_cursor, get_pool_stats
from src.graceful_shutdown import is_shutting_down
from src.monitoring import check_system_health
from src.rollback import is_system_enabled
from src.type_definitions import (
    ConnectionPoolHealth,
    DatabaseHealthStatus,
    HealthSummary,
    JSONValue,
    PoolStats,
    SystemHealthStatus,
    SystemStatus,
)

logger = logging.getLogger(__name__)

# Load config for health checks toggle
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def is_health_checks_enabled() -> bool:
    """Check if health checks are enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("operational.health_checks.enabled", True)


def check_database_health() -> DatabaseHealthStatus:
    """
    Check database connection health.

    Returns:
        dict with health status
    """
    health: DatabaseHealthStatus = {"status": "unknown", "latency_ms": None, "error": None}

    try:
        start_time = time.time()
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            latency_ms = (time.time() - start_time) * 1000
            health["status"] = "healthy"
            health["latency_ms"] = latency_ms
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        logger.error(f"Database health check failed: {e}")

    return health


def check_connection_pool_health() -> ConnectionPoolHealth:
    """
    Check connection pool health.

    Returns:
        dict with pool health status
    """
    health: ConnectionPoolHealth = {"status": "unknown", "pool_stats": None, "error": None}

    try:
        pool_stats_raw = get_pool_stats()
        if pool_stats_raw and isinstance(pool_stats_raw, dict):
            # Convert to PoolStats TypedDict format
            # Note: get_pool_stats returns min_conn/max_conn, but PoolStats expects min_connections/max_connections
            min_conn_val = pool_stats_raw.get("min_conn") or pool_stats_raw.get(
                "min_connections", 0
            )
            max_conn_val = pool_stats_raw.get("max_conn") or pool_stats_raw.get(
                "max_connections", 0
            )
            pool_stats: PoolStats = {
                "min_connections": int(min_conn_val)
                if isinstance(min_conn_val, int | float)
                else 0,
                "max_connections": int(max_conn_val)
                if isinstance(max_conn_val, int | float)
                else 0,
                "current_connections": int(pool_stats_raw.get("current_connections", 0))
                if isinstance(pool_stats_raw.get("current_connections"), int | float)
                else 0,
                "available_connections": int(pool_stats_raw.get("available_connections", 0))
                if isinstance(pool_stats_raw.get("available_connections"), int | float)
                else 0,
                "waiting_requests": int(pool_stats_raw.get("waiting_requests", 0))
                if isinstance(pool_stats_raw.get("waiting_requests"), int | float)
                else 0,
            }
            health["status"] = "healthy"
            health["pool_stats"] = pool_stats
        else:
            health["status"] = "degraded"
            health["error"] = "Pool not initialized"
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        logger.error(f"Connection pool health check failed: {e}")

    return health


def check_system_status() -> SystemStatus:
    """
    Check overall system status.

    Returns:
        dict with system status
    """
    status: SystemStatus = {
        "enabled": is_system_enabled(),
        "shutting_down": is_shutting_down(),
        "status": "operational",
    }

    if status["shutting_down"]:
        status["status"] = "shutting_down"
    elif not status["enabled"]:
        status["status"] = "disabled"

    return status


def comprehensive_health_check() -> SystemHealthStatus:
    """
    Perform comprehensive health check of all system components.

    Returns:
        dict with comprehensive health status
    """
    if not is_health_checks_enabled():
        return {
            "timestamp": time.time(),
            "overall_status": "disabled",
            "message": "Health checks are disabled via operational.health_checks.enabled",
            "components": {},
            "warnings": [],
            "errors": [],
        }

    health: SystemHealthStatus = {
        "timestamp": time.time(),
        "overall_status": "unknown",
        "components": {},
        "warnings": [],
        "errors": [],
    }

    # Check database
    db_health = check_database_health()
    health["components"]["database"] = db_health
    if db_health["status"] != "healthy":
        health["errors"].append(f"Database: {db_health.get('error', 'unknown error')}")

    # Check connection pool
    pool_health = check_connection_pool_health()
    health["components"]["connection_pool"] = pool_health
    pool_status = pool_health.get("status", "unknown")
    if isinstance(pool_status, str) and pool_status != "healthy":
        pool_error = pool_health.get("error", "unknown error")
        error_str = str(pool_error) if pool_error is not None else "unknown error"
        health["warnings"].append(f"Connection pool: {error_str}")

    # Check system status
    system_status = check_system_status()
    # Convert SystemStatus to dict[str, JSONValue] for compatibility
    system_status_dict: dict[str, JSONValue] = {
        "status": system_status["status"],
        "enabled": system_status["enabled"],
        "shutting_down": system_status["shutting_down"],
    }
    health["components"]["system"] = system_status_dict
    if system_status["status"] != "operational":
        health["warnings"].append(f"System: {system_status['status']}")

    # Check monitoring system
    try:
        monitoring_health = check_system_health()
        health["components"]["monitoring"] = monitoring_health
        if monitoring_health.get("status") != "healthy":
            health["warnings"].append(f"Monitoring: {monitoring_health.get('status', 'unknown')}")
    except Exception as e:
        health["warnings"].append(f"Monitoring check failed: {e}")

    # Determine overall status
    if health["errors"]:
        health["overall_status"] = "unhealthy"
    elif health["warnings"]:
        health["overall_status"] = "degraded"
    else:
        health["overall_status"] = "healthy"

    return health


def get_health_summary() -> HealthSummary:
    """
    Get quick health summary for monitoring/alerting.

    Returns:
        dict with health summary
    """
    health = comprehensive_health_check()

    components = health.get("components", {})
    database_status_val = components.get("database", {})
    pool_status_val = components.get("connection_pool", {})
    system_status_val = components.get("system", {})

    # Extract status strings with proper type checking
    database_status_str = "unknown"
    if isinstance(database_status_val, dict):
        status_val = database_status_val.get("status")
        if isinstance(status_val, str):
            database_status_str = status_val

    pool_status_str = "unknown"
    if isinstance(pool_status_val, dict):
        status_val = pool_status_val.get("status")
        if isinstance(status_val, str):
            pool_status_str = status_val

    system_status_str = "unknown"
    if isinstance(system_status_val, dict):
        status_val = system_status_val.get("status")
        if isinstance(status_val, str):
            system_status_str = status_val

    overall_status = health.get("overall_status", "unknown")
    overall_status_str = overall_status if isinstance(overall_status, str) else "unknown"

    summary: HealthSummary = {
        "status": overall_status_str,
        "database": database_status_str,
        "pool": pool_status_str,
        "system": system_status_str,
        "has_errors": len(health.get("errors", [])) > 0,
        "has_warnings": len(health.get("warnings", [])) > 0,
    }

    return summary
