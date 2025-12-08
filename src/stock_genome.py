"""Bootstrap genome catalog for stock market schema

Registers stock market fields in the genome_catalog table for IndexPilot awareness.
"""

import logging

from psycopg2.extras import RealDictCursor

from src.db import get_connection

logger = logging.getLogger(__name__)


def bootstrap_stock_genome_catalog():
    """
    Bootstrap the genome_catalog with stock market schema definition.

    Registers all stock market fields so IndexPilot can track and optimize them.
    """
    # Define the stock market schema fields
    genome_fields = [
        # Stocks table
        ("stocks", "id", "SERIAL", True, True, True, "core"),
        ("stocks", "symbol", "TEXT", True, True, True, "core"),
        ("stocks", "name", "TEXT", False, True, True, "core"),
        ("stocks", "sector", "TEXT", False, True, True, "core"),
        ("stocks", "created_at", "TIMESTAMP", False, True, True, "core"),
        # Stock prices table
        ("stock_prices", "id", "SERIAL", True, True, True, "core"),
        ("stock_prices", "stock_id", "INTEGER", True, True, True, "core"),
        ("stock_prices", "timestamp", "TIMESTAMP", True, True, True, "core"),
        ("stock_prices", "open", "NUMERIC", False, True, True, "price"),
        ("stock_prices", "high", "NUMERIC", False, True, True, "price"),
        ("stock_prices", "low", "NUMERIC", False, True, True, "price"),
        ("stock_prices", "close", "NUMERIC", False, True, True, "price"),
        ("stock_prices", "volume", "BIGINT", False, True, True, "volume"),
        ("stock_prices", "created_at", "TIMESTAMP", False, True, True, "core"),
    ]

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            inserted = 0
            updated = 0

            for (
                table_name,
                field_name,
                field_type,
                is_required,
                is_indexable,
                default_expression,
                feature_group,
            ) in genome_fields:
                # Check if already exists
                cursor.execute(
                    """
                    SELECT id FROM genome_catalog
                    WHERE table_name = %s AND field_name = %s
                """,
                    (table_name, field_name),
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE genome_catalog
                        SET field_type = %s,
                            is_required = %s,
                            is_indexable = %s,
                            default_expression = %s,
                            feature_group = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE table_name = %s AND field_name = %s
                    """,
                        (
                            field_type,
                            is_required,
                            is_indexable,
                            default_expression,
                            feature_group,
                            table_name,
                            field_name,
                        ),
                    )
                    updated += 1
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO genome_catalog
                        (table_name, field_name, field_type, is_required,
                         is_indexable, default_expression, feature_group)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
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
                    inserted += 1

            conn.commit()
            logger.info(
                f"Stock genome catalog bootstrapped: {inserted} inserted, {updated} updated"
            )
            print(f"Stock genome catalog bootstrapped: {inserted} inserted, {updated} updated")

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    try:
        bootstrap_stock_genome_catalog()
        print("Stock genome catalog bootstrap complete!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to bootstrap stock genome catalog: {e}")
        print(f"Error: {e}")
        sys.exit(1)

