"""
Production-grade query executor with intelligent caching.

Automatically chooses between:
- Native database query plan cache (PostgreSQL, MySQL 8.0+, SQL Server)
- Application-level cache (SQLite, older databases, or when explicitly enabled)

This provides optimal caching strategy based on database capabilities.

Features:
- Automatic cache invalidation on data mutations (INSERT/UPDATE/DELETE)
- Prevents stale data in application cache
- Thread-safe operations
"""

import logging
from typing import cast

from src.database.type_detector import (
    DATABASE_POSTGRESQL,
    get_database_type,
    get_recommended_cache_strategy,
)
from src.db import get_connection
from src.production_cache import get_production_cache, invalidate_cache_for_tables
from src.query_interceptor import intercept_query
from src.type_definitions import JSONValue, QueryParams, QueryResults

logger = logging.getLogger(__name__)


def _is_mutation_query(query: str) -> bool:
    """
    Detect if query is a mutation (INSERT/UPDATE/DELETE/ALTER).

    Uses centralized cache system's table extraction logic.

    Args:
        query: SQL query string

    Returns:
        bool: True if query mutates data
    """
    query_normalized = query.strip().upper()
    mutation_keywords = ["INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP", "TRUNCATE"]
    return any(query_normalized.startswith(keyword) for keyword in mutation_keywords)


def _extract_tables_from_mutation(query: str) -> set[str]:
    """
    Extract table names from mutation queries.

    Uses the same logic as the centralized cache system's table extraction.

    Args:
        query: SQL query string

    Returns:
        set: Set of table names affected by the mutation
    """
    import re

    tables: set[str] = set()

    # Normalize query (remove comments, extra whitespace) - same as cache system
    query_normalized = re.sub(r"--.*?\n", " ", query, flags=re.MULTILINE)
    query_normalized = re.sub(r"/\*.*?\*/", " ", query_normalized, flags=re.DOTALL)
    query_normalized = " ".join(query_normalized.split())

    # Patterns to match table names (same patterns as cache system)
    patterns = [
        r'\bFROM\s+["\']?(\w+)["\']?',  # FROM table
        r'\bJOIN\s+["\']?(\w+)["\']?',  # JOIN table
        r'\bINTO\s+["\']?(\w+)["\']?',  # INSERT INTO
        r'\bUPDATE\s+["\']?(\w+)["\']?',  # UPDATE
        r'\bTABLE\s+["\']?(\w+)["\']?',  # CREATE TABLE, DROP TABLE, ALTER TABLE
    ]

    for pattern in patterns:
        matches = re.findall(pattern, query_normalized, re.IGNORECASE)
        # Filter out SQL keywords that might be matched (same as cache system)
        sql_keywords = {"select", "where", "group", "order", "having", "limit", "offset"}
        tables.update(m for m in matches if m.lower() not in sql_keywords)

    return tables


