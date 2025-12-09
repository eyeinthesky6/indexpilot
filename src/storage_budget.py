# mypy: ignore-errors
"""Storage budget management for indexes"""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.db import get_cursor
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_storage_budget_enabled() -> bool:
    """Check if storage budget management is enabled"""
    return _config_loader.get_bool("features.storage_budget.enabled", True)


def get_storage_budget_config() -> dict[str, Any]:
    """Get storage budget configuration"""
    return {
        "enabled": is_storage_budget_enabled(),
        "max_storage_per_tenant_mb": _config_loader.get_float(
            "features.storage_budget.max_storage_per_tenant_mb", 1000.0
        ),
        "max_storage_total_mb": _config_loader.get_float(
            "features.storage_budget.max_storage_total_mb", 10000.0
        ),
        "warn_threshold_pct": _config_loader.get_float(
            "features.storage_budget.warn_threshold_pct", 80.0
        ),
    }


def get_index_storage_usage(
    tenant_id: int | None = None, table_name: str | None = None
) -> dict[str, Any]:
    """
    Get current index storage usage.

    Args:
        tenant_id: Tenant ID (None = all tenants)
        table_name: Table name (None = all tables)

    Returns:
        dict with storage usage statistics
    """
    if not is_storage_budget_enabled():
        return {"skipped": True, "reason": "storage_budget_disabled"}

    result: JSONDict = {
        "total_index_size_mb": 0.0,
        "total_index_size_gb": 0.0,
        "index_count": 0,
        "by_table": [],
        "by_tenant": [],
    }

    try:
        with get_cursor() as cursor:
            # Get index sizes
            if tenant_id and table_name:
                # Specific tenant and table
                query = """
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as size_pretty,
                        pg_relation_size(indexname::regclass) / (1024.0 * 1024.0) as size_mb
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = %s
                    ORDER BY pg_relation_size(indexname::regclass) DESC
                """
                cursor.execute(query, (table_name,))
            elif tenant_id:
                # All tables for specific tenant
                # Note: This assumes tenant_id is in table name or we track it separately
                # For now, get all indexes
                query = """
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as size_pretty,
                        pg_relation_size(indexname::regclass) / (1024.0 * 1024.0) as size_mb
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, pg_relation_size(indexname::regclass) DESC
                """
                cursor.execute(query)
            else:
                # All indexes
                query = """
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as size_pretty,
                        pg_relation_size(indexname::regclass) / (1024.0 * 1024.0) as size_mb
                    FROM pg_indexes
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY tablename, pg_relation_size(indexname::regclass) DESC
                """
                cursor.execute(query)

            indexes = cursor.fetchall()

            total_size_mb = 0.0
            table_sizes: dict[str, dict[str, Any]] = {}

            for idx in indexes:
                size_mb = float(idx["size_mb"]) if idx["size_mb"] else 0.0
                total_size_mb += size_mb

                table_key = f"{idx['schemaname']}.{idx['tablename']}"
                if table_key not in table_sizes:
                    table_sizes[table_key] = {
                        "table": table_key,
                        "index_count": 0,
                        "total_size_mb": 0.0,
                        "indexes": [],
                    }

                table_sizes[table_key]["index_count"] += 1
                table_sizes[table_key]["total_size_mb"] += size_mb
                table_sizes[table_key]["indexes"].append(
                    {
                        "index_name": idx["indexname"],
                        "size_mb": size_mb,
                        "size_pretty": idx["size_pretty"],
                    }
                )

            result["total_index_size_mb"] = total_size_mb
            result["total_index_size_gb"] = total_size_mb / 1024.0
            result["index_count"] = len(indexes)
            result["by_table"] = list(table_sizes.values())

    except Exception as e:
        logger.error(f"Failed to get index storage usage: {e}")
        result["error"] = str(e)

    return result


def check_storage_budget(
    tenant_id: int | None = None,
    estimated_index_size_mb: float = 0.0,
) -> dict[str, Any]:
    """
    Check if creating an index would exceed storage budget.

    Args:
        tenant_id: Tenant ID (None = check total budget)
        estimated_index_size_mb: Estimated size of new index in MB

    Returns:
        dict with budget check results
    """
    if not is_storage_budget_enabled():
        return {"allowed": True, "reason": "storage_budget_disabled"}

    config = get_storage_budget_config()
    current_usage = get_index_storage_usage(tenant_id=tenant_id)

    if current_usage.get("skipped"):
        return {"allowed": True, "reason": "could_not_check_budget"}

    current_size_mb = current_usage.get("total_index_size_mb", 0.0)
    new_size_mb = current_size_mb + estimated_index_size_mb

    if tenant_id:
        # Per-tenant budget
        max_storage = config.get("max_storage_per_tenant_mb", 1000.0)
        budget_type = "per_tenant"
    else:
        # Total budget
        max_storage = config.get("max_storage_total_mb", 10000.0)
        budget_type = "total"

    warn_threshold = config.get("warn_threshold_pct", 80.0) / 100.0
    warn_size = max_storage * warn_threshold

    allowed = new_size_mb <= max_storage
    warning = new_size_mb > warn_size

    result: JSONDict = {
        "allowed": allowed,
        "warning": warning,
        "budget_type": budget_type,
        "current_size_mb": current_size_mb,
        "estimated_new_size_mb": new_size_mb,
        "max_storage_mb": max_storage,
        "warn_threshold_mb": warn_size,
        "usage_pct": (new_size_mb / max_storage * 100.0) if max_storage > 0 else 0.0,
    }

    if not allowed:
        result[
            "reason"
        ] = f"Would exceed {budget_type} storage budget ({new_size_mb:.1f}MB > {max_storage:.1f}MB)"
    elif warning:
        result[
            "reason"
        ] = f"Approaching {budget_type} storage budget ({new_size_mb:.1f}MB > {warn_size:.1f}MB threshold)"
    else:
        result["reason"] = "Within storage budget"

    return result


def get_storage_budget_status() -> dict[str, Any]:
    """
    Get current storage budget status.

    Returns:
        dict with budget status
    """
    config = get_storage_budget_config()
    total_usage = get_index_storage_usage()

    if total_usage.get("skipped"):
        return {"enabled": False, "reason": total_usage.get("reason")}

    total_size_mb = total_usage.get("total_index_size_mb", 0.0)
    max_total = config.get("max_storage_total_mb", 10000.0)
    warn_threshold = config.get("warn_threshold_pct", 80.0) / 100.0

    return {
        "enabled": True,
        "total_size_mb": total_size_mb,
        "max_storage_mb": max_total,
        "usage_pct": (total_size_mb / max_total * 100.0) if max_total > 0 else 0.0,
        "warn_threshold_pct": warn_threshold * 100.0,
        "within_budget": total_size_mb <= max_total,
        "approaching_limit": total_size_mb > (max_total * warn_threshold),
        "index_count": total_usage.get("index_count", 0),
    }
