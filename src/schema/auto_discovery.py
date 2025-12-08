"""Auto-discover schema from existing PostgreSQL database"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)


def discover_schema_from_database(
    schema_name: str = "public",
    include_system_tables: bool = False,
    exclude_tables: set[str] | None = None,
) -> JSONDict:
    """
    Auto-discover schema from existing PostgreSQL database.

    Reads from information_schema to discover:
    - All tables
    - All columns with types
    - Primary keys
    - Foreign keys
    - Indexes (for reference)

    Args:
        schema_name: Schema to discover (default: "public")
        include_system_tables: Whether to include system tables (default: False)
        exclude_tables: Set of table names to exclude (default: None)

    Returns:
        Schema definition dict compatible with genome catalog format

    Example:
        >>> schema = discover_schema_from_database()
        >>> from src.genome import bootstrap_genome_catalog_from_schema
        >>> bootstrap_genome_catalog_from_schema(schema)
    """
    if exclude_tables is None:
        exclude_tables = set()

    # Add metadata tables to exclude list
    metadata_tables = {
        "genome_catalog",
        "expression_profile",
        "mutation_log",
        "query_stats",
        "index_versions",
        "ab_experiments",
        "ab_experiment_results",
    }
    exclude_tables = exclude_tables.union(metadata_tables)

    schema_definition: JSONDict = {"tables": []}

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            try:
                # 1. Discover all tables
                tables_query = """
                    SELECT
                        table_name,
                        table_type
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """
                cursor.execute(tables_query, (schema_name,))
                tables = cursor.fetchall()

                logger.info(f"Discovered {len(tables)} tables in schema '{schema_name}'")

                # 2. For each table, discover columns
                for table_row in tables:
                    table_name = table_row["table_name"]

                    # Skip excluded tables
                    if table_name in exclude_tables:
                        logger.debug(f"Skipping excluded table: {table_name}")
                        continue

                    # Skip system tables unless requested
                    if not include_system_tables and table_name.startswith("pg_"):
                        logger.debug(f"Skipping system table: {table_name}")
                        continue

                    logger.debug(f"Discovering columns for table: {table_name}")

                    # Get columns for this table
                    columns_query = """
                        SELECT
                            column_name,
                            data_type,
                            udt_name,
                            character_maximum_length,
                            numeric_precision,
                            numeric_scale,
                            is_nullable,
                            column_default,
                            ordinal_position
                        FROM information_schema.columns
                        WHERE table_schema = %s
                          AND table_name = %s
                        ORDER BY ordinal_position
                    """
                    cursor.execute(columns_query, (schema_name, table_name))
                    columns = cursor.fetchall()

                    if not columns:
                        logger.warning(f"No columns found for table {table_name}, skipping")
                        continue

                    # Get primary key columns
                    pk_query = """
                        SELECT
                            kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_schema = %s
                          AND tc.table_name = %s
                          AND tc.constraint_type = 'PRIMARY KEY'
                        ORDER BY kcu.ordinal_position
                    """
                    cursor.execute(pk_query, (schema_name, table_name))
                    pk_columns = {row["column_name"] for row in cursor.fetchall()}

                    # Get foreign keys
                    fk_query = """
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table_name,
                            ccu.column_name AS foreign_column_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                            AND ccu.table_schema = tc.table_schema
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND tc.table_schema = %s
                          AND tc.table_name = %s
                    """
                    cursor.execute(fk_query, (schema_name, table_name))
                    foreign_keys = cursor.fetchall()
                    fk_map = {
                        fk["column_name"]: {
                            "table": fk["foreign_table_name"],
                            "column": fk["foreign_column_name"],
                        }
                        for fk in foreign_keys
                    }

                    # Build table definition
                    table_def: JSONDict = {
                        "name": table_name,
                        "fields": [],
                    }

                    # Convert columns to field definitions
                    for col in columns:
                        col_name = col["column_name"]
                        data_type = col["data_type"]
                        udt_name = col["udt_name"]
                        is_nullable = col["is_nullable"] == "YES"

                        # Map PostgreSQL types to schema format
                        field_type = _map_postgres_type(data_type, udt_name)

                        # Determine if required (not nullable and no default)
                        is_required = not is_nullable and col["column_default"] is None

                        # Primary key is always required and indexable
                        is_pk = col_name in pk_columns
                        if is_pk:
                            is_required = True

                        # Build field definition
                        field_def: JSONDict = {
                            "name": col_name,
                            "type": field_type,
                            "required": is_required,
                            "indexable": True,  # Default to indexable, can be refined later
                        }

                        # Add foreign key info if present
                        if col_name in fk_map:
                            fk_info = fk_map[col_name]
                            field_def["foreign_key"] = {
                                "table": fk_info["table"],
                                "column": fk_info["column"],
                                "on_delete": "CASCADE",  # Default, could be discovered from constraint
                            }

                        table_def["fields"].append(field_def)

                    # Get existing indexes for reference (optional)
                    indexes_query = """
                        SELECT
                            indexname,
                            indexdef
                        FROM pg_indexes
                        WHERE schemaname = %s
                          AND tablename = %s
                    """
                    cursor.execute(indexes_query, (schema_name, table_name))
                    indexes = cursor.fetchall()

                    if indexes:
                        table_def["indexes"] = [
                            {
                                "name": idx["indexname"],
                                "definition": idx["indexdef"],
                            }
                            for idx in indexes
                        ]

                    schema_definition["tables"].append(table_def)

                logger.info(
                    f"Schema discovery complete: {len(schema_definition['tables'])} tables, "
                    f"{sum(len(t['fields']) for t in schema_definition['tables'])} fields"
                )

                return schema_definition

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to discover schema from database: {e}")
        raise


def _map_postgres_type(data_type: str, udt_name: str) -> str:
    """
    Map PostgreSQL data type to schema format type.

    Args:
        data_type: PostgreSQL data_type from information_schema
        udt_name: PostgreSQL udt_name (user-defined type name)

    Returns:
        Schema format type string
    """
    # Use udt_name if available (more specific)
    type_name = udt_name.upper() if udt_name else data_type.upper()

    # Map common PostgreSQL types
    type_mapping: dict[str, str] = {
        # Integer types
        "INTEGER": "INTEGER",
        "INT": "INTEGER",
        "INT4": "INTEGER",
        "BIGINT": "BIGINT",
        "INT8": "BIGINT",
        "SMALLINT": "SMALLINT",
        "INT2": "SMALLINT",
        "SERIAL": "SERIAL",
        "BIGSERIAL": "BIGSERIAL",
        # Numeric types
        "NUMERIC": "NUMERIC",
        "DECIMAL": "NUMERIC",
        "REAL": "REAL",
        "DOUBLE PRECISION": "DOUBLE PRECISION",
        "FLOAT": "REAL",
        "FLOAT4": "REAL",
        "FLOAT8": "DOUBLE PRECISION",
        # Text types
        "TEXT": "TEXT",
        "VARCHAR": "TEXT",
        "CHAR": "TEXT",
        "CHARACTER": "TEXT",
        "CHARACTER VARYING": "TEXT",
        # Boolean
        "BOOLEAN": "BOOLEAN",
        "BOOL": "BOOLEAN",
        # Date/time types
        "TIMESTAMP": "TIMESTAMP",
        "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
        "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
        "TIMESTAMPTZ": "TIMESTAMPTZ",
        "DATE": "DATE",
        "TIME": "TIME",
        "INTERVAL": "INTERVAL",
        # JSON types
        "JSON": "JSON",
        "JSONB": "JSONB",
        # Binary types
        "BYTEA": "BYTEA",
        # UUID
        "UUID": "UUID",
    }

    # Try exact match first
    if type_name in type_mapping:
        return type_mapping[type_name]

    # Try with length suffix (e.g., VARCHAR(255) -> TEXT)
    if "VARCHAR" in type_name or "CHARACTER VARYING" in type_name:
        return "TEXT"

    # Default: return as-is (uppercase)
    return type_name


def discover_and_bootstrap_schema(
    schema_name: str = "public",
    exclude_tables: set[str] | None = None,
) -> dict[str, Any]:
    """
    Discover schema from database and bootstrap genome catalog.

    Convenience function that:
    1. Discovers schema from database
    2. Bootstraps genome catalog with discovered schema

    Args:
        schema_name: Schema to discover (default: "public")
        exclude_tables: Set of table names to exclude

    Returns:
        dict with discovery results and bootstrap status
    """
    from src.genome import bootstrap_genome_catalog_from_schema

    try:
        logger.info(f"Starting schema discovery and bootstrap for schema '{schema_name}'")

        # Discover schema
        schema = discover_schema_from_database(
            schema_name=schema_name,
            exclude_tables=exclude_tables,
        )

        if not schema.get("tables"):
            return {
                "success": False,
                "error": "No tables discovered",
                "tables_count": 0,
            }

        # Bootstrap genome catalog
        bootstrap_genome_catalog_from_schema(schema)

        tables_count = len(schema["tables"])
        fields_count = sum(len(t["fields"]) for t in schema["tables"])

        logger.info(
            f"Schema discovery and bootstrap complete: "
            f"{tables_count} tables, {fields_count} fields"
        )

        return {
            "success": True,
            "tables_count": tables_count,
            "fields_count": fields_count,
            "tables": [t["name"] for t in schema["tables"]],
        }

    except Exception as e:
        logger.error(f"Schema discovery and bootstrap failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "tables_count": 0,
        }
