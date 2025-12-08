"""Safe live schema evolution with validation and impact analysis

This module provides safe schema evolution capabilities with:
- Pre-flight validation and impact analysis
- Automatic rollback support
- Thread-safe caching
- Comprehensive error handling
- Full audit trail integration

Key Functions:
- safe_add_column(): Safely add columns with validation
- safe_drop_column(): Safely drop columns with dependency checking
- safe_alter_column_type(): Safely change column types
- safe_rename_column(): Safely rename columns
- preview_schema_change(): Preview changes without executing
- analyze_schema_change_impact(): Analyze impact before changes
- validate_schema_change(): Validate changes before execution
"""

import logging
import threading
from datetime import datetime, timedelta

from psycopg2 import sql
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor

from src.audit import log_audit_event
from src.db import get_connection
from src.resilience import safe_database_operation
from src.type_definitions import JSONDict
from src.validation import (
    clear_validation_cache,
    is_valid_identifier,
    validate_field_name,
    validate_table_name,
)

logger = logging.getLogger(__name__)

# Load config for schema evolution toggle
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def is_schema_evolution_enabled() -> bool:
    """Check if schema evolution features are enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("operational.schema_evolution.enabled", True)


# Cache for impact analysis results (5 minute TTL) - thread-safe
_impact_cache: dict[str, tuple[datetime, JSONDict]] = {}
_cache_lock = threading.Lock()
_cache_ttl = timedelta(minutes=5)


def clear_impact_cache(table_name: str | None = None, field_name: str | None = None):
    """
    Clear impact analysis cache.

    Args:
        table_name: If provided, clear only entries for this table
        field_name: If provided, clear only entries for this field
    """
    with _cache_lock:
        if table_name and field_name:
            # Clear specific table/field entries
            keys_to_remove = [key for key in _impact_cache if f"{table_name}:{field_name}" in key]
            for key in keys_to_remove:
                _impact_cache.pop(key, None)
        elif table_name:
            # Clear all entries for this table
            keys_to_remove = [key for key in _impact_cache if key.startswith(f"{table_name}:")]
            for key in keys_to_remove:
                _impact_cache.pop(key, None)
        else:
            # Clear all cache
            _impact_cache.clear()
        logger.debug(f"Cleared impact cache (table={table_name}, field={field_name})")


def analyze_schema_change_impact(
    table_name: str,
    field_name: str | None = None,
    change_type: str = "ALTER_TABLE",
    conn: connection | None = None,
    use_cache: bool = True,
) -> JSONDict:
    """
    Analyze impact of a schema change before execution.

    Identifies:
    - Queries that use the table/field
    - Indexes that depend on the field
    - Expression profiles that reference the field
    - Foreign key constraints that depend on the field
    - Estimated query count impact

    Args:
        table_name: Table being modified
        field_name: Field being modified (if applicable)
        change_type: Type of change (ADD_COLUMN, DROP_COLUMN, ALTER_TABLE, etc.)
        conn: Optional database connection to reuse
        use_cache: Whether to use cached results (default: True)

    Returns:
        dict with impact analysis including:
        - affected_queries: Number of queries using this table/field
        - affected_indexes: List of dependent indexes
        - affected_expression_profiles: Number of expression profiles
        - foreign_key_constraints: List of FK constraints
        - warnings: List of warnings
        - errors: List of blocking errors
    """
    # Check cache first (thread-safe)
    if use_cache:
        cache_key = f"{table_name}:{field_name}:{change_type}"
        with _cache_lock:
            if cache_key in _impact_cache:
                cached_time, cached_result = _impact_cache[cache_key]
                if datetime.now() - cached_time < _cache_ttl:
                    logger.debug(f"Using cached impact analysis for {cache_key}")
                    return cached_result.copy()  # Return copy to prevent mutation

    table_name = validate_table_name(table_name)
    if field_name:
        # For ADD_COLUMN the field may not exist yet in genome_catalog.
        # Allow preview/impact analysis for new columns as long as the
        # identifier is valid. For destructive operations validate the
        # field against genome_catalog as before.
        if change_type == "ADD_COLUMN":
            if not is_valid_identifier(field_name):
                raise ValueError(f"Invalid field name format: {field_name}")
            # keep the supplied field_name (do not validate against genome_catalog)
        else:
            field_name = validate_field_name(field_name, table_name)

    impact: JSONDict = {
        "table_name": table_name,
        "field_name": field_name,
        "change_type": change_type,
        "affected_queries": 0,
        "affected_indexes": [],
        "affected_expression_profiles": 0,
        "foreign_key_constraints": [],
        "warnings": [],
        "errors": [],
    }

    def _analyze_impact(connection_obj: connection) -> JSONDict:
        """Internal function to analyze impact using provided connection"""
        cursor = connection_obj.cursor(cursor_factory=RealDictCursor)
        try:
            # Find queries that use this table/field
            if field_name:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as query_count,
                        COUNT(DISTINCT tenant_id) as tenant_count,
                        AVG(duration_ms) as avg_duration_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms
                    FROM query_stats
                    WHERE table_name = %s
                      AND field_name = %s
                      AND created_at >= NOW() - INTERVAL '7 days'
                """,
                    (table_name, field_name),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as query_count,
                        COUNT(DISTINCT tenant_id) as tenant_count,
                        AVG(duration_ms) as avg_duration_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms
                    FROM query_stats
                    WHERE table_name = %s
                      AND created_at >= NOW() - INTERVAL '7 days'
                """,
                    (table_name,),
                )

            query_stats = cursor.fetchone()
            if query_stats:
                impact["affected_queries"] = query_stats["query_count"] or 0
                impact["query_stats"] = {
                    "tenant_count": query_stats["tenant_count"] or 0,
                    "avg_duration_ms": float(query_stats["avg_duration_ms"] or 0),
                    "p95_duration_ms": float(query_stats["p95_duration_ms"] or 0),
                }

            # Find indexes that use this field (using pg_depend for accurate detection)
            if field_name:
                cursor.execute(
                    """
                    SELECT DISTINCT
                        i.indexname,
                        i.tablename,
                        i.indexdef
                    FROM pg_indexes i
                    JOIN pg_class ic ON ic.relname = i.indexname
                    JOIN pg_index idx ON idx.indexrelid = ic.oid
                    JOIN pg_attribute a ON a.attrelid = idx.indrelid
                        AND a.attnum = ANY(idx.indkey)
                    JOIN pg_class t ON t.oid = a.attrelid
                    WHERE t.relname = %s
                      AND a.attname = %s
                      AND i.schemaname = 'public'
                      AND i.tablename = %s
                """,
                    (table_name, field_name, table_name),
                )

                indexes = cursor.fetchall()
                impact["affected_indexes"] = [
                    {
                        "name": idx["indexname"],
                        "table": idx["tablename"],
                        "definition": idx["indexdef"],
                    }
                    for idx in indexes
                ]

                if change_type == "DROP_COLUMN" and indexes:
                    errors_val = impact.get("errors", [])
                    if isinstance(errors_val, list):
                        errors_val.append(
                            f"Cannot drop column {field_name}: {len(indexes)} indexes depend on it"
                        )
                        impact["errors"] = errors_val

            # Find expression profiles that reference this field
            if field_name:
                cursor.execute(
                    """
                    SELECT COUNT(*) as profile_count
                    FROM expression_profile
                    WHERE table_name = %s
                      AND field_name = %s
                """,
                    (table_name, field_name),
                )

                profile_result = cursor.fetchone()
                if profile_result:
                    impact["affected_expression_profiles"] = profile_result["profile_count"] or 0

            # Check for foreign key constraints that depend on this column
            if field_name:
                cursor.execute(
                    """
                    SELECT
                        tc.constraint_name,
                        tc.table_name as dependent_table,
                        kcu.column_name as dependent_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND ccu.table_name = %s
                      AND ccu.column_name = %s
                      AND tc.table_schema = 'public'
                """,
                    (table_name, field_name),
                )

                fk_constraints = cursor.fetchall()
                if fk_constraints:
                    impact["foreign_key_constraints"] = [
                        {
                            "constraint_name": fk["constraint_name"],
                            "dependent_table": fk["dependent_table"],
                            "dependent_column": fk["dependent_column"],
                        }
                        for fk in fk_constraints
                    ]
                    if change_type == "DROP_COLUMN":
                        errors_val = impact.get("errors", [])
                        if isinstance(errors_val, list):
                            errors_val.append(
                                f"Cannot drop column {field_name}: {len(fk_constraints)} foreign key constraint(s) depend on it"
                            )
                            impact["errors"] = errors_val

            # Check if field exists in genome_catalog
            if field_name:
                cursor.execute(
                    """
                    SELECT field_name, field_type, is_required, is_indexable
                    FROM genome_catalog
                    WHERE table_name = %s
                      AND field_name = %s
                """,
                    (table_name, field_name),
                )

                genome_entry = cursor.fetchone()
                if genome_entry:
                    impact["genome_catalog_entry"] = {
                        "field_type": genome_entry["field_type"],
                        "is_required": genome_entry["is_required"],
                        "is_indexable": genome_entry["is_indexable"],
                    }

            # Generate warnings
            affected_queries_val = impact.get("affected_queries", 0)
            affected_queries = affected_queries_val if isinstance(affected_queries_val, int) else 0
            if affected_queries > 1000:
                warnings_list = impact.get("warnings", [])
                if isinstance(warnings_list, list):
                    warnings_list.append(
                        f"High query volume ({affected_queries} queries in last 7 days). "
                        "Schema change may impact performance."
                    )
                    impact["warnings"] = warnings_list

            affected_indexes_val = impact.get("affected_indexes")
            if (
                affected_indexes_val
                and isinstance(affected_indexes_val, list)
                and len(affected_indexes_val) > 0
                and change_type in ("DROP_COLUMN", "ALTER_TABLE")
            ):
                warnings_list = impact.get("warnings", [])
                if isinstance(warnings_list, list):
                    warnings_list.append(
                        f"{len(affected_indexes_val)} indexes depend on this field. "
                        "Consider dropping indexes first or recreating them after change."
                    )
                    impact["warnings"] = warnings_list

            fk_constraints_val = impact.get("foreign_key_constraints")
            if (
                fk_constraints_val
                and isinstance(fk_constraints_val, list)
                and len(fk_constraints_val) > 0
                and change_type in ("DROP_COLUMN", "ALTER_TABLE")
            ):
                warnings_list = impact.get("warnings", [])
                if isinstance(warnings_list, list):
                    warnings_list.append(
                        f"{len(fk_constraints_val)} foreign key constraint(s) depend on this field. "
                        "Consider dropping constraints first or recreating them after change."
                    )
                    impact["warnings"] = warnings_list
        finally:
            cursor.close()

        return impact

    try:
        if conn is not None:
            # Reuse provided connection
            impact = _analyze_impact(conn)
        else:
            # Create new connection
            with get_connection() as new_conn:
                impact = _analyze_impact(new_conn)

        # Cache result (thread-safe)
        if use_cache:
            cache_key = f"{table_name}:{field_name}:{change_type}"
            with _cache_lock:
                _impact_cache[cache_key] = (datetime.now(), impact.copy())

    except Exception as e:
        logger.error(f"Failed to analyze schema change impact: {e}", exc_info=True)
        errors_list = impact.get("errors", [])
        if isinstance(errors_list, list):
            errors_list.append(f"Impact analysis failed: {str(e)}")
            impact["errors"] = errors_list
        # Return partial results even on error
        impact["partial_results"] = True

    return impact


def validate_schema_change(
    table_name: str,
    change_type: str,
    field_name: str | None = None,
    field_type: str | None = None,
    conn: connection | None = None,
    **_kwargs,
) -> tuple[bool, list[str], str | None]:
    """
    Validate a schema change before execution.

    Args:
        table_name: Table being modified
        change_type: Type of change (ADD_COLUMN, DROP_COLUMN, ALTER_COLUMN, etc.)
        field_name: Field name (if applicable)
        field_type: Field type (for ADD_COLUMN)
        conn: Optional database connection to reuse
        **kwargs: Additional parameters

    Returns:
        Tuple of (is_valid, list_of_errors, validated_table_name)
    """
    errors: list[str] = []
    validated_table: str | None = None

    # Validate table name (once, reuse result)
    try:
        validated_table = validate_table_name(table_name)
    except ValueError as e:
        errors.append(f"Invalid table name: {e}")
        return False, errors, None

    # Validate field name if provided (reuse validated_table)
    validated_field: str | None = None
    if field_name:
        try:
            validated_field = validate_field_name(field_name, validated_table)
        except ValueError as e:
            # For ADD_COLUMN, field might not exist yet, so be lenient
            if change_type != "ADD_COLUMN":
                errors.append(f"Invalid field name: {e}")
                return False, errors, validated_table

    # Check if table exists (reuse connection if provided)
    def _check_table_exists(connection_obj: connection) -> bool:
        cursor = connection_obj.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            """,
                (validated_table,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    try:
        if conn is not None:
            table_exists = _check_table_exists(conn)
        else:
            with get_connection() as new_conn:
                table_exists = _check_table_exists(new_conn)

        if not table_exists:
            errors.append(f"Table {validated_table} does not exist")
            return False, errors, validated_table
    except Exception as e:
        errors.append(f"Failed to check table existence: {e}")
        return False, errors, validated_table

    # Validate field type if provided
    if field_type:
        valid_types = {
            "TEXT",
            "VARCHAR",
            "CHARACTER VARYING",
            "INTEGER",
            "INT",
            "BIGINT",
            "SMALLINT",
            "NUMERIC",
            "DECIMAL",
            "REAL",
            "DOUBLE PRECISION",
            "BOOLEAN",
            "DATE",
            "TIMESTAMP",
            "TIMESTAMP WITH TIME ZONE",
            "JSON",
            "JSONB",
            "SERIAL",
            "BIGSERIAL",
        }
        if field_type.upper() not in valid_types and not any(
            field_type.upper().startswith(t) for t in ["VARCHAR", "CHARACTER", "NUMERIC", "DECIMAL"]
        ):
            errors.append(f"Invalid field type: {field_type}")

    # Check for conflicts (reuse connection if provided)
    if change_type == "ADD_COLUMN" and validated_field:

        def _check_column_exists(connection_obj: connection) -> bool:
            cursor = connection_obj.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = %s
                """,
                    (validated_table, validated_field),
                )
                return cursor.fetchone() is not None
            finally:
                cursor.close()

        try:
            if conn is not None:
                column_exists = _check_column_exists(conn)
            else:
                with get_connection() as new_conn:
                    column_exists = _check_column_exists(new_conn)

            if column_exists:
                errors.append(f"Column {validated_field} already exists in table {validated_table}")
                return False, errors, validated_table
        except Exception as e:
            errors.append(f"Failed to check column existence: {e}")

    return len(errors) == 0, errors, validated_table


def generate_rollback_plan(
    table_name: str, change_type: str, field_name: str | None = None, **kwargs
) -> JSONDict:
    """
    Generate a rollback plan for a schema change.

    Args:
        table_name: Table being modified
        change_type: Type of change
        field_name: Field name (if applicable)
        **kwargs: Additional parameters

    Returns:
        dict with rollback SQL and instructions
    """
    table_name = validate_table_name(table_name)

    rollback_plan: JSONDict = {
        "change_type": change_type,
        "table_name": table_name,
        "field_name": field_name,
        "rollback_sql": None,
        "instructions": [],
    }

    if change_type == "ADD_COLUMN" and field_name:
        # Rollback: DROP COLUMN (using sql.SQL for safety)
        rollback_plan["rollback_sql"] = str(
            sql.SQL(
                """
            ALTER TABLE {}
            DROP COLUMN IF EXISTS {}
        """
            ).format(sql.Identifier(table_name), sql.Identifier(field_name))
        )
        rollback_plan["instructions"] = [
            f"To rollback: DROP COLUMN {field_name} from {table_name}",
            "Note: This will lose all data in the column",
        ]

    elif change_type == "DROP_COLUMN" and field_name:
        # Rollback: Re-add column (but data is lost)
        field_type = kwargs.get("field_type", "TEXT")
        rollback_plan["rollback_sql"] = str(
            sql.SQL(
                """
            ALTER TABLE {}
            ADD COLUMN {} {}
        """
            ).format(sql.Identifier(table_name), sql.Identifier(field_name), sql.SQL(field_type))
        )
        rollback_plan["instructions"] = [
            f"To rollback: Re-add column {field_name} to {table_name}",
            "WARNING: Data will be lost - this only restores the column structure",
        ]

    elif change_type == "ALTER_COLUMN" and field_name:
        # Rollback: Restore previous type
        old_type = kwargs.get("old_type")
        if old_type:
            rollback_plan["rollback_sql"] = str(
                sql.SQL(
                    """
                ALTER TABLE {}
                ALTER COLUMN {} TYPE {}
            """
                ).format(sql.Identifier(table_name), sql.Identifier(field_name), sql.SQL(old_type))
            )
            rollback_plan["instructions"] = [
                f"To rollback: Restore column {field_name} type to {old_type}"
            ]

    elif change_type == "RENAME_COLUMN" and field_name:
        # Rollback: Rename back
        new_name = kwargs.get("new_name")
        if new_name:
            rollback_plan["rollback_sql"] = str(
                sql.SQL(
                    """
                ALTER TABLE {}
                RENAME COLUMN {} TO {}
            """
                ).format(
                    sql.Identifier(table_name), sql.Identifier(new_name), sql.Identifier(field_name)
                )
            )
            rollback_plan["instructions"] = [
                f"To rollback: Rename column {new_name} back to {field_name}"
            ]

    return rollback_plan


def safe_add_column(
    table_name: str,
    field_name: str,
    field_type: str,
    is_nullable: bool = True,
    default_value: str | None = None,
    tenant_id: int | None = None,
) -> JSONDict:
    """
    Safely add a column to a table with validation and impact analysis.

    Args:
        table_name: Table to modify
        field_name: Column name to add
        field_type: Column type
        is_nullable: Whether column allows NULL
        default_value: Default value for column
        tenant_id: Tenant ID (if tenant-specific change)

    Returns:
        dict with operation result including:
        - success: Whether operation succeeded
        - table_name: Validated table name
        - field_name: Validated field name
        - impact: Impact analysis results
        - rollback_plan: Generated rollback plan
        - warnings: List of warnings
    """
    # Check if schema evolution is enabled
    if not is_schema_evolution_enabled():
        raise RuntimeError(
            "Schema evolution is disabled. Enable via operational.schema_evolution.enabled in config."
        )

    # Validate change (reuse validated table name)
    is_valid, errors, validated_table = validate_schema_change(
        table_name=table_name,
        change_type="ADD_COLUMN",
        field_name=field_name,
        field_type=field_type,
    )

    if not is_valid:
        raise ValueError(f"Schema change validation failed: {', '.join(errors)}")

    # Use validated table name (guaranteed to be str if validation passed)
    if validated_table is None:
        raise ValueError("Table name validation returned None")
    table_name = validated_table

    # Analyze impact (reuse connection if available)
    impact = analyze_schema_change_impact(
        table_name=table_name, field_name=field_name, change_type="ADD_COLUMN", use_cache=True
    )

    # Generate rollback plan
    rollback_plan = generate_rollback_plan(
        table_name=table_name,
        change_type="ADD_COLUMN",
        field_name=field_name,
        field_type=field_type,
    )

    # Check for blocking errors
    errors_list = impact.get("errors", [])
    if errors_list and isinstance(errors_list, list) and len(errors_list) > 0:
        error_messages = [str(e) for e in errors_list if isinstance(e, str)]
        if error_messages:
            raise ValueError(f"Cannot add column: {', '.join(error_messages)}")

    # Build ALTER TABLE SQL (table_name already validated)
    # For ADD_COLUMN allow new valid identifiers even if not present in genome_catalog
    if not is_valid_identifier(field_name):
        raise ValueError(f"Invalid field name format: {field_name}")

    not_null = "NOT NULL" if not is_nullable else ""
    default = f"DEFAULT {default_value}" if default_value else ""

    alter_sql = sql.SQL(
        """
        ALTER TABLE {}
        ADD COLUMN {} {} {}
    """
    ).format(
        sql.Identifier(table_name),
        sql.Identifier(field_name),
        sql.SQL(field_type),
        sql.SQL(f"{not_null} {default}".strip()),
    )

    result: JSONDict = {
        "success": False,
        "table_name": table_name,
        "field_name": field_name,
        "impact": impact,
        "rollback_plan": rollback_plan,
        "warnings": impact["warnings"],
    }

    try:
        with safe_database_operation("add_column", table_name, rollback_on_failure=True) as conn:
            cursor = conn.cursor()
            try:
                # Execute ALTER TABLE
                cursor.execute(alter_sql)

                # Update genome_catalog
                cursor.execute(
                    """
                    INSERT INTO genome_catalog
                    (table_name, field_name, field_type, is_required, is_indexable, default_expression)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (table_name, field_name)
                    DO UPDATE SET
                        field_type = EXCLUDED.field_type,
                        is_required = EXCLUDED.is_required,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (table_name, field_name, field_type, not is_nullable, True, True),
                )
                # Commit is handled by get_connection() context manager

                # Clear validation cache
                clear_validation_cache()

                # Clear impact cache for this table/field
                clear_impact_cache(table_name, field_name)

                # Log to audit trail
                log_audit_event(
                    "ADD_COLUMN",
                    tenant_id=tenant_id,
                    table_name=table_name,
                    field_name=field_name,
                    details={
                        "field_type": field_type,
                        "is_nullable": is_nullable,
                        "default_value": default_value,
                        "impact_analysis": impact,
                        "rollback_sql": rollback_plan["rollback_sql"],
                    },
                    severity="info",
                )

                result["success"] = True
                logger.info(f"Successfully added column {field_name} to {table_name}")

            except Exception as e:
                logger.error(
                    f"Failed to add column {field_name} to {table_name}: {e}", exc_info=True
                )
                result["error"] = str(e)
                result["error_type"] = type(e).__name__
                raise
            finally:
                cursor.close()

    except Exception as e:
        if "error" not in result:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
        raise

    return result


