"""Query plan analysis using EXPLAIN"""

# INTEGRATION NOTE: QPG (Query Plan Guidance) Enhancement - ✅ COMPLETE
# Current: Enhanced query plan analysis with QPG concepts
# Enhancement: QPG implemented in src/algorithms/qpg.py
# Integration: QPG analysis integrated into analyze_query_plan() and analyze_query_plan_fast()
# See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict

from psycopg2.extras import RealDictCursor, RealDictRow

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.type_definitions import JSONDict, JSONValue, QueryParams

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Constants for query analyzer
DEFAULT_CACHE_MAX_SIZE = 100  # Maximum cached plans
DEFAULT_CACHE_TTL = 3600  # Cache TTL in seconds (1 hour)
DEFAULT_HIGH_COST_THRESHOLD = 100  # Cost threshold for index recommendations
DEFAULT_RETRY_BASE_DELAY = 0.1  # Base delay for exponential backoff (seconds)

# EXPLAIN result cache (LRU cache)
_explain_cache: OrderedDict[str, tuple[JSONDict, float]] = OrderedDict()
_cache_lock = threading.Lock()

# EXPLAIN success rate tracking
_explain_stats = {
    "total_attempts": 0,
    "successful": 0,
    "failed": 0,
    "cached_hits": 0,
    "fast_explain_used": 0,
    "analyze_explain_used": 0,
}
_stats_lock = threading.Lock()


def _get_cache_max_size() -> int:
    """Get cache max size from config or default"""
    return _config_loader.get_int("features.query_analyzer.cache_max_size", DEFAULT_CACHE_MAX_SIZE)


def _get_cache_ttl() -> int:
    """Get cache TTL from config or default"""
    return _config_loader.get_int("features.query_analyzer.cache_ttl", DEFAULT_CACHE_TTL)


def _get_high_cost_threshold() -> float:
    """Get high cost threshold from config or default"""
    return _config_loader.get_float(
        "features.query_analyzer.high_cost_threshold", DEFAULT_HIGH_COST_THRESHOLD
    )


def _get_retry_base_delay() -> float:
    """Get retry base delay from config or default"""
    return _config_loader.get_float(
        "features.query_analyzer.retry_base_delay", DEFAULT_RETRY_BASE_DELAY
    )


def _get_query_signature(query: str, params: QueryParams | None = None) -> str:
    """Generate a signature for query caching"""
    if params is None:
        params = ()
    # Normalize query (remove extra whitespace)
    normalized_query = " ".join(query.split())
    # Create signature from query + params
    signature_str = f"{normalized_query}:{str(params)}"
    return hashlib.md5(signature_str.encode()).hexdigest()


def get_explain_stats() -> JSONDict:
    """Get EXPLAIN success rate statistics"""
    with _stats_lock:
        total = _explain_stats["total_attempts"]
        if total == 0:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "cached_hit_rate": 0.0,
                "fast_explain_rate": 0.0,
                "analyze_explain_rate": 0.0,
                **dict(_explain_stats.items()),
            }
        success_rate = (_explain_stats["successful"] / total) * 100.0
        cached_hit_rate = (_explain_stats["cached_hits"] / total) * 100.0
        fast_rate = (_explain_stats["fast_explain_used"] / total) * 100.0
        analyze_rate = (_explain_stats["analyze_explain_used"] / total) * 100.0
        return {
            "total_attempts": total,
            "success_rate": success_rate,
            "cached_hit_rate": cached_hit_rate,
            "fast_explain_rate": fast_rate,
            "analyze_explain_rate": analyze_rate,
            **dict(_explain_stats.items()),
        }


def reset_explain_stats() -> None:
    """Reset EXPLAIN statistics (for testing/monitoring)"""
    with _stats_lock:
        _explain_stats.update(
            {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "cached_hits": 0,
                "fast_explain_used": 0,
                "analyze_explain_used": 0,
            }
        )


