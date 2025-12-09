"""Genome catalog operations - canonical schema definition"""

from psycopg2.extras import RealDictCursor

from src.db import get_connection, get_cursor
from src.schema.loader import convert_schema_to_genome_fields
from src.type_definitions import JSONDict


def bootstrap_genome_catalog():
    """Bootstrap the genome_catalog with the mini-CRM schema definition"""

    # Define the canonical schema
    genome_fields = [
        # Tenants table
        ("tenants", "id", "SERIAL", True, True, True, "core"),
        ("tenants", "name", "TEXT", True, True, True, "core"),
        ("tenants", "created_at", "TIMESTAMP", False, True, True, "core"),
        # Contacts table
        ("contacts", "id", "SERIAL", True, True, True, "core"),
        ("contacts", "tenant_id", "INTEGER", True, True, True, "core"),
        ("contacts", "name", "TEXT", True, True, True, "core"),
        ("contacts", "email", "TEXT", False, True, True, "core"),
        ("contacts", "phone", "TEXT", False, True, True, "core"),
        ("contacts", "custom_text_1", "TEXT", False, True, False, "custom"),
        ("contacts", "custom_text_2", "TEXT", False, True, False, "custom"),
        ("contacts", "custom_number_1", "NUMERIC", False, True, False, "custom"),
        ("contacts", "custom_number_2", "NUMERIC", False, True, False, "custom"),
        ("contacts", "created_at", "TIMESTAMP", False, True, True, "core"),
        ("contacts", "updated_at", "TIMESTAMP", False, True, True, "core"),
        # Organizations table
        ("organizations", "id", "SERIAL", True, True, True, "core"),
        ("organizations", "tenant_id", "INTEGER", True, True, True, "core"),
        ("organizations", "name", "TEXT", True, True, True, "core"),
        ("organizations", "industry", "TEXT", False, True, True, "core"),
        ("organizations", "custom_text_1", "TEXT", False, True, False, "custom"),
        ("organizations", "custom_text_2", "TEXT", False, True, False, "custom"),
        ("organizations", "custom_number_1", "NUMERIC", False, True, False, "custom"),
        ("organizations", "created_at", "TIMESTAMP", False, True, True, "core"),
        ("organizations", "updated_at", "TIMESTAMP", False, True, True, "core"),
        # Interactions table
        ("interactions", "id", "SERIAL", True, True, True, "core"),
        ("interactions", "tenant_id", "INTEGER", True, True, True, "core"),
        ("interactions", "contact_id", "INTEGER", False, True, True, "core"),
        ("interactions", "org_id", "INTEGER", False, True, True, "core"),
        ("interactions", "type", "TEXT", True, True, True, "core"),
        ("interactions", "occurred_at", "TIMESTAMP", False, True, True, "core"),
        ("interactions", "metadata_json", "JSONB", False, False, True, "core"),
    ]

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for (
                table_name,
                field_name,
                field_type,
                is_required,
                is_indexable,
                default_expression,
                feature_group,
            ) in genome_fields:
                cursor.execute(
                    """
                    INSERT INTO genome_catalog
                    (table_name, field_name, field_type, is_required, is_indexable, default_expression, feature_group)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (table_name, field_name)
                    DO UPDATE SET
                        field_type = EXCLUDED.field_type,
                        is_required = EXCLUDED.is_required,
                        is_indexable = EXCLUDED.is_indexable,
                        default_expression = EXCLUDED.default_expression,
                        feature_group = EXCLUDED.feature_group,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        table_name,
                        field_name,
                        field_type,
                        is_required,
                        is_indexable,
                        default_expression,
                        feature_group,
                    ),
                )

            conn.commit()
            print(f"Bootstrapped {len(genome_fields)} fields in genome_catalog")
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def get_genome_fields(table_name=None):
    """Get all fields from genome catalog, optionally filtered by table"""
    with get_cursor() as cursor:
        if table_name:
            cursor.execute(
                """
                SELECT * FROM genome_catalog
                WHERE table_name = %s
                ORDER BY table_name, field_name
            """,
                (table_name,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM genome_catalog
                ORDER BY table_name, field_name
            """
            )
        return cursor.fetchall()


def get_all_genome_fields():
    """Get all fields from genome catalog (alias for get_genome_fields())"""
    return get_genome_fields()


# New extensible functions (Option 2: Configuration-Based)


def bootstrap_genome_catalog_from_schema(schema_config: JSONDict):
    """
    Bootstrap genome catalog from schema configuration (Option 2).

    Args:
        schema_config: Schema configuration dict (from schema loader)
    """
    # Convert schema to genome fields format
    genome_fields = convert_schema_to_genome_fields(schema_config)

    if not genome_fields:
        print("No fields found in schema configuration")
        return

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for (
                table_name,
                field_name,
                field_type,
                is_required,
                is_indexable,
                default_expression,
                feature_group,
            ) in genome_fields:
                cursor.execute(
                    """
                    INSERT INTO genome_catalog
                    (table_name, field_name, field_type, is_required, is_indexable, default_expression, feature_group)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (table_name, field_name)
                    DO UPDATE SET
                        field_type = EXCLUDED.field_type,
                        is_required = EXCLUDED.is_required,
                        is_indexable = EXCLUDED.is_indexable,
                        default_expression = EXCLUDED.default_expression,
                        feature_group = EXCLUDED.feature_group,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        table_name,
                        field_name,
                        field_type,
                        is_required,
                        is_indexable,
                        default_expression,
                        feature_group,
                    ),
                )

            conn.commit()
            print(f"Bootstrapped {len(genome_fields)} fields in genome_catalog from schema config")
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


if __name__ == "__main__":
    bootstrap_genome_catalog()
