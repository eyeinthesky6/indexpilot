"""Query optimization utilities to leverage PostgreSQL's built-in query plan cache"""

import logging

from src.type_definitions import QueryParams

logger = logging.getLogger(__name__)


def prepare_query_for_caching(query: str, _use_prepared_statements: bool = True) -> str:
    """
    Optimize query for PostgreSQL's query plan cache.

    PostgreSQL automatically caches query plans, but we can optimize for better cache hits:
    1. Use parameterized queries (already done via psycopg2)
    2. Use consistent query patterns
    3. Avoid dynamic SQL where possible

    Args:
        query: SQL query string
        _use_prepared_statements: Reserved for future use

    Returns:
        Optimized query string (same as input, but validated)
    """
    # PostgreSQL automatically caches plans for parameterized queries
    # No transformation needed - just ensure queries are parameterized

    # Validate that query uses parameterized placeholders
    if "%s" not in query and "$1" not in query:
        logger.debug(
            "Query doesn't use parameterized placeholders - consider using parameterized queries for better plan caching"
        )

    return query


def get_query_cache_hints() -> dict[str, str]:
    """
    Get hints for optimizing PostgreSQL query plan cache usage.

    Returns:
        dict with optimization hints
    """
    return {
        "use_parameterized_queries": "Always use %s placeholders, never string formatting",
        "consistent_query_patterns": "Use consistent query structures for better cache hits",
        "avoid_dynamic_sql": "Minimize dynamic SQL generation - use parameterized queries",
        "connection_pooling": "Use connection pooling to share cached plans across connections",
        "prepared_statements": "PostgreSQL automatically caches plans for prepared statements",
        "statistics_updates": "Keep table statistics updated (ANALYZE) for optimal plan selection",
        "index_usage": "Create indexes to improve plan cache effectiveness",
    }


def explain_query_plan(query: str, params: QueryParams | None = None) -> str:
    """
    Get EXPLAIN output for a query to verify plan caching.

    This helps verify that PostgreSQL is using cached plans effectively.

    Args:
        query: SQL query
        params: Query parameters

    Returns:
        EXPLAIN output as string
    """
    from src.db import get_connection

    explain_query = f"EXPLAIN (FORMAT JSON) {query}"

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(explain_query, params)
            else:
                cursor.execute(explain_query)

            result = cursor.fetchone()
            cursor.close()

            if result:
                import json

                return json.dumps(result[0], indent=2)
            return "No plan available"
    except Exception as e:
        logger.error(f"Failed to explain query plan: {e}")
        return f"Error: {e}"