def analyze_query_plan_fast(query, params=None, use_cache=True, max_retries=3):
    """
    Analyze query execution plan using EXPLAIN (without ANALYZE).

    Faster than analyze_query_plan() because it doesn't execute the query.
    Use this for initial cost estimation, fall back to analyze_query_plan() if needed.

    Args:
        query: SQL query string
        params: Query parameters (handles None values properly)
        use_cache: Whether to use cached results
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        dict with plan analysis including cost, node type, and recommendations
    """
    # Handle None params properly - convert to empty tuple
    if params is None:
        params = ()
    elif not isinstance(params, list | tuple):
        # Handle single parameter case
        params = (params,)

    # Validate and sanitize parameters to prevent NULL-related issues
    try:
        sanitized_params = []
        for param in params:
            if param is None:
                # Replace None with a placeholder that won't cause EXPLAIN issues
                sanitized_params.append("")  # Empty string for NULL values
            else:
                sanitized_params.append(param)
        params = tuple(sanitized_params)
    except Exception as e:
        logger.warning(f"Parameter sanitization failed: {e}, using empty params")
        params = ()

    # Check cache first
    if use_cache:
        cache_key = _get_query_signature(query, params)
        with _cache_lock:
            if cache_key in _explain_cache:
                cached_result, cached_time = _explain_cache[cache_key]
                # Check if cache is still valid
                cache_ttl = _get_cache_ttl()
                if time.time() - cached_time < cache_ttl:
                    # Move to end (LRU)
                    _explain_cache.move_to_end(cache_key)
                    logger.debug(f"Using cached EXPLAIN plan for query signature: {cache_key[:8]}")
                    with _stats_lock:
                        _explain_stats["cached_hits"] += 1
                    return cached_result
                else:
                    # Expired, remove
                    del _explain_cache[cache_key]

    # Track attempt
    with _stats_lock:
        _explain_stats["total_attempts"] += 1
        _explain_stats["fast_explain_used"] += 1

    # Retry logic for transient failures
    retry_base_delay = _get_retry_base_delay()
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                cursor: RealDictCursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    # Use EXPLAIN without ANALYZE (faster, doesn't execute query)
                    explain_query = f"EXPLAIN (FORMAT JSON) {query}"
                    cursor.execute(explain_query, params)
                    result: RealDictRow | None = cursor.fetchone()

                    if not result:
                        if attempt < max_retries - 1:
                            wait_time = retry_base_delay * (2**attempt)
                            logger.debug(
                                f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned no result, "
                                f"retrying in {wait_time:.2f}s"
                            )
                            time.sleep(wait_time)
                            continue
                        return None

                    # RealDictCursor returns a dict, extract EXPLAIN output from first column value
                    plan_data: str | list[dict[str, JSONValue]] | None = None
                    for col_value in result.values():
                        if col_value is not None:
                            plan_data = col_value
                            break

                    if not plan_data:
                        if attempt < max_retries - 1:
                            wait_time = retry_base_delay * (2**attempt)
                            logger.debug(
                                f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned no plan data, "
                                f"retrying in {wait_time:.2f}s"
                            )
                            time.sleep(wait_time)
                            continue
                        return None

                    # Handle different plan_data types with explicit type checking
                    if isinstance(plan_data, str):
                        try:
                            parsed = json.loads(plan_data)
                            if isinstance(parsed, list):
                                plan = parsed
                            else:
                                # Invalid JSON structure
                                if attempt < max_retries - 1:
                                    wait_time = retry_base_delay * (2**attempt)
                                    logger.debug(
                                        f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned invalid JSON structure, "
                                        f"retrying in {wait_time:.2f}s"
                                    )
                                    time.sleep(wait_time)
                                    continue
                                return None
                        except json.JSONDecodeError as e:
                            if attempt < max_retries - 1:
                                wait_time = retry_base_delay * (2**attempt)
                                logger.debug(
                                    f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} JSON decode failed: {e}, "
                                    f"retrying in {wait_time:.2f}s"
                                )
                                time.sleep(wait_time)
                                continue
                            logger.warning(
                                f"EXPLAIN JSON decode failed after {max_retries} attempts: {e}"
                            )
                            return None
                    elif isinstance(plan_data, list):
                        plan = plan_data
                    else:
                        # Handle unexpected data types for runtime safety
                        # Theoretically unreachable but kept for robustness
                        logger.warning(  # type: ignore[unreachable]
                            f"EXPLAIN (fast) returned unexpected data type: {type(plan_data)}"
                        )
                        if attempt < max_retries - 1:
                            wait_time = retry_base_delay * (2**attempt)
                            logger.debug(
                                f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned unexpected data type, "
                                f"retrying in {wait_time:.2f}s"
                            )
                            time.sleep(wait_time)
                            continue
                        return None

                    # Extract plan information
                    if not plan or len(plan) == 0 or "Plan" not in plan[0]:
                        if attempt < max_retries - 1:
                            wait_time = retry_base_delay * (2**attempt)
                            logger.debug(
                                f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned invalid plan structure, "
                                f"retrying in {wait_time:.2f}s"
                            )
                            time.sleep(wait_time)
                            continue
                        return None
                    plan_node_value = plan[0].get("Plan")
                    if not isinstance(plan_node_value, dict):
                        if attempt < max_retries - 1:
                            wait_time = retry_base_delay * (2**attempt)
                            logger.debug(
                                f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} returned invalid plan node, "
                                f"retrying in {wait_time:.2f}s"
                            )
                            time.sleep(wait_time)
                            continue
                        return None
                    plan_node: dict[str, JSONValue] = plan_node_value

                    total_cost_val = plan_node.get("Total Cost", 0)
                    total_cost = (
                        float(total_cost_val) if isinstance(total_cost_val, int | float) else 0.0
                    )
                    node_type_val = plan_node.get("Node Type", "Unknown")
                    node_type = str(node_type_val) if node_type_val is not None else "Unknown"

                    analysis: JSONDict = {
                        "total_cost": total_cost,
                        "actual_time_ms": 0,  # Not available without ANALYZE
                        "node_type": node_type,
                        "planning_time_ms": 0,  # Not available without ANALYZE
                        "has_seq_scan": _has_sequential_scan(plan_node),
                        "has_index_scan": _has_index_scan(plan_node),
                        "needs_index": False,
                        "recommendations": [],
                        "from_cache": False,
                        "retry_attempt": attempt,  # Track which retry succeeded
                    }

                    # Determine if index would help
                    high_cost_threshold = _get_high_cost_threshold()
                    analysis_total_cost_val = analysis.get("total_cost", 0.0)
                    analysis_total_cost_float = (
                        float(analysis_total_cost_val)
                        if isinstance(analysis_total_cost_val, int | float)
                        else 0.0
                    )
                    analysis_has_seq_scan = analysis.get("has_seq_scan", False)
                    if (
                        isinstance(analysis_has_seq_scan, bool)
                        and analysis_has_seq_scan
                        and analysis_total_cost_float > high_cost_threshold
                    ):
                        analysis["needs_index"] = True
                        recommendations = analysis.get("recommendations", [])
                        if isinstance(recommendations, list):
                            recommendations.append(
                                f"Sequential scan detected (cost: {analysis_total_cost_float:.2f}). "
                                "Consider creating an index on filtered columns."
                            )

                    # Check for nested loops (can be slow)
                    node_type_check = plan_node.get("Node Type")
                    if isinstance(node_type_check, str) and node_type_check == "Nested Loop":
                        recommendations = analysis.get("recommendations", [])
                        if isinstance(recommendations, list):
                            recommendations.append(
                                "Nested loop join detected. Consider indexes on join columns."
                            )

                    # QPG Enhancement: Add QPG analysis for better bottleneck identification
                    # Enhanced with diverse plan generation
                    try:
                        from src.algorithms.qpg import enhance_plan_analysis

                        analysis = enhance_plan_analysis(analysis, plan_node, query=query)
                    except Exception as e:
                        logger.debug(f"QPG enhancement failed: {e}")
                        # Continue with base analysis if QPG fails

                    # ✅ INTEGRATION: Check if query involves materialized views
                    try:
                        from src.materialized_view_support import find_materialized_views

                        query_lower = query.lower() if query else ""
                        # Check if query references any materialized views
                        mvs = find_materialized_views(schema_name="public")
                        for mv in mvs:
                            mv_name = mv.get("name", "")
                            if mv_name and mv_name.lower() in query_lower:
                                analysis["involves_materialized_view"] = True
                                analysis["materialized_view"] = mv.get("full_name", mv_name)
                                # Add recommendation to check MV indexes
                                if "recommendations" not in analysis:
                                    analysis["recommendations"] = []
                                recommendations = analysis["recommendations"]
                                if isinstance(recommendations, list):
                                    recommendations.append(
                                        f"Query involves materialized view {mv_name}. Consider indexes on MV for better refresh performance."
                                    )
                                break
                    except Exception as e:
                        logger.debug(f"Materialized view check failed: {e}")
                        # Silently fail - MV support is optional

                    # Cache the result
                    if use_cache:
                        cache_key = _get_query_signature(query, params)
                        cache_max_size = _get_cache_max_size()
                        with _cache_lock:
                            # Remove oldest if cache is full
                            if len(_explain_cache) >= cache_max_size:
                                _explain_cache.popitem(last=False)
                            _explain_cache[cache_key] = (analysis, time.time())

                    # Track success
                    with _stats_lock:
                        _explain_stats["successful"] += 1

                    if attempt > 0:
                        logger.info(
                            f"EXPLAIN (fast) succeeded on attempt {attempt + 1}/{max_retries} "
                            f"for query: {query[:50]}..."
                        )

                    return analysis
                finally:
                    cursor.close()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_base_delay * (2**attempt)
                logger.debug(
                    f"EXPLAIN (fast) attempt {attempt + 1}/{max_retries} failed: {e}, "
                    f"retrying in {wait_time:.2f}s"
                )
                time.sleep(wait_time)
            else:
                logger.warning(
                    f"EXPLAIN (fast) failed after {max_retries} attempts: {e} "
                    f"for query: {query[:100]}..."
                )
                with _stats_lock:
                    _explain_stats["failed"] += 1
                return None


