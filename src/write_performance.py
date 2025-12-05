"""Write performance monitoring and index limits"""

import logging

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.monitoring import get_monitoring
from src.types import BoolStrTuple

logger = logging.getLogger(__name__)

# Load config for write performance settings
try:

    from src.config_loader import ConfigLoader
    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def _get_max_indexes_per_table() -> int:
    """Get max indexes per table from config"""
    if _config_loader is None:
        return 10
    return _config_loader.get_int('production_safeguards.write_performance.max_indexes_per_table', 10)


def _get_warn_indexes_per_table() -> int:
    """Get warn threshold from config"""
    if _config_loader is None:
        return 7
    return _config_loader.get_int('production_safeguards.write_performance.warn_indexes_per_table', 7)


def _get_write_performance_threshold() -> float:
    """Get write performance threshold from config"""
    if _config_loader is None:
        return 0.2
    return _config_loader.get_float('production_safeguards.write_performance.write_overhead_threshold', 0.2)


def is_write_performance_enabled() -> bool:
    """Check if write performance monitoring is enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool('production_safeguards.write_performance.enabled', True)


def get_index_count_for_table(table_name: str) -> int:
    """Get current number of indexes for a table"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM pg_indexes
                WHERE tablename = %s
                  AND schemaname = %s
                  AND indexname LIKE %s
            """, (table_name, 'public', 'idx_%'))
            result = cursor.fetchone()
            return result['count'] if result and 'count' in result else 0
        finally:
            cursor.close()


def can_create_index_for_table(table_name: str) -> BoolStrTuple:
    """
    Check if we can create another index for a table.

    Returns:
        (can_create, reason_if_not)
    """
    if not is_write_performance_enabled():
        return True, None  # If disabled, allow index creation

    current_count = get_index_count_for_table(table_name)
    max_indexes = _get_max_indexes_per_table()
    warn_threshold = _get_warn_indexes_per_table()

    if current_count >= max_indexes:
        return False, f"Table {table_name} already has {current_count} indexes (max: {max_indexes})"

    if current_count >= warn_threshold:
        monitoring = get_monitoring()
        monitoring.alert('warning',
                        f'Table {table_name} approaching index limit '
                        f'({current_count}/{max_indexes})')

    return True, None


def get_table_write_stats(table_name: str, hours: int = 24) -> dict:
    """
    Get write performance statistics for a table.

    Tracks actual INSERT/UPDATE/DELETE operations from query_stats table
    and calculates real write performance metrics.
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get actual write operation statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_writes,
                    AVG(duration_ms) as avg_write_duration_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_write_duration_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_write_duration_ms
                FROM query_stats
                WHERE table_name = %s
                  AND query_type = 'WRITE'
                  AND created_at >= NOW() - INTERVAL '1 hour' * %s
            """, (table_name, hours))

            write_stats = cursor.fetchone()

            # Get baseline (write performance without indexes, from historical data)
            # For now, use a simple heuristic: assume 10ms baseline per write
            baseline_write_duration_ms = 10.0

            index_count = get_index_count_for_table(table_name)

            # Calculate estimated overhead based on index count
            # Each index adds ~2-5% overhead to writes (index maintenance)
            estimated_write_overhead = min(index_count * 0.03, 0.5)  # Cap at 50%

            # If we have actual write stats, use them
            if write_stats and write_stats['total_writes'] and write_stats['total_writes'] > 0:
                avg_duration = write_stats['avg_write_duration_ms'] or baseline_write_duration_ms
                overhead_ratio = (avg_duration - baseline_write_duration_ms) / baseline_write_duration_ms if baseline_write_duration_ms > 0 else 0
                estimated_write_overhead = max(0, min(overhead_ratio, 1.0))  # Clamp 0-100%
            else:
                # No write stats available, use estimation
                avg_duration = baseline_write_duration_ms * (1 + estimated_write_overhead)

            max_indexes = _get_max_indexes_per_table()
            return {
                'table_name': table_name,
                'index_count': index_count,
                'total_writes': write_stats['total_writes'] if write_stats else 0,
                'avg_write_duration_ms': write_stats['avg_write_duration_ms'] if write_stats else avg_duration,
                'p95_write_duration_ms': write_stats['p95_write_duration_ms'] if write_stats else None,
                'p99_write_duration_ms': write_stats['p99_write_duration_ms'] if write_stats else None,
                'estimated_write_overhead': estimated_write_overhead,
                'baseline_duration_ms': baseline_write_duration_ms,
                'status': 'ok' if index_count < max_indexes else 'limit_reached'
            }
        finally:
            cursor.close()


def monitor_write_performance(table_name: str):
    """
    Monitor write performance and alert if degraded.

    In production, this would:
    1. Track INSERT/UPDATE/DELETE latency
    2. Compare against baseline
    3. Alert if degradation exceeds threshold
    """
    if not is_write_performance_enabled():
        return {}  # If disabled, return empty stats

    stats = get_table_write_stats(table_name)
    threshold = _get_write_performance_threshold()

    if stats.get('estimated_write_overhead', 0) > threshold:
        monitoring = get_monitoring()
        monitoring.alert('warning',
                        f'Table {table_name} may have degraded write performance '
                        f'(estimated overhead: {stats["estimated_write_overhead"]*100:.1f}%)')

    return stats

