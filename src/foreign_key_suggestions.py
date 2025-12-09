"""Foreign key index suggestions"""

import logging
from typing import Any

from psycopg2 import sql

from src.config_loader import ConfigLoader
from src.db import get_cursor

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_foreign_key_suggestions_enabled() -> bool:
    """Check if foreign key index suggestions are enabled"""
    return _config_loader.get_bool("features.foreign_key_suggestions.enabled", True)


def find_foreign_keys_without_indexes(
    schema_name: str = "public",
) -> list[dict[str, Any]]:
    """
    Find foreign key columns that don't have indexes.

    Foreign keys are frequently used in JOINs and benefit significantly from indexes.

    Args:
        schema_name: Schema to check (default: public)

    Returns:
        List of foreign keys without indexes
    """
    if not is_foreign_key_suggestions_enabled():
        logger.debug("Foreign key suggestions are disabled")
        return []

    fk_without_indexes = []

    try:
        with get_cursor() as cursor:
            # Find foreign keys that don't have indexes on the FK columns
            # Use psycopg2.sql to properly construct the query and avoid RealDictCursor issues
            query = sql.SQL(
                """
                    SELECT DISTINCT
                        tc.table_schema,
                        tc.table_name,
                        kcu.column_name,
                        tc.constraint_name,
                        ccu.table_schema AS foreign_table_schema,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM pg_indexes idx
                                WHERE idx.schemaname = tc.table_schema
                                  AND idx.tablename = tc.table_name
                                  AND (
                                      idx.indexdef LIKE '%' || kcu.column_name || '%'
                                      OR EXISTS (
                                          SELECT 1
                                          FROM pg_index i
                                          JOIN pg_class t ON i.indrelid = t.oid
                                          JOIN pg_class c ON i.indexrelid = c.oid
                                          JOIN pg_attribute a ON a.attrelid = t.oid
                                          WHERE t.relname = tc.table_name
                                            AND t.relnamespace = (
                                                SELECT oid FROM pg_namespace WHERE nspname = tc.table_schema
                                            )
                                            AND a.attname = kcu.column_name
                                            AND a.attnum = ANY(i.indkey)
                                      )
                                  )
                            ) THEN true
                            ELSE false
                        END as has_index
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = {}
                    ORDER BY tc.table_name, kcu.column_name
                """
            ).format(sql.Literal(schema_name))
            cursor.execute(query)
            results = cursor.fetchall()

            for row in results:
                # Handle both dict (RealDictCursor) and tuple results
                try:
                    if isinstance(row, dict):
                        has_index = row.get("has_index", False)
                        table_schema = row.get("table_schema", "")
                        table_name = row.get("table_name", "")
                        column_name = row.get("column_name", "")
                        constraint_name = row.get("constraint_name", "")
                        foreign_table_schema = row.get("foreign_table_schema", "")
                        foreign_table_name = row.get("foreign_table_name", "")
                        foreign_column_name = row.get("foreign_column_name", "")
                    elif isinstance(row, tuple | list):
                        # Use safe helper to prevent "tuple index out of range" errors
                        from src.db import safe_get_row_value

                        has_index = safe_get_row_value(
                            row, "has_index", False
                        ) or safe_get_row_value(row, 7, False)
                        table_schema = safe_get_row_value(
                            row, "table_schema", ""
                        ) or safe_get_row_value(row, 0, "")
                        table_name = safe_get_row_value(
                            row, "table_name", ""
                        ) or safe_get_row_value(row, 1, "")
                        column_name = safe_get_row_value(
                            row, "column_name", ""
                        ) or safe_get_row_value(row, 2, "")
                        constraint_name = safe_get_row_value(
                            row, "constraint_name", ""
                        ) or safe_get_row_value(row, 3, "")
                        foreign_table_schema = safe_get_row_value(
                            row, "foreign_table_schema", ""
                        ) or safe_get_row_value(row, 4, "")
                        foreign_table_name = safe_get_row_value(
                            row, "foreign_table_name", ""
                        ) or safe_get_row_value(row, 5, "")
                        foreign_column_name = safe_get_row_value(
                            row, "foreign_column_name", ""
                        ) or safe_get_row_value(row, 6, "")

                        # Validate we got required fields
                        if not table_name or not column_name:
                            logger.warning(
                                f"Unexpected tuple result missing required fields: {row}"
                            )
                            continue
                    else:
                        logger.warning(f"Unexpected result type: {type(row)}")
                        continue
                except (IndexError, KeyError, AttributeError) as e:
                    logger.warning(f"Error processing foreign key row: {e}, row type: {type(row)}")
                    continue

                if not has_index:
                    fk_without_indexes.append(
                        {
                            "schema": table_schema,
                            "table": table_name,
                            "column": column_name,
                            "constraint_name": constraint_name,
                            "foreign_table": f"{foreign_table_schema}.{foreign_table_name}",
                            "foreign_column": foreign_column_name,
                            "full_name": f"{table_schema}.{table_name}.{column_name}",
                        }
                    )

            if fk_without_indexes:
                logger.info(
                    f"Found {len(fk_without_indexes)} foreign keys without indexes in schema '{schema_name}'"
                )

    except Exception as e:
        import traceback

        error_type = type(e).__name__
        error_msg = str(e) if e else "Unknown error"
        logger.error(f"Failed to find foreign keys without indexes ({error_type}): {error_msg}")
        # Only log full traceback for IndexError to help debug tuple index issues
        if isinstance(e, IndexError | KeyError):
            logger.debug(f"Foreign key query error traceback: {traceback.format_exc()}")

    return fk_without_indexes


