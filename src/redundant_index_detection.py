"""Detect redundant and overlapping indexes"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_redundant_index_detection_enabled() -> bool:
    """Check if redundant index detection is enabled"""
    return _config_loader.get_bool("features.redundant_index_detection.enabled", True)


def find_redundant_indexes(schema_name: str = "public") -> list[dict[str, Any]]:
    """
    Find redundant indexes (overlapping or duplicate).

    An index is redundant if:
    1. Another index covers the same columns (or a prefix)
    2. A composite index makes a single-column index redundant
    3. Multiple indexes on the same column(s)

    Args:
        schema_name: Schema to check (default: public)

    Returns:
        List of redundant indexes with suggestions
    """
    if not is_redundant_index_detection_enabled():
        logger.debug("Redundant index detection is disabled")
        return []

    redundant_indexes = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get all indexes with their columns
                query = """
                    SELECT
                        i.schemaname,
                        i.tablename,
                        i.indexname,
                        i.indexdef,
                        array_agg(a.attname ORDER BY array_position(i.indkey, a.attnum)) as index_columns,
                        pg_size_pretty(pg_relation_size(i.indexname::regclass)) as size_pretty,
                        pg_relation_size(i.indexname::regclass) / (1024.0 * 1024.0) as size_mb,
                        idx_scan as index_scans
                    FROM pg_indexes i
                    JOIN pg_class c ON c.relname = i.indexname
                    JOIN pg_index idx ON idx.indexrelid = c.oid
                    LEFT JOIN pg_attribute a ON a.attrelid = idx.indrelid
                        AND a.attnum = ANY(idx.indkey)
                    LEFT JOIN pg_stat_user_indexes stat ON stat.indexrelname = i.indexname
                        AND stat.schemaname = i.schemaname
                    WHERE i.schemaname = %s
                    GROUP BY i.schemaname, i.tablename, i.indexname, i.indexdef,
                             pg_relation_size(i.indexname::regclass),
                             idx_scan
                    ORDER BY i.tablename, i.indexname
                """
                cursor.execute(query, (schema_name,))
                indexes = cursor.fetchall()

                # Build index map by table
                table_indexes: dict[str, list[dict[str, Any]]] = {}
                for idx in indexes:
                    table_key = f"{idx['schemaname']}.{idx['tablename']}"
                    if table_key not in table_indexes:
                        table_indexes[table_key] = []

                    index_columns = [col for col in idx["index_columns"] if col]
                    table_indexes[table_key].append(
                        {
                            "schema": idx["schemaname"],
                            "table": idx["tablename"],
                            "index_name": idx["indexname"],
                            "indexdef": idx["indexdef"],
                            "columns": index_columns,
                            "size_mb": float(idx["size_mb"]) if idx["size_mb"] else 0.0,
                            "size_pretty": idx["size_pretty"],
                            "scans": int(idx["index_scans"]) if idx["index_scans"] else 0,
                        }
                    )

                # Check for redundant indexes
                for table_key, table_idx_list in table_indexes.items():
                    for i, idx1 in enumerate(table_idx_list):
                        for idx2 in table_idx_list[i + 1 :]:
                            redundancy = _check_index_redundancy(idx1, idx2)
                            if redundancy["is_redundant"]:
                                redundant_indexes.append(redundancy)

                if redundant_indexes:
                    logger.info(
                        f"Found {len(redundant_indexes)} redundant index pairs in schema '{schema_name}'"
                    )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to find redundant indexes: {e}")

    return redundant_indexes


def _check_index_redundancy(idx1: dict[str, Any], idx2: dict[str, Any]) -> dict[str, Any]:
    """
    Check if two indexes are redundant.

    Args:
        idx1: First index
        idx2: Second index

    Returns:
        dict with redundancy information
    """
    cols1 = idx1["columns"]
    cols2 = idx2["columns"]

    # Check if one index is a prefix of another
    if len(cols1) <= len(cols2):
        if cols1 == cols2[: len(cols1)]:
            # idx1 is a prefix of idx2 - idx1 is redundant
            return {
                "is_redundant": True,
                "redundant_index": idx1["index_name"],
                "covering_index": idx2["index_name"],
                "table": f"{idx1['schema']}.{idx1['table']}",
                "redundant_columns": cols1,
                "covering_columns": cols2,
                "reason": f"Index '{idx1['index_name']}' is a prefix of '{idx2['index_name']}'",
                "suggestion": f"Consider dropping '{idx1['index_name']}' as '{idx2['index_name']}' covers it",
                "redundant_size_mb": idx1["size_mb"],
                "redundant_scans": idx1["scans"],
            }
    else:
        if cols2 == cols1[: len(cols2)]:
            # idx2 is a prefix of idx1 - idx2 is redundant
            return {
                "is_redundant": True,
                "redundant_index": idx2["index_name"],
                "covering_index": idx1["index_name"],
                "table": f"{idx1['schema']}.{idx1['table']}",
                "redundant_columns": cols2,
                "covering_columns": cols1,
                "reason": f"Index '{idx2['index_name']}' is a prefix of '{idx1['index_name']}'",
                "suggestion": f"Consider dropping '{idx2['index_name']}' as '{idx1['index_name']}' covers it",
                "redundant_size_mb": idx2["size_mb"],
                "redundant_scans": idx2["scans"],
            }

    # Check if indexes are identical
    if cols1 == cols2:
        # Both are identical - suggest keeping the one with more scans
        if idx1["scans"] >= idx2["scans"]:
            redundant = idx2
            keep = idx1
        else:
            redundant = idx1
            keep = idx2

        return {
            "is_redundant": True,
            "redundant_index": redundant["index_name"],
            "covering_index": keep["index_name"],
            "table": f"{idx1['schema']}.{idx1['table']}",
            "redundant_columns": redundant["columns"],
            "covering_columns": keep["columns"],
            "reason": f"Indexes '{idx1['index_name']}' and '{idx2['index_name']}' are identical",
            "suggestion": f"Consider dropping '{redundant['index_name']}' "
            f"(keeping '{keep['index_name']}' with {keep['scans']} scans)",
            "redundant_size_mb": redundant["size_mb"],
            "redundant_scans": redundant["scans"],
        }

    return {"is_redundant": False}


def suggest_index_consolidation(
    schema_name: str = "public",
) -> list[dict[str, Any]]:
    """
    Suggest index consolidation opportunities.

    Args:
        schema_name: Schema to analyze

    Returns:
        List of consolidation suggestions
    """
    redundant = find_redundant_indexes(schema_name=schema_name)
    suggestions = []

    for redundancy in redundant:
        if redundancy.get("is_redundant"):
            suggestions.append(
                {
                    "action": "drop",
                    "index": redundancy["redundant_index"],
                    "table": redundancy["table"],
                    "reason": redundancy["reason"],
                    "suggestion": redundancy["suggestion"],
                    "space_savings_mb": redundancy.get("redundant_size_mb", 0.0),
                    "drop_sql": f"DROP INDEX CONCURRENTLY {redundancy['redundant_index']}",
                }
            )

    if suggestions:
        logger.info(f"Generated {len(suggestions)} index consolidation suggestions")

    return suggestions
