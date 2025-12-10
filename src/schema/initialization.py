# mypy: ignore-errors
"""Database schema setup and migrations"""

import logging
import threading
import time
from typing import Any

from psycopg2.errors import DeadlockDetected, DuplicateObject
from psycopg2.extras import RealDictCursor

from src.database import get_database_adapter
from src.db import get_connection

logger = logging.getLogger(__name__)

# Lock to prevent concurrent schema initialization
_schema_init_lock = threading.Lock()
_schema_initialized = False


def create_business_tables(cursor):
    """Create the multi-tenant mini-CRM business tables"""

    # Tenants table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Contacts table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            custom_text_1 TEXT,
            custom_text_2 TEXT,
            custom_number_1 NUMERIC,
            custom_number_2 NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Organizations table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            industry TEXT,
            custom_text_1 TEXT,
            custom_text_2 TEXT,
            custom_number_1 NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Interactions table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interactions (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
            org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
            type TEXT NOT NULL,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata_json JSONB
        )
    """
    )


def create_metadata_tables(cursor):
    """Create the IndexPilot metadata tables"""

    # Genome catalog - canonical schema definition
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS genome_catalog (
            id SERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL,
            is_required BOOLEAN DEFAULT FALSE,
            is_indexable BOOLEAN DEFAULT TRUE,
            default_expression BOOLEAN DEFAULT TRUE,
            feature_group TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_name, field_name)
        )
    """
    )

    # Expression profile - per-tenant field activation
    # Note: tenant_id is optional - system works with or without multi-tenancy
    # If tenants table exists, foreign key will be added via schema config
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS expression_profile (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER,
            table_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, table_name, field_name)
        )
    """
    )

    # Mutation log - tracks all schema/index changes
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mutation_log (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER,
            mutation_type TEXT NOT NULL,
            table_name TEXT,
            field_name TEXT,
            details_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Query stats - tracks query performance
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS query_stats (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
            table_name TEXT NOT NULL,
            field_name TEXT,
            query_type TEXT NOT NULL,
            duration_ms NUMERIC NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Index versions - tracks index version history for rollback
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS index_versions (
            id SERIAL PRIMARY KEY,
            index_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            index_definition TEXT NOT NULL,
            created_by TEXT DEFAULT 'auto_indexer',
            metadata_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # A/B experiments - tracks A/B testing experiments for index strategies
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_experiments (
            id SERIAL PRIMARY KEY,
            experiment_name TEXT NOT NULL UNIQUE,
            table_name TEXT NOT NULL,
            field_name TEXT,
            variant_a_config JSONB NOT NULL,
            variant_b_config JSONB NOT NULL,
            traffic_split_pct NUMERIC DEFAULT 50.0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # A/B experiment results - tracks query results for each variant
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_experiment_results (
            id SERIAL PRIMARY KEY,
            experiment_name TEXT NOT NULL REFERENCES ab_experiments(experiment_name) ON DELETE CASCADE,
            variant TEXT NOT NULL,
            query_duration_ms NUMERIC NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # ML model metadata - tracks ML models used for query interception and predictions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ml_model_metadata (
            id SERIAL PRIMARY KEY,
            model_name TEXT NOT NULL UNIQUE,
            model_type TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            accuracy NUMERIC,
            training_samples INTEGER,
            model_config_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Algorithm usage tracking - tracks which algorithms were used for index decisions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS algorithm_usage (
            id SERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            field_name TEXT,
            algorithm_name TEXT NOT NULL,
            recommendation_json JSONB,
            used_in_decision BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )


def create_indexes(cursor, max_retries: int = 3, retry_delay: float = 0.5):
    """
    Create initial indexes for foreign keys and common lookups.

    Includes retry logic for deadlocks that can occur during concurrent initialization.

    Args:
        cursor: Database cursor
        max_retries: Maximum number of retries for deadlock errors
        retry_delay: Delay between retries in seconds
    """
    index_statements = [
        """
        CREATE INDEX IF NOT EXISTS idx_contacts_tenant_id
        ON contacts(tenant_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organizations_tenant_id
        ON organizations(tenant_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_interactions_tenant_id
        ON interactions(tenant_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_expression_profile_tenant
        ON expression_profile(tenant_id, table_name, field_name)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_index_versions_name
        ON index_versions(index_name, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ab_experiments_status
        ON ab_experiments(status, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_results_exp
        ON ab_experiment_results(experiment_name, variant, created_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_algorithm_usage_table_field
        ON algorithm_usage(table_name, field_name, algorithm_name, created_at DESC)
        """,
    ]

    for stmt in index_statements:
        for attempt in range(max_retries):
            try:
                cursor.execute(stmt)
                break  # Success, move to next statement
            except DeadlockDetected as e:
                # Rollback transaction before retrying (required after deadlock)
                cursor.connection.rollback()
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Deadlock detected while creating index, retrying ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to create index after {max_retries} retries: {e}")
                    raise
            except DuplicateObject:
                # Index already exists (shouldn't happen with IF NOT EXISTS, but handle gracefully)
                logger.debug("Index already exists, skipping")
                break  # Success (index exists), move to next statement
            except Exception as e:
                # Catch any other exception and rollback transaction before re-raising
                # This prevents InFailedSqlTransaction errors on subsequent operations
                logger.error(f"Unexpected error creating index: {e}")
                cursor.connection.rollback()
                raise


def init_schema():
    """
    Initialize the complete database schema.

    Uses a lock to prevent concurrent initialization that can cause deadlocks.
    """
    global _schema_initialized

    # Check if already initialized (fast path)
    if _schema_initialized:
        return

    # Acquire lock to prevent concurrent initialization
    with _schema_init_lock:
        # Double-check after acquiring lock
        if _schema_initialized:
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    create_business_tables(cursor)
                    create_metadata_tables(cursor)
                    create_indexes(cursor)
                    conn.commit()
                    _schema_initialized = True
                    logger.info("Schema initialized successfully")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to initialize schema: {e}")
                    raise
                finally:
                    cursor.close()
        except Exception:
            # Reset flag on failure so retry is possible
            _schema_initialized = False
            raise


# New extensible functions (Option 2: Configuration-Based)


def create_table_from_definition(cursor, table_def: dict[str, Any], adapter=None):
    """
    Create a table from schema definition using database adapter.

    Supports foreign keys if defined in schema config (not hardcoded).

    Args:
        cursor: Database cursor
        table_def: Table definition from schema config
        adapter: Database adapter (auto-detected if None)
    """
    if adapter is None:
        adapter = get_database_adapter()

    table_name = table_def.get("name")
    if not table_name:
        raise ValueError("Table definition must have 'name' field")

    fields = table_def.get("fields", [])
    if not fields:
        raise ValueError(f"Table {table_name} must have at least one field")

    # Build CREATE TABLE SQL
    escaped_table = adapter.escape_identifier(table_name)
    field_definitions = []
    foreign_keys = []

    for field in fields:
        field_name = field.get("name")
        field_type = field.get("type", "TEXT")
        is_required = field.get("required", False)
        foreign_key = field.get(
            "foreign_key"
        )  # Optional: {'table': 'tenants', 'column': 'id', 'on_delete': 'CASCADE'}

        escaped_field = adapter.escape_identifier(field_name)
        not_null = "NOT NULL" if is_required else ""

        # Handle auto-increment for 'id' fields
        if field_name == "id" and field_type.upper() in ("SERIAL", "INTEGER", "INT"):
            field_type = adapter.get_auto_increment_type()
            field_definitions.append(f"{escaped_field} {field_type} PRIMARY KEY")
        else:
            # Handle JSON types
            if field_type.upper() in ("JSON", "JSONB"):
                field_type = adapter.get_json_type()

            field_definitions.append(f"{escaped_field} {field_type} {not_null}".strip())

            # Handle foreign keys (if defined in schema)
            if foreign_key:
                fk_table = foreign_key.get("table")
                fk_column = foreign_key.get("column", "id")
                on_delete = foreign_key.get("on_delete", "CASCADE")
                foreign_keys.append(
                    f"FOREIGN KEY ({escaped_field}) REFERENCES {adapter.escape_identifier(fk_table)}({adapter.escape_identifier(fk_column)}) ON DELETE {on_delete}"
                )

    # Build SQL with foreign keys
    fields_sql = ",\n            ".join(field_definitions)
    if foreign_keys:
        fields_sql += ",\n            " + ",\n            ".join(foreign_keys)

    sql = f"CREATE TABLE IF NOT EXISTS {escaped_table} (\n            {fields_sql}\n        )"

    cursor.execute(sql)

    # Create indexes if defined
    indexes = table_def.get("indexes", [])
    for index_def in indexes:
        index_fields = index_def.get("fields", [])
        index_type = index_def.get("type", "btree")
        if index_fields:
            index_sql = adapter.create_index_sql(
                table=table_name, fields=index_fields, index_type=index_type
            )
            cursor.execute(index_sql)


def init_schema_from_config(schema_config: dict[str, Any], adapter=None):
    """
    Initialize schema from configuration (Option 2).

    Args:
        schema_config: Schema configuration dict (from schema loader)
        adapter: Database adapter (auto-detected if None)
    """
    if adapter is None:
        adapter = get_database_adapter()

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Create metadata tables first
            create_metadata_tables(cursor)

            # Create business tables from config
            tables = schema_config.get("tables", [])
            for table_def in tables:
                create_table_from_definition(cursor, table_def, adapter)

            # Create metadata table indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_expression_profile_tenant
                ON expression_profile(tenant_id, table_name, field_name)
            """
            )

            conn.commit()
            print(f"Schema initialized successfully from config ({len(tables)} tables)")
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
