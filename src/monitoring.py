"""Real-time monitoring and alerting"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection

logger = logging.getLogger(__name__)

# Alert thresholds
ALERT_THRESHOLDS = {
    'query_latency_p95_ms': 100,  # Alert if P95 > 100ms
    'query_latency_p99_ms': 200,  # Alert if P99 > 200ms
    'connection_pool_exhaustion': True,  # Alert on pool exhaustion
    'index_creation_failure': True,  # Alert on index creation failure
    'error_rate_pct': 5.0,  # Alert if error rate > 5%
    'index_size_gb': 10.0,  # Alert if total index size > 10GB
}


class MonitoringSystem:
    """Real-time monitoring system"""

    def __init__(self):
        self.alerts = []
        self.metrics = defaultdict(list)
        self.alert_callbacks = []

    def add_alert_callback(self, callback):
        """Add a callback function for alerts"""
        self.alert_callbacks.append(callback)

    def record_metric(self, metric_name, value, timestamp=None):
        """Record a metric value"""
        if timestamp is None:
            timestamp = time.time()
        self.metrics[metric_name].append((timestamp, value))

        # Keep only last 1000 values per metric
        if len(self.metrics[metric_name]) > 1000:
            self.metrics[metric_name] = self.metrics[metric_name][-1000:]

        # Also send via adapter (if configured) - this ensures host monitoring gets metrics
        try:
            from src.adapters import get_monitoring_adapter
            adapter = get_monitoring_adapter()
            adapter.record_metric(metric_name, value, timestamp=timestamp)
        except Exception as e:
            # Don't fail if adapter not available or fails
            logger.debug(f"Could not record metric via adapter: {e}")

    def check_thresholds(self):
        """Check if any metrics exceed thresholds"""
        alerts = []

        # Check query latency
        if 'query_latency_p95' in self.metrics and self.metrics['query_latency_p95']:
            latest_p95 = self.metrics['query_latency_p95'][-1][1]
            if latest_p95 > ALERT_THRESHOLDS['query_latency_p95_ms']:
                alerts.append({
                    'level': 'warning',
                    'metric': 'query_latency_p95',
                    'value': latest_p95,
                    'threshold': ALERT_THRESHOLDS['query_latency_p95_ms'],
                    'message': f'P95 query latency ({latest_p95:.2f}ms) exceeds threshold ({ALERT_THRESHOLDS["query_latency_p95_ms"]}ms)'
                })

        if 'query_latency_p99' in self.metrics and self.metrics['query_latency_p99']:
            latest_p99 = self.metrics['query_latency_p99'][-1][1]
            if latest_p99 > ALERT_THRESHOLDS['query_latency_p99_ms']:
                alerts.append({
                    'level': 'critical',
                    'metric': 'query_latency_p99',
                    'value': latest_p99,
                    'threshold': ALERT_THRESHOLDS['query_latency_p99_ms'],
                    'message': f'P99 query latency ({latest_p99:.2f}ms) exceeds threshold ({ALERT_THRESHOLDS["query_latency_p99_ms"]}ms)'
                })

        # Check error rate
        if 'error_rate' in self.metrics and self.metrics['error_rate']:
            latest_error_rate = self.metrics['error_rate'][-1][1]
            if latest_error_rate > ALERT_THRESHOLDS['error_rate_pct']:
                alerts.append({
                    'level': 'critical',
                    'metric': 'error_rate',
                    'value': latest_error_rate,
                    'threshold': ALERT_THRESHOLDS['error_rate_pct'],
                    'message': f'Error rate ({latest_error_rate:.2f}%) exceeds threshold ({ALERT_THRESHOLDS["error_rate_pct"]}%)'
                })

        return alerts

    def alert(self, level, message, metric=None, value=None):
        """Send an alert"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'metric': metric,
            'value': value
        }

        self.alerts.append(alert)

        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        # Log alert
        if level == 'critical':
            logger.critical(f"ALERT: {message}")
        elif level == 'warning':
            logger.warning(f"ALERT: {message}")
        else:
            logger.info(f"ALERT: {message}")

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        # Also send via adapter (if configured) - this ensures host monitoring gets alerts
        try:
            from src.adapters import get_monitoring_adapter
            adapter = get_monitoring_adapter()
            adapter.alert(level, message, metric=metric, value=value)
        except Exception as e:
            # Don't fail if adapter not available or fails
            logger.debug(f"Could not send alert via adapter: {e}")

    def get_recent_alerts(self, minutes=60):
        """Get alerts from the last N minutes"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert['timestamp']) >= cutoff
        ]

    def get_metrics_summary(self):
        """Get summary of recent metrics"""
        summary = {}

        for metric_name, values in self.metrics.items():
            if values:
                recent_values = [v[1] for v in values[-100:]]  # Last 100 values
                summary[metric_name] = {
                    'count': len(recent_values),
                    'avg': sum(recent_values) / len(recent_values) if recent_values else 0,
                    'min': min(recent_values) if recent_values else 0,
                    'max': max(recent_values) if recent_values else 0,
                    'latest': recent_values[-1] if recent_values else 0
                }

        return summary


# Global monitoring instance
_monitoring = MonitoringSystem()


def get_monitoring():
    """Get global monitoring instance"""
    return _monitoring


def check_system_health():
    """Check overall system health and return status"""
    from src.types import JSONDict
    health: JSONDict = {
        'status': 'healthy',
        'checks': {},
        'timestamp': datetime.now().isoformat()
    }

    # Ensure checks is a dict
    checks = health.get('checks', {})
    if not isinstance(checks, dict):
        checks = {}
        health['checks'] = checks

    # Check database connectivity
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
        health['status'] = 'degraded'

    # Check connection pool
    try:
        from src.db import get_pool_stats
        pool_stats = get_pool_stats()
        if pool_stats:
            checks['connection_pool'] = 'ok'
        else:
            checks['connection_pool'] = 'not_initialized'
            health['status'] = 'degraded'
    except Exception as e:
        checks['connection_pool'] = f'error: {str(e)}'
        health['status'] = 'degraded'

    # Check recent alerts
    recent_alerts = _monitoring.get_recent_alerts(minutes=5)
    critical_alerts = [a for a in recent_alerts if a['level'] == 'critical']
    if critical_alerts:
        health['status'] = 'critical'
        checks['alerts'] = f'{len(critical_alerts)} critical alerts'

    return health


def get_index_usage_stats():
    """Get statistics on index usage to identify unused indexes"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                ORDER BY idx_scan ASC
            """)
            return cursor.fetchall()
        finally:
            cursor.close()