def safe_drop_column(
    table_name: str, field_name: str, tenant_id: int | None = None, force: bool = False
) -> JSONDict:
    """
    Safely drop a column with validation and impact analysis.

    Args:
        table_name: Table to modify
        field_name: Column name to drop
        tenant_id: Tenant ID (if tenant-specific change)
        force: If True, drop even if indexes depend on it (drops indexes first)

    Returns:
        dict with operation result including:
        - success: Whether operation succeeded
        - dropped_indexes: List of indexes that were dropped (if force=True)
        - impact: Impact analysis results
        - rollback_plan: Generated rollback plan
        - warnings: List of warnings
    """
    # Check if schema evolution is enabled
    if not is_schema_evolution_enabled():
        raise RuntimeError(
            "Schema evolution is disabled. Enable via operational.schema_evolution.enabled in config."
        )

    # Validate change (reuse validated table name)
    is_valid, errors, validated_table = validate_schema_change(
        table_name=table_name, change_type="DROP_COLUMN", field_name=field_name
    )

    if not is_valid:
        raise ValueError(f"Schema change validation failed: {', '.join(errors)}")

    # Use validated table name (guaranteed to be str if validation passed)
    if validated_table is None:
        raise ValueError("Table name validation returned None")
    table_name = validated_table

    # Analyze impact (reuse connection if available)
    impact = analyze_schema_change_impact(
        table_name=table_name, field_name=field_name, change_type="DROP_COLUMN", use_cache=True
    )

    # Check for blocking errors
    errors_val = impact.get("errors", [])
    if errors_val and isinstance(errors_val, list) and len(errors_val) > 0 and not force:
        errors_str = [str(e) for e in errors_val if isinstance(e, str)]
        raise ValueError(f"Cannot drop column: {', '.join(errors_str)}")

    # Get field type for rollback plan
    field_type = None
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = %s
                """,
                    (table_name, field_name),
                )
                db_result = cursor.fetchone()
                if db_result:
                    field_type = db_result["data_type"]
            finally:
                cursor.close()
    except Exception:
        pass

    # Generate rollback plan
    rollback_plan = generate_rollback_plan(
        table_name=table_name,
        change_type="DROP_COLUMN",
        field_name=field_name,
        field_type=field_type,
    )

    # table_name already validated, just validate field_name
    field_name = validate_field_name(field_name, table_name)

    result: JSONDict = {
        "success": False,
        "table_name": table_name,
        "field_name": field_name,
        "impact": impact,
        "rollback_plan": rollback_plan,
        "warnings": impact["warnings"],
        "dropped_indexes": [],
    }

    try:
        with safe_database_operation("drop_column", table_name, rollback_on_failure=True) as conn:
            cursor = conn.cursor()
            try:
                # Drop dependent indexes if force=True
                affected_indexes_val = impact.get("affected_indexes", [])
                if force and affected_indexes_val and isinstance(affected_indexes_val, list):
                    dropped_indexes_list = result.get("dropped_indexes", [])
                    if not isinstance(dropped_indexes_list, list):
                        dropped_indexes_list = []
                        result["dropped_indexes"] = dropped_indexes_list
                    for idx in affected_indexes_val:
                        if isinstance(idx, dict):
                            idx_name_val = idx.get("name")
                            if isinstance(idx_name_val, str):
                                try:
                                    drop_index_sql = sql.SQL("DROP INDEX IF EXISTS {}").format(
                                        sql.Identifier(idx_name_val)
                                    )
                                    cursor.execute(drop_index_sql)
                                    dropped_indexes_list.append(idx_name_val)
                                    logger.info(f"Dropped dependent index: {idx_name_val}")
                                except Exception as e:
                                    logger.warning(f"Failed to drop index {idx_name_val}: {e}")
                    result["dropped_indexes"] = dropped_indexes_list

                # Execute DROP COLUMN
                drop_sql = sql.SQL(
                    """
                    ALTER TABLE {}
                    DROP COLUMN IF EXISTS {}
                """
                ).format(sql.Identifier(table_name), sql.Identifier(field_name))
                cursor.execute(drop_sql)

                # Remove from genome_catalog
                cursor.execute(
                    """
                    DELETE FROM genome_catalog
                    WHERE table_name = %s AND field_name = %s
                """,
                    (table_name, field_name),
                )
                # Commit is handled by get_connection() context manager

                # Clear validation cache
                clear_validation_cache()

                # Clear impact cache for this table/field
                clear_impact_cache(table_name, field_name)

                # Log to audit trail
                log_audit_event(
                    "DROP_COLUMN",
                    tenant_id=tenant_id,
                    table_name=table_name,
                    field_name=field_name,
                    details={
                        "field_type": field_type,
                        "impact_analysis": impact,
                        "rollback_sql": rollback_plan["rollback_sql"],
                        "dropped_indexes": result["dropped_indexes"],
                        "force": force,
                    },
                    severity="warning",
                )

                result["success"] = True
                logger.info(f"Successfully dropped column {field_name} from {table_name}")

            except Exception as e:
                logger.error(
                    f"Failed to drop column {field_name} from {table_name}: {e}", exc_info=True
                )
                result["error"] = str(e)
                result["error_type"] = type(e).__name__
                raise
            finally:
                cursor.close()

    except Exception as e:
        if "error" not in result:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
        raise

    return result


def preview_schema_change(
    table_name: str,
    change_type: str,
    field_name: str | None = None,
    conn: connection | None = None,
    **kwargs,
) -> JSONDict:
    """
    Preview a schema change without executing it.

    Returns impact analysis and validation results.

    Args:
        table_name: Table to modify
        change_type: Type of change
        field_name: Field name (if applicable)
        conn: Optional database connection to reuse
        **kwargs: Additional parameters

    Returns:
        dict with preview information including:
        - valid: Whether validation passed
        - validation_errors: List of validation errors
        - impact: Impact analysis results
        - rollback_plan: Generated rollback plan
        - can_proceed: Whether change can be executed safely
        - warnings: List of warnings
    """
    try:
        # Validate (reuse validated table name and connection)
        is_valid, errors, validated_table = validate_schema_change(
            table_name=table_name,
            change_type=change_type,
            field_name=field_name,
            conn=conn,
            **kwargs,
        )

        # Use validated table name
        if validated_table:
            table_name = validated_table

        # Analyze impact (reuse connection if provided)
        impact = analyze_schema_change_impact(
            table_name=table_name,
            field_name=field_name,
            change_type=change_type,
            conn=conn,
            use_cache=True,
        )

        # Generate rollback plan
        rollback_plan = generate_rollback_plan(
            table_name=table_name, change_type=change_type, field_name=field_name, **kwargs
        )

        errors_val = impact.get("errors", [])
        errors_list = errors_val if isinstance(errors_val, list) else []
        warnings_val = impact.get("warnings", [])
        warnings_list = warnings_val if isinstance(warnings_val, list) else []

        return {
            "valid": is_valid,
            "validation_errors": errors,  # type: ignore[dict-item]
            "impact": impact,
            "rollback_plan": rollback_plan,
            "can_proceed": is_valid and len(errors_list) == 0,
            "warnings": warnings_list,
        }
    except Exception as e:
        logger.error(f"Failed to preview schema change: {e}", exc_info=True)
        return {
            "valid": False,
            "validation_errors": [str(e)],
            "impact": {"errors": [str(e)], "warnings": []},
            "rollback_plan": {},
            "can_proceed": False,
            "warnings": [],
        }


def safe_alter_column_type(
    table_name: str,
    field_name: str,
    new_type: str,
    using_clause: str | None = None,
    tenant_id: int | None = None,
) -> JSONDict:
    """
    Safely alter column type with validation and impact analysis.

    Args:
        table_name: Table to modify
        field_name: Column name to alter
        new_type: New column type
        using_clause: Optional USING clause for type conversion (e.g., "field_name::integer")
        tenant_id: Tenant ID (if tenant-specific change)

    Returns:
        dict with operation result including:
        - success: Whether operation succeeded
        - old_type: Previous column type
        - new_type: New column type
        - impact: Impact analysis results
        - rollback_plan: Generated rollback plan
        - warnings: List of warnings
    """
    # Check if schema evolution is enabled
    if not is_schema_evolution_enabled():
        raise RuntimeError(
            "Schema evolution is disabled. Enable via operational.schema_evolution.enabled in config."
        )

    # Validate change
    is_valid, errors, validated_table = validate_schema_change(
        table_name=table_name,
        change_type="ALTER_COLUMN",
        field_name=field_name,
        field_type=new_type,
    )

    if not is_valid:
        raise ValueError(f"Schema change validation failed: {', '.join(errors)}")

    # Use validated table name (guaranteed to be str if validation passed)
    if validated_table is None:
        raise ValueError("Table name validation returned None")
    table_name = validated_table

    # Get current type for rollback
    old_type = None
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = %s
                """,
                    (table_name, field_name),
                )
                db_result = cursor.fetchone()
                if db_result:
                    old_type = db_result["data_type"]
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Could not get current column type: {e}")

    # Analyze impact (reuse connection if available)
    impact = analyze_schema_change_impact(
        table_name=table_name, field_name=field_name, change_type="ALTER_COLUMN", use_cache=True
    )

    # Generate rollback plan
    rollback_plan = generate_rollback_plan(
        table_name=table_name, change_type="ALTER_COLUMN", field_name=field_name, old_type=old_type
    )

    # Check for blocking errors
    errors_val = impact.get("errors", [])
    if errors_val and isinstance(errors_val, list) and len(errors_val) > 0:
        errors_str = [str(e) for e in errors_val if isinstance(e, str)]
        raise ValueError(f"Cannot alter column type: {', '.join(errors_str)}")

    # Build ALTER TABLE SQL
    field_name = validate_field_name(field_name, table_name)

    using_sql = f" USING {using_clause}" if using_clause else ""

    alter_sql = sql.SQL(
        """
        ALTER TABLE {}
        ALTER COLUMN {} TYPE {} {}
    """
    ).format(
        sql.Identifier(table_name),
        sql.Identifier(field_name),
        sql.SQL(new_type),
        sql.SQL(using_sql),
    )

    result: JSONDict = {
        "success": False,
        "table_name": table_name,
        "field_name": field_name,
        "old_type": old_type,
        "new_type": new_type,
        "impact": impact,
        "rollback_plan": rollback_plan,
        "warnings": impact["warnings"],
    }

    try:
        with safe_database_operation(
            "alter_column_type", table_name, rollback_on_failure=True
        ) as conn:
            cursor = conn.cursor()
            try:
                # Execute ALTER TABLE
                cursor.execute(alter_sql)

                # Update genome_catalog
                cursor.execute(
                    """
                    UPDATE genome_catalog
                    SET field_type = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE table_name = %s AND field_name = %s
                """,
                    (new_type, table_name, field_name),
                )
                # Commit is handled by get_connection() context manager

                # Clear validation cache
                clear_validation_cache()

                # Clear impact cache for this table/field
                clear_impact_cache(table_name, field_name)

                # Log to audit trail
                log_audit_event(
                    "ALTER_COLUMN",
                    tenant_id=tenant_id,
                    table_name=table_name,
                    field_name=field_name,
                    details={
                        "old_type": old_type,
                        "new_type": new_type,
                        "using_clause": using_clause,
                        "impact_analysis": impact,
                        "rollback_sql": rollback_plan["rollback_sql"],
                    },
                    severity="info",
                )

                result["success"] = True
                logger.info(
                    f"Successfully altered column {field_name} type from {old_type} to {new_type} in {table_name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to alter column type {field_name} in {table_name}: {e}", exc_info=True
                )
                result["error"] = str(e)
                result["error_type"] = type(e).__name__
                raise
            finally:
                cursor.close()

    except Exception as e:
        if "error" not in result:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
        raise

    return result


