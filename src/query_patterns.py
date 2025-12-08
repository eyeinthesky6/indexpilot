"""Query pattern detection for smart indexing"""

from psycopg2.extras import RealDictCursor

from src.db import get_connection


def detect_query_patterns(table_name, field_name, time_window_hours=24):
    """
    Detect query patterns for a field (exact match, LIKE, range, etc.)

    Returns:
        dict with pattern information
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get sample queries that used this field
            # Note: We'd need to store actual queries for this, but for now
            # we'll infer from field usage stats
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_queries,
                    AVG(duration_ms) as avg_duration
                FROM query_stats
                WHERE table_name = %s
                  AND field_name = %s
                  AND created_at >= NOW() - INTERVAL '1 hour' * %s
            """,
                (table_name, field_name, time_window_hours),
            )

            result = cursor.fetchone()
            if not result or result["total_queries"] == 0:
                return {
                    "has_like": False,
                    "has_exact": False,
                    "has_range": False,
                    "pattern": "unknown",
                }

            # Check field type to infer likely patterns
            # Validate identifiers first
            from src.validation import validate_field_name, validate_table_name

            table_name = validate_table_name(table_name)
            field_name = validate_field_name(field_name, table_name)

            cursor.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """,
                (table_name, field_name),
            )

            type_result = cursor.fetchone()
            field_type = type_result["data_type"] if type_result else "text"

            # Analyze query patterns from query_stats if available
            # Check for LIKE patterns (if we stored query text, we'd analyze it here)
            # For now, use field type and usage statistics to infer patterns

            # Get query duration distribution to infer pattern complexity
            cursor.execute(
                """
                SELECT
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as median_duration,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration,
                    MAX(duration_ms) as max_duration
                FROM query_stats
                WHERE table_name = %s
                  AND field_name = %s
                  AND created_at >= NOW() - INTERVAL '1 hour' * %s
            """,
                (table_name, field_name, time_window_hours),
            )

            duration_stats = cursor.fetchone()

            # Infer patterns based on field type and query characteristics
            # Text fields are more likely to use LIKE, numeric fields use ranges
            has_like = field_type in ["text", "varchar", "character varying"]
            has_range = field_type in [
                "integer",
                "numeric",
                "bigint",
                "timestamp",
                "date",
                "timestamp with time zone",
            ]

            # If queries are consistently fast, likely exact matches
            # If there's high variance, might be LIKE or range queries
            pattern = "exact"  # Default
            if duration_stats and duration_stats["median_duration"]:
                duration_variance = (duration_stats["p95_duration"] or 0) - (
                    duration_stats["median_duration"] or 0
                )
                if duration_variance > duration_stats["median_duration"] * 2:
                    # High variance suggests LIKE or complex queries
                    if has_like:
                        pattern = "like"
                    elif has_range:
                        pattern = "range"

            # ✅ INTEGRATION: Check for multi-dimensional patterns (iDistance)
            is_multi_dimensional = False
            try:
                from src.pattern_detection import detect_multi_dimensional_pattern

                multi_dim_result = detect_multi_dimensional_pattern(
                    table_name=table_name,
                    field_names=[
                        field_name
                    ],  # Single field, but check if multi-dimensional patterns exist
                )
                is_multi_dimensional_val = multi_dim_result.get("is_multi_dimensional", False)
                is_multi_dimensional = (
                    bool(is_multi_dimensional_val)
                    if isinstance(is_multi_dimensional_val, bool)
                    else False
                )
            except Exception:
                pass  # Silently fail if pattern detection unavailable

            # ✅ INTEGRATION: Check for temporal patterns (Bx-tree)
            is_temporal = False
            try:
                from src.pattern_detection import detect_temporal_pattern

                temporal_result = detect_temporal_pattern(
                    table_name=table_name,
                    field_name=field_name,
                    query_patterns={"field_type": field_type},
                )
                is_temporal_val = temporal_result.get("is_temporal", False)
                is_temporal = bool(is_temporal_val) if isinstance(is_temporal_val, bool) else False
            except Exception:
                pass  # Silently fail if pattern detection unavailable

            patterns = {
                "has_like": has_like,
                "has_exact": True,  # Most queries include exact matches
                "has_range": has_range,
                "pattern": pattern,
                "median_duration_ms": duration_stats["median_duration"] if duration_stats else None,
                "p95_duration_ms": duration_stats["p95_duration"] if duration_stats else None,
                "is_multi_dimensional": is_multi_dimensional,  # iDistance integration
                "is_temporal": is_temporal,  # Bx-tree integration
            }

            return patterns
        finally:
            cursor.close()


def get_null_ratio(table_name, field_name):
    """Get the ratio of NULL values in a field"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Validate identifiers to prevent SQL injection
            from src.validation import validate_field_name, validate_table_name

            table_name = validate_table_name(table_name)
            field_name = validate_field_name(field_name, table_name)

            # Use parameterized query with identifier quoting
            from psycopg2 import sql

            query = sql.SQL(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT({}) as non_null
                FROM {}
            """
            ).format(sql.Identifier(field_name), sql.Identifier(table_name))
            cursor.execute(query)
            result = cursor.fetchone()
            if result and result["total"] > 0:
                null_count = result["total"] - result["non_null"]
                return null_count / result["total"]
            return 0.0
        except Exception:
            # If field doesn't exist or query fails, return 0
            return 0.0
        finally:
            cursor.close()
