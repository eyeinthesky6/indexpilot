"""Per-tenant configuration support"""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_per_tenant_config_enabled() -> bool:
    """Check if per-tenant configuration is enabled"""
    return _config_loader.get_bool("features.per_tenant_config.enabled", True)


def get_tenant_config(tenant_id: int) -> dict[str, Any]:
    """
    Get configuration for a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        dict with tenant-specific configuration
    """
    if not is_per_tenant_config_enabled():
        return {}

    tenant_config: JSONDict = {}

    try:
        with get_connection() as conn:
            from psycopg2.extras import RealDictCursor

            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check if tenant_config table exists
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'tenant_config'
                    )
                    """
                )
                from src.db import safe_get_row_value

                row = cursor.fetchone()
                table_exists = bool(
                    safe_get_row_value(row, 0, False) or safe_get_row_value(row, "exists", False)
                )

                if table_exists:
                    cursor.execute(
                        """
                        SELECT config_key, config_value, config_type
                        FROM tenant_config
                        WHERE tenant_id = %s
                        ORDER BY config_key
                        """,
                        (tenant_id,),
                    )
                    results = cursor.fetchall()

                    for row in results:
                        key = row["config_key"]
                        value = row["config_value"]
                        config_type = row.get("config_type", "string")

                        # Convert value based on type
                        if config_type == "int":
                            value = int(value) if value else 0
                        elif config_type == "float":
                            value = float(value) if value else 0.0
                        elif config_type == "bool":
                            value = str(value).lower() in ("true", "1", "yes")
                        elif config_type == "json":
                            import json

                            value = json.loads(value) if value else {}

                        tenant_config[key] = value

            finally:
                cursor.close()

    except Exception as e:
        logger.debug(f"Could not get tenant config for tenant {tenant_id}: {e}")

    return tenant_config


def set_tenant_config(
    tenant_id: int, config_key: str, config_value: Any, config_type: str = "string"
) -> bool:
    """
    Set a configuration value for a tenant.

    Args:
        tenant_id: Tenant ID
        config_key: Configuration key
        config_value: Configuration value
        config_type: Type of value (string, int, float, bool, json)

    Returns:
        True if successful
    """
    if not is_per_tenant_config_enabled():
        return False

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Ensure tenant_config table exists
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tenant_config (
                        tenant_id INTEGER NOT NULL,
                        config_key VARCHAR(255) NOT NULL,
                        config_value TEXT,
                        config_type VARCHAR(50) DEFAULT 'string',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tenant_id, config_key)
                    )
                    """
                )

                # Convert value to string for storage
                if config_type == "json":
                    import json

                    value_str = json.dumps(config_value)
                else:
                    value_str = str(config_value)

                # Upsert config value
                cursor.execute(
                    """
                    INSERT INTO tenant_config (tenant_id, config_key, config_value, config_type, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (tenant_id, config_key)
                    DO UPDATE SET
                        config_value = EXCLUDED.config_value,
                        config_type = EXCLUDED.config_type,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (tenant_id, config_key, value_str, config_type),
                )

                conn.commit()
                return True

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to set tenant config: {e}")
                return False
            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to set tenant config for tenant {tenant_id}: {e}")
        return False


def get_tenant_index_config(tenant_id: int) -> dict[str, Any]:
    """
    Get index-related configuration for a tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        dict with tenant index configuration
    """
    tenant_config = get_tenant_config(tenant_id)

    # Default tenant config
    default_config = {
        "max_indexes_per_table": _config_loader.get_int(
            "features.auto_indexer.max_indexes_per_table", 10
        ),
        "storage_budget_mb": _config_loader.get_float(
            "features.storage_budget.max_storage_per_tenant_mb", 1000.0
        ),
        "min_query_threshold": _config_loader.get_int(
            "features.auto_indexer.min_queries_per_hour", 100
        ),
        "index_type_preference": "auto",  # auto, btree, hash, gin, gist
        "workload_aware": True,
    }

    # Override with tenant-specific config
    if tenant_config:
        if "max_indexes_per_table" in tenant_config:
            default_config["max_indexes_per_table"] = tenant_config["max_indexes_per_table"]
        if "storage_budget_mb" in tenant_config:
            default_config["storage_budget_mb"] = tenant_config["storage_budget_mb"]
        if "min_query_threshold" in tenant_config:
            default_config["min_query_threshold"] = tenant_config["min_query_threshold"]
        if "index_type_preference" in tenant_config:
            default_config["index_type_preference"] = tenant_config["index_type_preference"]
        if "workload_aware" in tenant_config:
            default_config["workload_aware"] = tenant_config["workload_aware"]

    return default_config


def get_tenant_storage_budget(tenant_id: int) -> float:
    """
    Get storage budget for a tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        Storage budget in MB
    """
    tenant_config = get_tenant_index_config(tenant_id)
    return tenant_config.get("storage_budget_mb", 1000.0)


def get_tenant_maintenance_window(tenant_id: int) -> dict[str, Any] | None:
    """
    Get maintenance window configuration for a tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        dict with maintenance window config or None for default
    """
    tenant_config = get_tenant_config(tenant_id)

    if "maintenance_window" in tenant_config:
        return tenant_config["maintenance_window"]

    return None
