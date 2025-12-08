"""Detect schema changes and update genome catalog automatically"""

import logging

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.schema.auto_discovery import discover_schema_from_database
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)


def detect_and_sync_schema_changes(
    schema_name: str = "public",
    auto_update: bool = True,
) -> JSONDict:
    """
    Detect schema changes and sync genome catalog with current database schema.

    This function detects schema changes made via ANY means:
    - Direct SQL (ALTER TABLE, CREATE TABLE, etc.)
    - ORMs (Django, SQLAlchemy, etc.) - they execute SQL
    - Migrations (Alembic, Django migrations, etc.) - they execute SQL
    - GUI tools (pgAdmin, DBeaver, etc.) - they execute SQL
    - Any other tool that modifies PostgreSQL schema

    How it works:
    1. Queries PostgreSQL's information_schema (system catalog) to discover current schema
    2. Compares with genome_catalog
    3. Detects new tables/columns (not in genome_catalog)
    4. Detects removed tables/columns (in genome_catalog but not in database)
    5. Optionally updates genome_catalog to match current schema

    Note: information_schema reflects the current state of the database regardless of
    how changes were made, so ALL schema changes are detected.

    Args:
        schema_name: Schema to check (default: "public")
        auto_update: If True, automatically update genome_catalog (default: True)

    Returns:
        dict with change detection results:
        - new_tables: List of new tables discovered
        - new_columns: List of new columns discovered (table, field)
        - removed_tables: List of tables that no longer exist
        - removed_columns: List of columns that no longer exist (table, field)
        - updated: Whether genome_catalog was updated
    """
    from src.genome import bootstrap_genome_catalog_from_schema, get_genome_fields

    result: JSONDict = {
        "new_tables": [],
        "new_columns": [],
        "removed_tables": [],
        "removed_columns": [],
        "updated": False,
        "tables_count": 0,
        "fields_count": 0,
    }

    try:
        # 1. Discover current schema from database
        logger.info(f"Discovering current schema from database '{schema_name}'...")
        current_schema = discover_schema_from_database(schema_name=schema_name)

        if not current_schema.get("tables"):
            logger.warning("No tables discovered in schema")
            return result

        # 2. Get current genome_catalog entries
        logger.debug("Reading current genome_catalog entries...")
        genome_fields = get_genome_fields()

        # Build sets for comparison with proper type narrowing
        # Type narrowing: current_schema["tables"] is a list of dicts
        tables_list = current_schema.get("tables")
        if not isinstance(tables_list, list):
            logger.error("Invalid schema structure: 'tables' is not a list")
            return result

        current_tables: set[str] = set()
        current_fields: set[tuple[str, str]] = set()

        for table_def in tables_list:
            if not isinstance(table_def, dict):
                continue
            table_name = table_def.get("name")
            if isinstance(table_name, str):
                current_tables.add(table_name)

                # Get fields for this table
                fields = table_def.get("fields")
                if isinstance(fields, list):
                    for field_def in fields:
                        if not isinstance(field_def, dict):
                            continue
                        field_name = field_def.get("name")
                        if isinstance(field_name, str):
                            current_fields.add((table_name, field_name))

        # Type narrowing: genome_fields is a list of RealDictRow (dict-like)
        genome_tables: set[str] = set()
        genome_fields_set: set[tuple[str, str]] = set()

        for field_row in genome_fields:
            if not isinstance(field_row, dict):
                continue
            table_name = field_row.get("table_name")
            field_name = field_row.get("field_name")
            if isinstance(table_name, str):
                genome_tables.add(table_name)
                if isinstance(field_name, str):
                    genome_fields_set.add((table_name, field_name))

        # 3. Detect new tables
        new_tables = current_tables - genome_tables
        result["new_tables"] = list(new_tables)

        # 4. Detect removed tables
        removed_tables = genome_tables - current_tables
        result["removed_tables"] = list(removed_tables)

        # 5. Detect new columns (in current schema but not in genome_catalog)
        new_columns = current_fields - genome_fields_set
        result["new_columns"] = [
            {"table": table, "field": field}  # type: ignore[dict-item]
            for table, field in new_columns
        ]

        # 6. Detect removed columns (in genome_catalog but not in current schema)
        removed_columns = genome_fields_set - current_fields
        removed_columns_list: list[JSONDict] = [
            {"table": table, "field": field}  # type: ignore[dict-item]
            for table, field in removed_columns
        ]
        result["removed_columns"] = removed_columns_list

        # Log detected changes
        if new_tables or new_columns:
            logger.info(
                f"Detected new schema elements: {len(new_tables)} tables, {len(new_columns)} columns"
            )
        if removed_tables or removed_columns:
            logger.info(
                f"Detected removed schema elements: {len(removed_tables)} tables, {len(removed_columns)} columns"
            )

        # 7. Update genome_catalog if requested
        if auto_update:
            if new_tables or new_columns:
                logger.info("Updating genome_catalog with new schema elements...")
                bootstrap_genome_catalog_from_schema(current_schema)
                result["updated"] = True
                result["tables_count"] = len(current_tables)
                result["fields_count"] = len(current_fields)

            # Remove orphaned entries (tables/columns that no longer exist)
            if removed_tables or removed_columns:
                logger.info("Cleaning up orphaned genome_catalog entries...")
                _remove_orphaned_entries(removed_tables, removed_columns_list)
                result["updated"] = True

        return result

    except Exception as e:
        logger.error(f"Failed to detect and sync schema changes: {e}", exc_info=True)
        result["error"] = str(e)
        return result


def _remove_orphaned_entries(
    removed_tables: set[str],
    removed_columns: list[JSONDict],
) -> None:
    """
    Remove orphaned entries from genome_catalog.

    Args:
        removed_tables: Set of table names that no longer exist
        removed_columns: List of dicts with 'table' and 'field' keys for removed columns
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                removed_count = 0

                # Remove entries for removed tables
                if removed_tables:
                    cursor.execute(
                        """
                        DELETE FROM genome_catalog
                        WHERE table_name = ANY(%s)
                        """,
                        (list(removed_tables),),
                    )
                    removed_count += cursor.rowcount

                # Remove entries for removed columns
                if removed_columns:
                    for col in removed_columns:
                        if not isinstance(col, dict):
                            continue
                        table_name = col.get("table")
                        field_name = col.get("field")
                        if isinstance(table_name, str) and isinstance(field_name, str):
                            cursor.execute(
                                """
                                DELETE FROM genome_catalog
                                WHERE table_name = %s AND field_name = %s
                                """,
                                (table_name, field_name),
                            )
                            removed_count += cursor.rowcount

                conn.commit()

                if removed_count > 0:
                    logger.info(f"Removed {removed_count} orphaned entries from genome_catalog")

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to remove orphaned entries: {e}", exc_info=True)
        raise
