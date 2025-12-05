"""Comprehensive health check system for production"""

import logging
import time
from typing import Any

from src.db import get_connection, get_pool_stats
from src.graceful_shutdown import is_shutting_down
from src.monitoring import check_system_health
from src.rollback import is_system_enabled

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
    return _config_loader.get_bool('operational.health_checks.enabled', True)


def check_database_health() -> dict[str, Any]:
    """
    Check database connection health.

    Returns:
        dict with health status
    """
    health: dict[str, Any] = {
        'status': 'unknown',
        'latency_ms': None,
        'error': None
    }

    try:
        start_time = time.time()
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT 1')
                cursor.fetchone()
                latency_ms = (time.time() - start_time) * 1000
                health['status'] = 'healthy'
                health['latency_ms'] = latency_ms
            finally:
                cursor.close()
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        logger.error(f"Database health check failed: {e}")

    return health


def check_connection_pool_health() -> dict[str, Any]:
    """
    Check connection pool health.

    Returns:
        dict with pool health status
    """
    health: dict[str, Any] = {
        'status': 'unknown',
        'pool_stats': None,
        'error': None
    }

    try:
        pool_stats = get_pool_stats()
        if pool_stats:
            health['status'] = 'healthy'
            health['pool_stats'] = pool_stats
        else:
            health['status'] = 'degraded'
            health['error'] = 'Pool not initialized'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        logger.error(f"Connection pool health check failed: {e}")

    return health


def check_system_status() -> dict[str, Any]:
    """
    Check overall system status.

    Returns:
        dict with system status
    """
    status: dict[str, Any] = {
        'enabled': is_system_enabled(),
        'shutting_down': is_shutting_down(),
        'status': 'operational'
    }

    if status['shutting_down']:
        status['status'] = 'shutting_down'
    elif not status['enabled']:
        status['status'] = 'disabled'

    return status


def comprehensive_health_check() -> dict[str, Any]:
    """
    Perform comprehensive health check of all system components.

    Returns:
        dict with comprehensive health status
    """
    if not is_health_checks_enabled():
        return {
            'timestamp': time.time(),
            'overall_status': 'disabled',
            'message': 'Health checks are disabled via operational.health_checks.enabled',
            'components': {},
            'warnings': [],
            'errors': []
        }

    health: dict[str, Any] = {
        'timestamp': time.time(),
        'overall_status': 'unknown',
        'components': {},
        'warnings': [],
        'errors': []
    }

    # Check database
    db_health = check_database_health()
    health['components']['database'] = db_health
    if db_health['status'] != 'healthy':
        health['errors'].append(f"Database: {db_health.get('error', 'unknown error')}")

    # Check connection pool
    pool_health = check_connection_pool_health()
    health['components']['connection_pool'] = pool_health
    if pool_health['status'] != 'healthy':
        health['warnings'].append(f"Connection pool: {pool_health.get('error', 'unknown error')}")

    # Check system status
    system_status = check_system_status()
    health['components']['system'] = system_status
    if system_status['status'] != 'operational':
        health['warnings'].append(f"System: {system_status['status']}")

    # Check monitoring system
    try:
        monitoring_health = check_system_health()
        health['components']['monitoring'] = monitoring_health
        if monitoring_health.get('status') != 'healthy':
            health['warnings'].append(f"Monitoring: {monitoring_health.get('status', 'unknown')}")
    except Exception as e:
        health['warnings'].append(f"Monitoring check failed: {e}")

    # Determine overall status
    if health['errors']:
        health['overall_status'] = 'unhealthy'
    elif health['warnings']:
        health['overall_status'] = 'degraded'
    else:
        health['overall_status'] = 'healthy'

    return health


def get_health_summary() -> dict[str, Any]:
    """
    Get quick health summary for monitoring/alerting.

    Returns:
        dict with health summary
    """
    health = comprehensive_health_check()

    summary: dict[str, Any] = {
        'status': health['overall_status'],
        'database': health['components']['database']['status'],
        'pool': health['components']['connection_pool']['status'],
        'system': health['components']['system']['status'],
        'has_errors': len(health['errors']) > 0,
        'has_warnings': len(health['warnings']) > 0
    }

    return summary