def suggest_foreign_key_indexes(
    schema_name: str = "public",
) -> list[dict[str, Any]]:
    """
    Suggest indexes for foreign key columns.

    Args:
        schema_name: Schema to check (default: public)

    Returns:
        List of index suggestions for foreign keys
    """
    if not is_foreign_key_suggestions_enabled():
        return []

    suggestions = []

    try:
        fk_without_indexes = find_foreign_keys_without_indexes(schema_name=schema_name)

        for fk in fk_without_indexes:
            # Generate index name
            index_name = f"idx_{fk['table']}_{fk['column']}_fk"

            # Check if tenant_id exists (for multi-tenant tables)
            has_tenant = False
            try:
                with get_cursor() as cursor:
                    cursor.execute(
                        """
                            SELECT EXISTS (
                                SELECT 1
                                FROM information_schema.columns
                                WHERE table_schema = %s
                                  AND table_name = %s
                                  AND column_name = 'tenant_id'
                            ) as exists
                            """,
                        (fk["schema"], fk["table"]),
                    )
                    tenant_result = cursor.fetchone()
                    has_tenant = tenant_result.get("exists", False) if tenant_result else False
            except Exception:
                pass  # Assume no tenant_id if check fails

            # If tenant_id exists, suggest composite index
            if has_tenant:
                index_name = f"idx_{fk['table']}_tenant_{fk['column']}_fk"
                index_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_name}
                    ON {fk["schema"]}.{fk["table"]} (tenant_id, {fk["column"]})
                """
                columns = ["tenant_id", fk["column"]]
            else:
                index_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_name}
                    ON {fk["schema"]}.{fk["table"]} ({fk["column"]})
                """
                columns = [fk["column"]]

            suggestions.append(
                {
                    "table": f"{fk['schema']}.{fk['table']}",
                    "columns": columns,
                    "index_name": index_name,
                    "index_sql": index_sql.strip(),
                    "reason": f"Foreign key column '{fk['column']}' references {fk['foreign_table']}.{fk['foreign_column']}",
                    "foreign_key": fk["constraint_name"],
                    "foreign_table": fk["foreign_table"],
                    "priority": "high",  # Foreign keys are high priority for JOINs
                }
            )

        if suggestions:
            logger.info(f"Generated {len(suggestions)} foreign key index suggestions")

    except Exception as e:
        logger.error(f"Failed to suggest foreign key indexes: {e}")

    return suggestions


def analyze_join_patterns_for_fk(
    schema_name: str = "public",
) -> list[dict[str, Any]]:
    """
    Analyze JOIN patterns to identify frequently joined foreign keys.

    This helps prioritize which FK indexes to create first.

    Args:
        schema_name: Schema to analyze

    Returns:
        List of foreign keys with JOIN frequency analysis
    """
    if not is_foreign_key_suggestions_enabled():
        return []

    # Get query stats to analyze JOIN patterns (reserved for future use)
    # from src.stats import get_query_stats
    # query_stats = get_query_stats(time_window_hours=24)

    try:
        # This is a simplified analysis - in production, you'd parse actual queries
        # For now, we'll just return FK suggestions with basic priority
        fk_suggestions = suggest_foreign_key_indexes(schema_name=schema_name)

        # Add JOIN frequency if we can detect it from query stats
        # (This would require query parsing in a full implementation)

        return fk_suggestions

    except Exception as e:
        logger.debug(f"Could not analyze JOIN patterns: {e}")
        return suggest_foreign_key_indexes(schema_name=schema_name)