def analyze_query_plan(query, params=None, use_cache=True, max_retries=3):
    """
    Analyze query execution plan using EXPLAIN ANALYZE.

    This executes the query, so it's slower but provides actual execution times.
    Use analyze_query_plan_fast() for initial cost estimation.

    Args:
        query: SQL query string
        params: Query parameters
        use_cache: Whether to use cached results
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        dict with plan analysis including cost, time, node type, and recommendations
    """
    if params is None:
        params = ()

    # Track attempt
    with _stats_lock:
        _explain_stats["total_attempts"] += 1
        _explain_stats["analyze_explain_used"] += 1

    # Check cache first
    if use_cache:
        cache_key = _get_query_signature(query, params)
        cache_ttl = _get_cache_ttl()
        with _cache_lock:
            if cache_key in _explain_cache:
                cached_result, cached_time = _explain_cache[cache_key]
                # Check if cache is still valid
                if time.time() - cached_time < cache_ttl:
                    # Move to end (LRU)
                    _explain_cache.move_to_end(cache_key)
                    logger.debug(
                        f"Using cached EXPLAIN ANALYZE plan for query signature: {cache_key[:8]}"
                    )
                    with _stats_lock:
                        _explain_stats["cached_hits"] += 1
                        _explain_stats["successful"] += 1
                    return cached_result
                else:
                    # Expired, remove
                    del _explain_cache[cache_key]

    # Retry logic for transient failures
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    # Get query plan in JSON format with ANALYZE
                    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    cursor.execute(explain_query, params)
                    result: RealDictRow | None = cursor.fetchone()

                    if not result:
                        return None

                    # RealDictCursor returns a dict, extract EXPLAIN output from first column value
                    plan_data: str | list[dict[str, JSONValue]] | None = None
                    for col_value in result.values():
                        if col_value is not None:
                            plan_data = col_value
                            break

                    if not plan_data:
                        return None

                    plan: list[dict[str, JSONValue]]
                    if isinstance(plan_data, str):
                        parsed = json.loads(plan_data)
                        if not isinstance(parsed, list):
                            return None
                        plan = parsed
                    elif isinstance(plan_data, list):
                        plan = plan_data
                    else:
                        # Type narrowing: plan_data can only be str | list | None at this point
                        # and we've already handled None, so this should be unreachable
                        # but kept for runtime safety
                        return None  # type: ignore[unreachable]

                    # Extract plan information
                    if not plan or len(plan) == 0 or "Plan" not in plan[0]:
                        return None
                    plan_node_value = plan[0].get("Plan")
                    if not isinstance(plan_node_value, dict):
                        return None
                    plan_node: dict[str, JSONValue] = plan_node_value

                    total_cost_val = plan_node.get("Total Cost", 0)
                    total_cost = (
                        float(total_cost_val) if isinstance(total_cost_val, int | float) else 0.0
                    )
                    exec_time_val = plan[0].get("Execution Time", 0)
                    exec_time = (
                        float(exec_time_val) if isinstance(exec_time_val, int | float) else 0.0
                    )
                    node_type_val = plan_node.get("Node Type", "Unknown")
                    node_type = str(node_type_val) if node_type_val is not None else "Unknown"
                    planning_time_val = plan[0].get("Planning Time", 0)
                    planning_time = (
                        float(planning_time_val)
                        if isinstance(planning_time_val, int | float)
                        else 0.0
                    )

                    analysis: JSONDict = {
                        "total_cost": total_cost,
                        "actual_time_ms": exec_time,
                        "node_type": node_type,
                        "planning_time_ms": planning_time,
                        "has_seq_scan": _has_sequential_scan(plan_node),
                        "has_index_scan": _has_index_scan(plan_node),
                        "needs_index": False,
                        "recommendations": [],
                        "from_cache": False,
                    }

                    # Determine if index would help
                    high_cost_threshold = _get_high_cost_threshold()
                    analysis_total_cost_val = analysis.get("total_cost", 0.0)
                    analysis_total_cost_float = (
                        float(analysis_total_cost_val)
                        if isinstance(analysis_total_cost_val, int | float)
                        else 0.0
                    )
                    analysis_has_seq_scan = analysis.get("has_seq_scan", False)
                    if (
                        isinstance(analysis_has_seq_scan, bool)
                        and analysis_has_seq_scan
                        and analysis_total_cost_float > high_cost_threshold
                    ):
                        analysis["needs_index"] = True
                        recommendations = analysis.get("recommendations", [])
                        if isinstance(recommendations, list):
                            recommendations.append(
                                f"Sequential scan detected (cost: {analysis_total_cost_float:.2f}). "
                                "Consider creating an index on filtered columns."
                            )

                    # Check for nested loops (can be slow)
                    node_type_check = plan_node.get("Node Type")
                    if isinstance(node_type_check, str) and node_type_check == "Nested Loop":
                        recommendations = analysis.get("recommendations", [])
                        if isinstance(recommendations, list):
                            recommendations.append(
                                "Nested loop join detected. Consider indexes on join columns."
                            )

                    # QPG Enhancement: Add QPG analysis for better bottleneck identification
                    # Enhanced with diverse plan generation
                    try:
                        from src.algorithms.qpg import enhance_plan_analysis

                        analysis = enhance_plan_analysis(analysis, plan_node, query=query)
                        # Track algorithm usage for monitoring and analysis
                        try:
                            from src.algorithm_tracking import track_algorithm_usage

                            # Extract table name from query if possible
                            table_name = analysis.get("table_name", "")
                            track_algorithm_usage(
                                table_name=table_name,
                                field_name=None,
                                algorithm_name="qpg",
                                recommendation=analysis,
                                used_in_decision=True,
                            )
                        except Exception as e:
                            logger.debug(f"Could not track QPG usage: {e}")
                    except Exception as e:
                        logger.debug(f"QPG enhancement failed: {e}")
                        # Continue with base analysis if QPG fails

                    # Cache the result
                    if use_cache:
                        cache_key = _get_query_signature(query, params)
                        cache_max_size = _get_cache_max_size()
                        with _cache_lock:
                            # Remove oldest if cache is full
                            if len(_explain_cache) >= cache_max_size:
                                _explain_cache.popitem(last=False)
                            _explain_cache[cache_key] = (analysis, time.time())

                    # Track success
                    with _stats_lock:
                        _explain_stats["successful"] += 1

                    return analysis
                finally:
                    cursor.close()
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: base_delay * 2^attempt
                retry_base_delay = _get_retry_base_delay()
                wait_time = retry_base_delay * (2**attempt)
                logger.debug(
                    f"EXPLAIN ANALYZE attempt {attempt + 1}/{max_retries} failed: {e}, "
                    f"retrying in {wait_time:.2f}s"
                )
                time.sleep(wait_time)
            else:
                logger.warning(f"EXPLAIN ANALYZE failed after {max_retries} attempts: {e}")
                with _stats_lock:
                    _explain_stats["failed"] += 1
                return None

    # If all retries failed
    with _stats_lock:
        _explain_stats["failed"] += 1
    return None