def safe_rename_column(
    table_name: str, old_name: str, new_name: str, tenant_id: int | None = None
) -> JSONDict:
    """
    Safely rename a column with validation and impact analysis.

    Args:
        table_name: Table to modify
        old_name: Current column name
        new_name: New column name
        tenant_id: Tenant ID (if tenant-specific change)

    Returns:
        dict with operation result including:
        - success: Whether operation succeeded
        - old_name: Previous column name
        - new_name: New column name
        - impact: Impact analysis results
        - rollback_plan: Generated rollback plan
        - warnings: List of warnings
    """
    # Check if schema evolution is enabled
    if not is_schema_evolution_enabled():
        raise RuntimeError(
            "Schema evolution is disabled. Enable via operational.schema_evolution.enabled in config."
        )

    # Validate change
    is_valid, errors, validated_table = validate_schema_change(
        table_name=table_name, change_type="RENAME_COLUMN", field_name=old_name
    )

    if not is_valid:
        raise ValueError(f"Schema change validation failed: {', '.join(errors)}")

    # Use validated table name (guaranteed to be str if validation passed)
    if validated_table is None:
        raise ValueError("Table name validation returned None")
    table_name = validated_table

    # Validate new name
    try:
        new_name = validate_field_name(new_name, table_name)
    except ValueError:
        # For rename, new name might not exist in genome_catalog yet, so be lenient
        from src.validation import is_valid_identifier

        if not is_valid_identifier(new_name):
            raise ValueError(f"Invalid new column name: {new_name}") from None

    # Check if new name already exists
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = %s
                """,
                    (table_name, new_name),
                )
                if cursor.fetchone():
                    raise ValueError(f"Column {new_name} already exists in table {table_name}")
            finally:
                cursor.close()
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.error(f"Failed to check column existence: {e}")
        raise

    # Analyze impact (reuse connection if available)
    impact = analyze_schema_change_impact(
        table_name=table_name, field_name=old_name, change_type="RENAME_COLUMN", use_cache=True
    )

    # Generate rollback plan
    rollback_plan = generate_rollback_plan(
        table_name=table_name, change_type="RENAME_COLUMN", field_name=old_name, new_name=new_name
    )

    # Build ALTER TABLE SQL
    old_name = validate_field_name(old_name, table_name)

    rename_sql = sql.SQL(
        """
        ALTER TABLE {}
        RENAME COLUMN {} TO {}
    """
    ).format(sql.Identifier(table_name), sql.Identifier(old_name), sql.Identifier(new_name))

    result: JSONDict = {
        "success": False,
        "table_name": table_name,
        "old_name": old_name,
        "new_name": new_name,
        "impact": impact,
        "rollback_plan": rollback_plan,
        "warnings": impact["warnings"],
    }

    try:
        with safe_database_operation("rename_column", table_name, rollback_on_failure=True) as conn:
            cursor = conn.cursor()
            try:
                # Execute ALTER TABLE
                cursor.execute(rename_sql)

                # Update genome_catalog
                cursor.execute(
                    """
                    UPDATE genome_catalog
                    SET field_name = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE table_name = %s AND field_name = %s
                """,
                    (new_name, table_name, old_name),
                )

                # Update expression_profile
                cursor.execute(
                    """
                    UPDATE expression_profile
                    SET field_name = %s
                    WHERE table_name = %s AND field_name = %s
                """,
                    (new_name, table_name, old_name),
                )
                # Commit is handled by get_connection() context manager

                # Clear validation cache
                clear_validation_cache()

                # Clear impact cache for both old and new field names
                clear_impact_cache(table_name, old_name)
                clear_impact_cache(table_name, new_name)

                # Log to audit trail
                log_audit_event(
                    "RENAME_COLUMN",
                    tenant_id=tenant_id,
                    table_name=table_name,
                    field_name=new_name,
                    details={
                        "old_name": old_name,
                        "new_name": new_name,
                        "impact_analysis": impact,
                        "rollback_sql": rollback_plan["rollback_sql"],
                    },
                    severity="info",
                )

                result["success"] = True
                logger.info(f"Successfully renamed column {old_name} to {new_name} in {table_name}")

            except Exception as e:
                logger.error(
                    f"Failed to rename column {old_name} to {new_name} in {table_name}: {e}",
                    exc_info=True,
                )
                result["error"] = str(e)
                result["error_type"] = type(e).__name__
                raise
            finally:
                cursor.close()

    except Exception as e:
        if "error" not in result:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
        raise

    return result
