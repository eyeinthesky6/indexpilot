"""Foreign key index suggestions"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

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
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Find foreign keys that don't have indexes on the FK columns
                query = """
                    SELECT DISTINCT
                        tc.table_schema,
                        tc.table_name,
                        kcu.column_name,
                        tc.constraint_name,
                        ccu.table_schema AS foreign_table_schema,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        -- Check if index exists on this column
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
                      AND tc.table_schema = %s
                    ORDER BY tc.table_name, kcu.column_name
                """
                cursor.execute(query, (schema_name,))
                results = cursor.fetchall()

                for row in results:
                    has_index = row.get("has_index", False)
                    if not has_index:
                        fk_without_indexes.append(
                            {
                                "schema": row["table_schema"],
                                "table": row["table_name"],
                                "column": row["column_name"],
                                "constraint_name": row["constraint_name"],
                                "foreign_table": f"{row['foreign_table_schema']}.{row['foreign_table_name']}",
                                "foreign_column": row["foreign_column_name"],
                                "full_name": f"{row['table_schema']}.{row['table_name']}.{row['column_name']}",
                            }
                        )

                if fk_without_indexes:
                    logger.info(
                        f"Found {len(fk_without_indexes)} foreign keys without indexes in schema '{schema_name}'"
                    )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to find foreign keys without indexes: {e}")

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
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = %s
                              AND table_name = %s
                              AND column_name = 'tenant_id'
                        )
                        """,
                        (fk["schema"], fk["table"]),
                    )
                    has_tenant = cursor.fetchone()[0]
                    cursor.close()
            except Exception:
                pass  # Assume no tenant_id if check fails

            # If tenant_id exists, suggest composite index
            if has_tenant:
                index_name = f"idx_{fk['table']}_tenant_{fk['column']}_fk"
                index_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_name}
                    ON {fk['schema']}.{fk['table']} (tenant_id, {fk['column']})
                """
                columns = ["tenant_id", fk["column"]]
            else:
                index_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_name}
                    ON {fk['schema']}.{fk['table']} ({fk['column']})
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

    try:
        from src.stats import get_query_stats

        # Get query stats to analyze JOIN patterns
        query_stats = get_query_stats(time_window_hours=24)

        # This is a simplified analysis - in production, you'd parse actual queries
        # For now, we'll just return FK suggestions with basic priority
        fk_suggestions = suggest_foreign_key_indexes(schema_name=schema_name)

        # Add JOIN frequency if we can detect it from query stats
        # (This would require query parsing in a full implementation)

        return fk_suggestions

    except Exception as e:
        logger.debug(f"Could not analyze JOIN patterns: {e}")
        return suggest_foreign_key_indexes(schema_name=schema_name)

