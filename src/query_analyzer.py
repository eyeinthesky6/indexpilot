"""Query plan analysis using EXPLAIN"""

# INTEGRATION NOTE: QPG (Query Plan Guidance) Enhancement
# Current: Basic query plan analysis with EXPLAIN
# Enhancement: Add QPG concepts (arXiv:2312.17510) for diverse plan generation
# Integration Point: Enhance analyze_query_plan() with QPG-inspired bottleneck identification
# See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict

from psycopg2.extras import RealDictCursor

from src.db import get_connection

logger = logging.getLogger(__name__)

# EXPLAIN result cache (LRU cache)
_explain_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_cache_lock = threading.Lock()
_cache_max_size = 100  # Maximum cached plans
_cache_ttl = 3600  # Cache TTL in seconds (1 hour)


def _get_query_signature(query: str, params=None) -> str:
    """Generate a signature for query caching"""
    if params is None:
        params = []
    # Normalize query (remove extra whitespace)
    normalized_query = " ".join(query.split())
    # Create signature from query + params
    signature_str = f"{normalized_query}:{str(params)}"
    return hashlib.md5(signature_str.encode()).hexdigest()


def analyze_query_plan_fast(query, params=None, use_cache=True):
    """
    Analyze query execution plan using EXPLAIN (without ANALYZE).

    Faster than analyze_query_plan() because it doesn't execute the query.
    Use this for initial cost estimation, fall back to analyze_query_plan() if needed.

    Args:
        query: SQL query string
        params: Query parameters
        use_cache: Whether to use cached results

    Returns:
        dict with plan analysis including cost, node type, and recommendations
    """
    if params is None:
        params = []

    # Check cache first
    if use_cache:
        cache_key = _get_query_signature(query, params)
        with _cache_lock:
            if cache_key in _explain_cache:
                cached_result, cached_time = _explain_cache[cache_key]
                # Check if cache is still valid
                if time.time() - cached_time < _cache_ttl:
                    # Move to end (LRU)
                    _explain_cache.move_to_end(cache_key)
                    logger.debug(f"Using cached EXPLAIN plan for query signature: {cache_key[:8]}")
                    return cached_result
                else:
                    # Expired, remove
                    del _explain_cache[cache_key]

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Use EXPLAIN without ANALYZE (faster, doesn't execute query)
            explain_query = f"EXPLAIN (FORMAT JSON) {query}"
            cursor.execute(explain_query, params)
            result = cursor.fetchone()

            if not result:
                return None

            # RealDictCursor returns a dict, extract EXPLAIN output from first column value
            plan_data = None
            for col_value in result.values():
                if col_value is not None:
                    plan_data = col_value
                    break

            if not plan_data:
                return None

            plan = json.loads(plan_data) if isinstance(plan_data, str) else plan_data

            # Extract plan information
            if not plan or len(plan) == 0 or "Plan" not in plan[0]:
                return None
            plan_node = plan[0]["Plan"]

            analysis = {
                "total_cost": plan_node.get("Total Cost", 0),
                "actual_time_ms": 0,  # Not available without ANALYZE
                "node_type": plan_node.get("Node Type", "Unknown"),
                "planning_time_ms": 0,  # Not available without ANALYZE
                "has_seq_scan": _has_sequential_scan(plan_node),
                "has_index_scan": _has_index_scan(plan_node),
                "needs_index": False,
                "recommendations": [],
                "from_cache": False,
            }

            # Determine if index would help
            if analysis["has_seq_scan"] and analysis["total_cost"] > 100:
                analysis["needs_index"] = True
                analysis["recommendations"].append(
                    f"Sequential scan detected (cost: {analysis['total_cost']:.2f}). "
                    "Consider creating an index on filtered columns."
                )

            # Check for nested loops (can be slow)
            if plan_node.get("Node Type") == "Nested Loop":
                analysis["recommendations"].append(
                    "Nested loop join detected. Consider indexes on join columns."
                )

            # Cache the result
            if use_cache:
                cache_key = _get_query_signature(query, params)
                with _cache_lock:
                    # Remove oldest if cache is full
                    if len(_explain_cache) >= _cache_max_size:
                        _explain_cache.popitem(last=False)
                    _explain_cache[cache_key] = (analysis, time.time())

            return analysis
        except Exception as e:
            logger.debug(f"EXPLAIN (fast) failed: {e}")
            return None
        finally:
            cursor.close()


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
        params = []

    # Check cache first
    if use_cache:
        cache_key = _get_query_signature(query, params)
        with _cache_lock:
            if cache_key in _explain_cache:
                cached_result, cached_time = _explain_cache[cache_key]
                # Check if cache is still valid
                if time.time() - cached_time < _cache_ttl:
                    # Move to end (LRU)
                    _explain_cache.move_to_end(cache_key)
                    logger.debug(
                        f"Using cached EXPLAIN ANALYZE plan for query signature: {cache_key[:8]}"
                    )
                    return cached_result
                else:
                    # Expired, remove
                    del _explain_cache[cache_key]

    # Retry logic for transient failures
    last_exception = None
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    # Get query plan in JSON format with ANALYZE
                    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    cursor.execute(explain_query, params)
                    result = cursor.fetchone()

                    if not result:
                        return None

                    # RealDictCursor returns a dict, extract EXPLAIN output from first column value
                    plan_data = None
                    for col_value in result.values():
                        if col_value is not None:
                            plan_data = col_value
                            break

                    if not plan_data:
                        return None

                    plan = json.loads(plan_data) if isinstance(plan_data, str) else plan_data

                    # Extract plan information
                    if not plan or len(plan) == 0 or "Plan" not in plan[0]:
                        return None
                    plan_node = plan[0]["Plan"]

                    analysis = {
                        "total_cost": plan_node.get("Total Cost", 0),
                        "actual_time_ms": plan[0].get("Execution Time", 0),
                        "node_type": plan_node.get("Node Type", "Unknown"),
                        "planning_time_ms": plan[0].get("Planning Time", 0),
                        "has_seq_scan": _has_sequential_scan(plan_node),
                        "has_index_scan": _has_index_scan(plan_node),
                        "needs_index": False,
                        "recommendations": [],
                        "from_cache": False,
                    }

                    # Determine if index would help
                    if analysis["has_seq_scan"] and analysis["total_cost"] > 100:
                        analysis["needs_index"] = True
                        analysis["recommendations"].append(
                            f"Sequential scan detected (cost: {analysis['total_cost']:.2f}). "
                            "Consider creating an index on filtered columns."
                        )

                    # Check for nested loops (can be slow)
                    if plan_node.get("Node Type") == "Nested Loop":
                        analysis["recommendations"].append(
                            "Nested loop join detected. Consider indexes on join columns."
                        )

                    # Cache the result
                    if use_cache:
                        cache_key = _get_query_signature(query, params)
                        with _cache_lock:
                            # Remove oldest if cache is full
                            if len(_explain_cache) >= _cache_max_size:
                                _explain_cache.popitem(last=False)
                            _explain_cache[cache_key] = (analysis, time.time())

                    return analysis
                finally:
                    cursor.close()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff: 0.1s, 0.2s, 0.4s
                wait_time = 0.1 * (2**attempt)
                logger.debug(
                    f"EXPLAIN ANALYZE attempt {attempt + 1}/{max_retries} failed: {e}, "
                    f"retrying in {wait_time:.2f}s"
                )
                time.sleep(wait_time)
            else:
                logger.warning(f"EXPLAIN ANALYZE failed after {max_retries} attempts: {e}")
                return None

    # If all retries failed
    return None


def _has_sequential_scan(plan_node):
    """Recursively check if plan contains sequential scan"""
    if plan_node.get("Node Type") == "Seq Scan":
        return True

    # Check child plans
    if "Plans" in plan_node:
        for child in plan_node["Plans"]:
            if _has_sequential_scan(child):
                return True

    return False


def _has_index_scan(plan_node):
    """Recursively check if plan uses index scan"""
    node_type = plan_node.get("Node Type", "")
    if "Index" in node_type or node_type == "Bitmap Heap Scan":
        return True

    # Check child plans
    if "Plans" in plan_node:
        for child in plan_node["Plans"]:
            if _has_index_scan(child):
                return True

    return False


def measure_query_performance(query, params=None, num_runs=10):
    """
    Measure actual query performance by running it multiple times.

    Returns:
        dict with median, average, min, max times in milliseconds
    """
    if params is None:
        params = []

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