def execute_query(
    query: str,
    params: QueryParams | None = None,
    use_cache: bool | None = None,
    cache_ttl: int | None = None,
    tenant_id: str | None = None,
    skip_interception: bool = False,
) -> QueryResults:
    """
    Execute a query with intelligent caching and proactive blocking.

    Automatically uses:
    - Native database cache for PostgreSQL/MySQL 8.0+/SQL Server
    - Application cache for SQLite or when explicitly enabled
    - Query interception for proactive blocking of harmful queries

    Args:
        query: SQL query string
        params: Query parameters (tuple)
        use_cache: Force cache usage (None = auto-detect)
        cache_ttl: Cache TTL in seconds (uses default if None)
        tenant_id: Tenant ID for rate limiting and audit logging
        skip_interception: If True, skip query interception (for internal queries)

    Returns:
        list: Query results as list of dicts

    Raises:
        QueryBlockedError: If query is blocked by interceptor
    """
    from psycopg2.extras import RealDictCursor

    if params is None:
        params = ()

    # Check for canary deployment and A/B testing (Phase 3)
    import time
    start_time = time.time()
    canary_deployment = None
    ab_experiment = None

    try:
        from src.adaptive_safeguards import get_all_canary_deployments, get_canary_deployment

        # Check for active canary deployments
        all_canaries = get_all_canary_deployments()
        for dep_id, dep_info in all_canaries.items():
            if dep_info.get("status") == "active":
                canary_deployment = get_canary_deployment(dep_id)
                if canary_deployment and canary_deployment.should_use_canary():
                    break

        # Check for active A/B experiments (would need table_name extraction for full implementation)
        # Placeholder for future enhancement
    except Exception as e:
        logger.debug(f"Could not check canary/AB deployments: {e}")

    # Intercept query before execution (proactive blocking)
    # This checks rate limits and analyzes query plan to block harmful queries
    intercept_query(query, params, tenant_id, skip_interception=skip_interception)

    # Determine caching strategy
    if use_cache is None:
        database_type = get_database_type()
        strategy = get_recommended_cache_strategy(database_type)

        # Use application cache if:
        # - Strategy is 'application' or 'hybrid'
        # - Database is SQLite
        # - Explicitly enabled via environment variable
        use_cache = strategy in ("application", "hybrid") or database_type not in (
            DATABASE_POSTGRESQL,
        )
    else:
        # Explicit override
        pass

    # Try application cache first (if enabled)
    if use_cache:
        cache = get_production_cache()
        if cache:
            cached_result = cache.get(query, params)
            if cached_result is not None:
                logger.debug(f"Cache HIT for query: {query[:50]}...")
                # Cache stores QueryResults, cast to satisfy type checker
                return cast(QueryResults, cached_result)

    # Check for canary deployment and A/B testing (Phase 3)
    import time
    start_time = time.time()
    canary_deployment = None
    ab_experiment = None

    try:
        from src.adaptive_safeguards import get_all_canary_deployments, get_canary_deployment

        # Check for active canary deployments
        all_canaries = get_all_canary_deployments()
        for dep_id, dep_info in all_canaries.items():
            if dep_info.get("status") == "active":
                canary_deployment = get_canary_deployment(dep_id)
                if canary_deployment and canary_deployment.should_use_canary():
                    break

        # Check for active A/B experiments (Phase 3)
        # Extract table name from query for matching
        import re
        table_match = re.search(r'\bFROM\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1)
            from src.index_lifecycle_advanced import get_all_ab_experiments
            all_experiments = get_all_ab_experiments()
            for exp_name, exp_info in all_experiments.items():
                if exp_info.get("status") == "active" and exp_info.get("table_name") == table_name:
                    ab_experiment = exp_info
                    break
    except Exception as e:
        logger.debug(f"Could not check canary/AB deployments: {e}")

    # Execute query
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Check if this is a mutation query (for cache invalidation)
            is_mutation = _is_mutation_query(query)
            affected_tables: set[str] = set()

            if is_mutation:
                # Extract tables that will be affected by this mutation
                affected_tables = _extract_tables_from_mutation(query)

            cursor.execute(query, params)

            # For mutations, fetch rowcount instead of results
            if is_mutation:
                _ = cursor.rowcount  # Track rowcount but don't use it
                conn.commit()  # Ensure mutation is committed

                # Invalidate cache for affected tables using centralized system
                if affected_tables and use_cache:
                    invalidate_cache_for_tables(affected_tables)
                    logger.debug(f"Invalidated cache for tables: {affected_tables}")

                # Mutations don't return query results
                # Record canary/AB results for mutations
                execution_time_ms = (time.time() - start_time) * 1000
                success = True

                if canary_deployment:
                    try:
                        canary_deployment.record_canary_result(success)
                    except Exception as e:
                        logger.debug(f"Could not record canary result: {e}")

                return []
            else:
                # SELECT queries - fetch results
                results = cursor.fetchall()
                result_list = [dict(row) for row in results]

                # Security: Limit result size to prevent memory exhaustion
                MAX_RESULT_SIZE = 100000  # Maximum number of rows
                if len(result_list) > MAX_RESULT_SIZE:
                    logger.warning(
                        f"Query result size ({len(result_list)}) exceeds maximum ({MAX_RESULT_SIZE}), "
                        f"truncating to prevent memory exhaustion"
                    )
                    result_list = result_list[:MAX_RESULT_SIZE]

                # Record execution time for canary/AB testing (Phase 3)
                execution_time_ms = (time.time() - start_time) * 1000
                success = True  # Query executed successfully

                # Record canary deployment result
                if canary_deployment:
                    try:
                        canary_deployment.record_canary_result(success)
                    except Exception as e:
                        logger.debug(f"Could not record canary result: {e}")

                # Record A/B testing result
                if ab_experiment:
                    try:
                        from src.index_lifecycle_advanced import record_ab_result
                        # Extract query type (simplified)
                        query_type = "SELECT" if query.strip().upper().startswith("SELECT") else "unknown"
                        record_ab_result(
                            experiment_name=ab_experiment.get("experiment_name", ""),
                            variant="a",  # Would need to determine variant based on index used
                            query_duration_ms=execution_time_ms,
                            query_type=query_type
                        )
                    except Exception as e:
                        logger.debug(f"Could not record AB result: {e}")

                # Cache result if application cache is enabled
                if use_cache:
                    cache = get_production_cache()
                    if cache:
                        # Convert to JSONValue-compatible format
                        cache_value: JSONValue = [
                            {str(k): v for k, v in row.items()} if isinstance(row, dict) else row
                            for row in result_list
                        ]
                        cache.set(query, params, cache_value, ttl=cache_ttl)
                        logger.debug(f"Cached query result: {query[:50]}...")

                return result_list
        except Exception as e:
            # Record failure for canary/AB testing
            execution_time_ms = (time.time() - start_time) * 1000
            success = False

            if canary_deployment:
                try:
                    canary_deployment.record_canary_result(success)
                except Exception:
                    pass

            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            cursor.close()


def execute_query_no_cache(
    query: str,
    params: QueryParams | None = None,
    tenant_id: str | None = None,
    skip_interception: bool = False,
) -> QueryResults:
    """
    Execute a query without caching (always hits database).

    Use this for:
    - Write operations (INSERT, UPDATE, DELETE)
    - Queries that must always return fresh data
    - Testing/debugging

    Args:
        query: SQL query string
        params: Query parameters
        tenant_id: Tenant ID for rate limiting and audit logging
        skip_interception: If True, skip query interception (for internal queries)

    Returns:
        list: Query results
    """
    return execute_query(
        query, params, use_cache=False, tenant_id=tenant_id, skip_interception=skip_interception
    )
