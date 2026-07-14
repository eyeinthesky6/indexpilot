"""Index health monitoring and maintenance"""

import logging
from datetime import datetime
from typing import Any

from src.db import get_cursor
from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)


def monitor_index_health(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 1.0,
) -> dict[str, Any]:
    """
    Collect factual index inventory and cumulative usage counters.

    Args:
        bloat_threshold_percent: Retained for compatibility; bloat is not inferred
        min_size_mb: Minimum index size to monitor (default: 1MB)

    Returns:
        dict with factual health metrics for all indexes
    """
    if not is_system_enabled():
        logger.info("Index health monitoring skipped: system is disabled")
        return {"status": "disabled", "indexes": []}

    with get_cursor() as cursor:
        # PostgreSQL does not expose a trustworthy generic bloat percentage in
        # pg_stat_user_indexes. Keep this inventory factual and let an explicit
        # pgstattuple/operator workflow measure physical bloat when needed.
        cursor.execute(
            """
                SELECT
                    stats.schemaname,
                    stats.relname AS tablename,
                    stats.indexrelname AS indexname,
                    stats.idx_scan AS index_scans,
                    stats.idx_tup_read AS tuples_read,
                    stats.idx_tup_fetch AS tuples_fetched,
                    pg_relation_size(stats.indexrelid) AS index_size_bytes,
                    pg_relation_size(stats.relid) AS table_size_bytes,
                    metadata.indisvalid AS is_valid,
                    metadata.indisready AS is_ready,
                    metadata.indisunique AS is_unique,
                    metadata.indisprimary AS is_primary,
                    EXISTS (
                        SELECT 1 FROM pg_constraint constraint_meta
                        WHERE constraint_meta.conindid = stats.indexrelid
                    ) AS is_constraint_owned
                FROM pg_stat_user_indexes stats
                JOIN pg_index metadata ON metadata.indexrelid = stats.indexrelid
                WHERE stats.schemaname = 'public'
                ORDER BY stats.indexrelname
            """
        )

        indexes = cursor.fetchall()
        health_data: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "total_indexes": len(indexes),
            "indexes": [],
            "summary": {
                "bloated": 0,
                "underutilized": 0,
                "healthy": 0,
                "warning": 0,
                "total_size_mb": 0.0,
                "bloat_status": "not_measured",
            },
            "evidence": {
                "bloat_status": "not_measured",
                "bloat_threshold_percent_requested": bloat_threshold_percent,
                "note": (
                    "Size, validity, readiness, and cumulative scan counters are factual; "
                    "physical bloat requires a separate measured workflow."
                ),
            },
        }

        for idx in indexes:
            index_name = idx["indexname"]
            table_name = idx["tablename"]
            index_size_bytes = idx.get("index_size_bytes", 0) or 0
            table_size_bytes = idx.get("table_size_bytes", 0) or 0
            index_scans = idx.get("index_scans", 0) or 0
            index_size_mb = index_size_bytes / (1024 * 1024)

            # Skip small indexes
            if index_size_mb < min_size_mb:
                continue

            is_valid = bool(idx.get("is_valid", False))
            is_ready = bool(idx.get("is_ready", False))
            health_status = "healthy" if is_valid and is_ready else "warning"
            if health_status == "healthy":
                summary = health_data["summary"]
                if isinstance(summary, dict):
                    summary["healthy"] = summary.get("healthy", 0) + 1
            else:
                summary = health_data["summary"]
                if isinstance(summary, dict):
                    summary["warning"] = summary.get("warning", 0) + 1

            index_health = {
                "indexname": index_name,
                "tablename": table_name,
                "size_mb": round(index_size_mb, 2),
                "size_bytes": index_size_bytes,
                "table_size_mb": round(table_size_bytes / (1024 * 1024), 2),
                "index_scans": index_scans,
                "tuples_read": idx.get("tuples_read", 0) or 0,
                "tuples_fetched": idx.get("tuples_fetched", 0) or 0,
                "is_valid": is_valid,
                "is_ready": is_ready,
                "is_unique": bool(idx.get("is_unique", False)),
                "is_primary": bool(idx.get("is_primary", False)),
                "is_constraint_owned": bool(idx.get("is_constraint_owned", False)),
                "bloat_status": "not_measured",
                "bloat_percent": None,
                "last_used_at": None,
                "health_status": health_status,
                "is_bloated": False,
                "is_underutilized": False,
            }

            indexes_list = health_data["indexes"]
            if isinstance(indexes_list, list):
                indexes_list.append(index_health)
            summary = health_data["summary"]
            if isinstance(summary, dict):
                summary["total_size_mb"] = summary.get("total_size_mb", 0.0) + index_size_mb

        summary = health_data["summary"]
        if isinstance(summary, dict):
            summary["total_size_mb"] = round(summary.get("total_size_mb", 0.0), 2)

        summary = health_data.get("summary", {})
        healthy = summary.get("healthy", 0) if isinstance(summary, dict) else 0
        warning = summary.get("warning", 0) if isinstance(summary, dict) else 0
        logger.info(
            f"Index inventory: {healthy} valid/ready, {warning} requiring catalog review; "
            "bloat not measured"
        )

        return health_data


def find_bloated_indexes(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Return no automatic candidates because this module does not measure bloat.

    Args:
        bloat_threshold_percent: Bloat threshold (default: 20%)
        min_size_mb: Minimum index size to consider (default: 10MB)

    Returns:
        List of bloated indexes
    """
    _ = (bloat_threshold_percent, min_size_mb)
    logger.info("Automatic bloat candidates unavailable: physical bloat is not measured")
    return []


def reindex_bloated_indexes(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 10.0,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """
    Keep the legacy REINDEX entry point advisory-only.

    Args:
        bloat_threshold_percent: Bloat threshold (default: 20%)
        min_size_mb: Minimum index size to consider (default: 10MB)
        dry_run: If True, only report what would be reindexed

    Returns:
        List of indexes reindexed (or would be reindexed)
    """
    if not dry_run:
        raise RuntimeError(
            "automatic_reindex_disabled: use an explicit operator-run, autocommit maintenance "
            "workflow after measuring physical bloat"
        )
    if not is_system_enabled():
        logger.info("Index reindexing skipped: system is disabled")
        return []

    bloated = find_bloated_indexes(
        bloat_threshold_percent=bloat_threshold_percent, min_size_mb=min_size_mb
    )

    if not bloated:
        logger.info("No bloated indexes found")
        return []

    return []
