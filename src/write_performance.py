"""Write performance monitoring and index limits"""

import logging
from decimal import Decimal
from typing import Any

from src.db import get_cursor
from src.monitoring import get_monitoring
from src.type_definitions import BoolStrTuple, JSONValue

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
    return _config_loader.get_int(
        "production_safeguards.write_performance.max_indexes_per_table", 10
    )


def _get_warn_indexes_per_table() -> int:
    """Get warn threshold from config"""
    if _config_loader is None:
        return 7
    return _config_loader.get_int(
        "production_safeguards.write_performance.warn_indexes_per_table", 7
    )


def _get_write_performance_threshold() -> float:
    """Get write performance threshold from config"""
    if _config_loader is None:
        return 0.2
    return _config_loader.get_float(
        "production_safeguards.write_performance.write_overhead_threshold", 0.2
    )


def is_write_performance_enabled() -> bool:
    """Check if write performance monitoring is enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("production_safeguards.write_performance.enabled", True)


def get_index_count_for_table(table_name: str) -> int:
    """Get current number of indexes for a table"""
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM pg_indexes
            WHERE tablename = %s
              AND schemaname = %s
        """,
            (table_name, "public"),
        )
        result = cursor.fetchone()
        if result and "count" in result:
            count_val = result["count"]
            return int(count_val) if isinstance(count_val, int | float) else 0
        return 0


def _optional_float(value: Any) -> float | None:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


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
        monitoring.alert(
            "warning", f"Table {table_name} approaching index limit ({current_count}/{max_indexes})"
        )

    return True, None


def get_table_write_stats(table_name: str, hours: int = 24) -> dict[str, JSONValue]:
    """
    Get write performance statistics for a table.

    Reports observed writes, latency samples, and index footprint. It does not
    invent an index-overhead percentage without a comparable baseline.
    """
    if hours < 1:
        raise ValueError("hours must be at least 1")

    with get_cursor() as cursor:
        # Get actual write operation statistics
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_writes,
                AVG(duration_ms) as avg_write_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_write_duration_ms,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_write_duration_ms
            FROM query_stats
            WHERE table_name = %s
              AND query_type = 'WRITE'
              AND created_at >= NOW() - INTERVAL '1 hour' * %s
        """,
            (table_name, hours),
        )

        write_stats = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS index_count,
                   COALESCE(SUM(pg_relation_size(indexrelid)), 0) AS total_index_bytes
            FROM pg_stat_user_indexes
            WHERE schemaname = %s AND relname = %s
            """,
            ("public", table_name),
        )
        index_inventory = cursor.fetchone() or {}
        cursor.execute(
            """
            SELECT n_tup_ins AS inserts,
                   n_tup_upd AS updates,
                   n_tup_del AS deletes,
                   n_tup_hot_upd AS hot_updates,
                   (SELECT stats_reset::text FROM pg_stat_database
                    WHERE datname = current_database()) AS database_stats_reset_at
            FROM pg_stat_user_tables
            WHERE schemaname = %s AND relname = %s
            """,
            ("public", table_name),
        )
        activity = cursor.fetchone() or {}

        logged_write_samples = int((write_stats or {}).get("total_writes", 0) or 0)
        index_count = int(index_inventory.get("index_count", 0) or 0)
        inserts = int(activity.get("inserts", 0) or 0)
        updates = int(activity.get("updates", 0) or 0)
        deletes = int(activity.get("deletes", 0) or 0)

        max_indexes = _get_max_indexes_per_table()
        return {
            "table_name": table_name,
            "index_count": index_count,
            "total_index_bytes": int(index_inventory.get("total_index_bytes", 0) or 0),
            "total_writes": logged_write_samples,
            "logged_write_samples": logged_write_samples,
            "writes_observed": inserts + updates + deletes,
            "inserts": inserts,
            "updates": updates,
            "deletes": deletes,
            "hot_updates": int(activity.get("hot_updates", 0) or 0),
            "database_stats_reset_at": activity.get("database_stats_reset_at"),
            "observation_window_hours": hours,
            "avg_write_duration_ms": _optional_float(
                (write_stats or {}).get("avg_write_duration_ms")
            ),
            "p95_write_duration_ms": _optional_float(
                (write_stats or {}).get("p95_write_duration_ms")
            ),
            "p99_write_duration_ms": _optional_float(
                (write_stats or {}).get("p99_write_duration_ms")
            ),
            "estimated_write_overhead": None,
            "baseline_duration_ms": None,
            "write_overhead_status": "not_measured",
            "measurement_status": (
                "latency_observed_without_comparable_baseline"
                if logged_write_samples
                else "no_write_latency_samples"
            ),
            "status": "ok" if index_count < max_indexes else "limit_reached",
        }


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

    measured_overhead = stats.get("estimated_write_overhead")
    if isinstance(measured_overhead, int | float) and measured_overhead > threshold:
        monitoring = get_monitoring()
        monitoring.alert(
            "warning",
            f"Table {table_name} has measured write overhead above the configured threshold "
            f"({measured_overhead * 100:.1f}%)",
        )

    return stats