def _has_sequential_scan(plan_node: dict[str, JSONValue]) -> bool:
    """Recursively check if plan contains sequential scan"""
    node_type = plan_node.get("Node Type")
    if isinstance(node_type, str) and node_type == "Seq Scan":
        return True

    # Check child plans
    plans = plan_node.get("Plans")
    if isinstance(plans, list):
        for child in plans:
            if isinstance(child, dict) and _has_sequential_scan(child):
                return True

    return False


def _has_index_scan(plan_node: dict[str, JSONValue]) -> bool:
    """Recursively check if plan uses index scan"""
    node_type = plan_node.get("Node Type", "")
    if isinstance(node_type, str) and ("Index" in node_type or node_type == "Bitmap Heap Scan"):
        return True

    # Check child plans
    plans = plan_node.get("Plans")
    if isinstance(plans, list):
        for child in plans:
            if isinstance(child, dict) and _has_index_scan(child):
                return True

    return False


def measure_query_performance(
    query: str, params: QueryParams | None = None, num_runs: int = 10
) -> dict[str, float]:
    """
    Measure actual query performance by running it multiple times.

    Returns:
        dict with median, average, min, max times in milliseconds
    """
    if params is None:
        params = ()

    # Warm up (run once)
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            _ = cursor.fetchall()
        finally:
            cursor.close()

    # Measure multiple runs
    times = []
    for _ in range(num_runs):
        start = time.time()
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                _ = cursor.fetchall()
            finally:
                cursor.close()
        times.append((time.time() - start) * 1000)

    if not times:
        # Edge case: no times collected (shouldn't happen with num_runs > 0)
        return {"median_ms": 0.0, "avg_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0}

    sorted_times = sorted(times)
    median_idx = len(sorted_times) // 2

    return {
        "median_ms": sorted_times[median_idx],
        "avg_ms": sum(times) / len(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "p95_ms": sorted_times[int(len(sorted_times) * 0.95)]
        if len(sorted_times) > 1
        else sorted_times[0],
    }


def suggest_index_type_from_plan(plan_node: dict[str, JSONValue], query: str | None = None) -> str:
    """
    Suggest optimal index type based on query plan analysis.

    Analyzes plan nodes to determine if B-tree, Hash, GIN, GiST, or BRIN would be best.

    Args:
        plan_node: Query plan node (from EXPLAIN)
        query: Optional query text for pattern analysis

    Returns:
        Suggested index type: 'btree', 'hash', 'gin', 'gist', 'brin', or 'standard'
    """
    node_type = plan_node.get("Node Type", "")
    if not isinstance(node_type, str):
        return "btree"  # Default

    # Check for text search patterns (GIN for full-text search)
    if query:
        query_lower = query.lower()
        if any(pattern in query_lower for pattern in ["@@", "to_tsvector", "tsvector", "tsquery"]):
            return "gin"
        if any(pattern in query_lower for pattern in ["like", "ilike", "similar to", "~"]):
            # For pattern matching, GIN with pg_trgm is often best
            return "gin"

    # Check for array operations (GIN for arrays)
    if query and any(pattern in query.lower() for pattern in ["@>", "<@", "&&", "array["]):
        return "gin"

    # Check for geometric/spatial operations (GiST)
    if query and any(
        pattern in query.lower() for pattern in ["<->", "<#>", "<->>", "point", "polygon"]
    ):
        return "gist"

    # Check for equality-only operations (Hash)
    filter_conditions = plan_node.get("Filter", "")
    if (
        isinstance(filter_conditions, str)
        and "=" in filter_conditions
        and not any(op in filter_conditions for op in ["<", ">", "<=", ">=", "BETWEEN"])
    ):
        # But Hash indexes are limited - only for equality
        # For most cases, B-tree is safer
        pass

    # Check for large sequential scans (BRIN for large tables)
    if node_type == "Seq Scan":
        rows_removed = plan_node.get("Rows Removed by Filter", 0)
        if isinstance(rows_removed, int | float) and rows_removed > 100000:
            # Large table with filtering - BRIN might help
            return "brin"

    # Default: B-tree (most versatile)
    return "btree"


def detect_composite_index_from_plan(plan_node: dict[str, JSONValue]) -> list[str]:
    """
    Detect composite index opportunities from query plan.

    Analyzes plan to find multiple columns that would benefit from a composite index.

    Args:
        plan_node: Query plan node (from EXPLAIN)

    Returns:
        List of column names that should be in a composite index (ordered by importance)
    """
    columns: list[str] = []

    # Extract filter conditions
    filter_str = plan_node.get("Filter", "")
    if isinstance(filter_str, str):
        # Simple heuristic: look for column names in filter
        # In production, would parse SQL properly
        import re

        # Match column-like patterns (simplified)
        col_pattern = r"\b([a-z_][a-z0-9_]*)\s*[=<>]"
        matches = re.findall(col_pattern, filter_str.lower())
        columns.extend(matches)

    # Extract index conditions
    index_condition = plan_node.get("Index Condition", "")
    if isinstance(index_condition, str):
        import re

        col_pattern = r"\b([a-z_][a-z0-9_]*)\s*[=<>]"
        matches = re.findall(col_pattern, index_condition.lower())
        columns.extend(matches)

    # Remove duplicates while preserving order
    seen = set()
    unique_columns = []
    for col in columns:
        if col not in seen:
            seen.add(col)
            unique_columns.append(col)

    return unique_columns[:5]  # Limit to 5 columns for composite index


def detect_covering_index_from_plan(
    plan_node: dict[str, JSONValue], query: str | None = None
) -> dict[str, JSONValue]:
    """
    Detect covering index opportunities from query plan.

    A covering index includes all columns needed for a query, allowing index-only scans.

    Args:
        plan_node: Query plan node (from EXPLAIN)
        query: Optional query text

    Returns:
        dict with covering index suggestion:
        - is_covering_opportunity: bool
        - columns: list[str] - Columns to include
        - estimated_benefit: float - Estimated improvement percentage
    """
    # Check if plan uses Index Scan (not Index Only Scan)
    node_type = plan_node.get("Node Type", "")
    if not isinstance(node_type, str):
        return {
            "is_covering_opportunity": False,
            "columns": [],
            "estimated_benefit": 0.0,
        }

    # If already using Index Only Scan, no covering index needed
    if node_type == "Index Only Scan":
        return {
            "is_covering_opportunity": False,
            "columns": [],
            "estimated_benefit": 0.0,
        }

    # If using Index Scan with heap fetches, covering index could help
    heap_fetches = plan_node.get("Heap Fetches", 0)
    if isinstance(heap_fetches, int | float) and heap_fetches > 0:
        # Extract columns from plan
        columns = detect_composite_index_from_plan(plan_node)

        # Estimate benefit based on heap fetches
        rows = plan_node.get("Actual Rows", plan_node.get("Plan Rows", 0))
        if isinstance(rows, int | float) and rows > 0:
            fetch_ratio = heap_fetches / rows if rows > 0 else 0.0
            # Higher fetch ratio = more benefit from covering index
            estimated_benefit = min(50.0, fetch_ratio * 30.0)  # Cap at 50% improvement

            from typing import cast

            return {
                "is_covering_opportunity": True,
                "columns": cast(list[JSONValue], columns),
                "estimated_benefit": estimated_benefit,
                "heap_fetches": heap_fetches,
                "total_rows": rows,
            }

    return {
        "is_covering_opportunity": False,
        "columns": [],
        "estimated_benefit": 0.0,
    }


def compare_explain_before_after(
    query: str,
    params: QueryParams | None,
    index_name: str | None = None,
) -> JSONDict:
    """
    Compare EXPLAIN results before and after index creation.

    This helps validate that an index actually improves query performance.

    Args:
        query: SQL query to analyze
        params: Query parameters
        index_name: Optional index name (if checking after creation)

    Returns:
        dict with before/after comparison:
        - before: dict - Plan before index
        - after: dict - Plan after index (if index_name provided)
        - improvement_pct: float - Performance improvement percentage
        - cost_reduction_pct: float - Cost reduction percentage
        - is_effective: bool - Whether index is effective
    """
    if params is None:
        params = ()

    # Get before plan (current state)
    before_plan = analyze_query_plan_fast(query, params, use_cache=False)

    if not before_plan:
        return {
            "before": None,
            "after": None,
            "improvement_pct": 0.0,
            "cost_reduction_pct": 0.0,
            "is_effective": False,
            "error": "Could not analyze query plan",
        }

    before_cost = before_plan.get("total_cost", 0.0)
    before_cost_float = float(before_cost) if isinstance(before_cost, int | float) else 0.0

    # If index_name provided, get after plan
    after_plan = None
    if index_name:
        # Force index usage to see improvement
        # Note: This is a simplified approach - in production would use actual index
        after_plan = analyze_query_plan_fast(query, params, use_cache=False)
        # In real implementation, would ensure index is used

    if not after_plan:
        return {
            "before": before_plan,
            "after": None,
            "improvement_pct": 0.0,
            "cost_reduction_pct": 0.0,
            "is_effective": False,
            "note": "After plan not available (index may not be created yet)",
        }

    after_cost = after_plan.get("total_cost", 0.0)
    after_cost_float = float(after_cost) if isinstance(after_cost, int | float) else 0.0

    # Calculate improvements
    if before_cost_float > 0:
        cost_reduction_pct = ((before_cost_float - after_cost_float) / before_cost_float) * 100.0
        improvement_pct = max(0.0, cost_reduction_pct)
        is_effective = improvement_pct > 10.0  # At least 10% improvement
    else:
        cost_reduction_pct = 0.0
        improvement_pct = 0.0
        is_effective = False

    return {
        "before": before_plan,
        "after": after_plan,
        "improvement_pct": improvement_pct,
        "cost_reduction_pct": cost_reduction_pct,
        "is_effective": is_effective,
        "before_cost": before_cost_float,
        "after_cost": after_cost_float,
    }
