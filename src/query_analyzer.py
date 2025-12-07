"""Query plan analysis using EXPLAIN"""

import json
import time

from psycopg2.extras import RealDictCursor

from src.db import get_connection


def analyze_query_plan(query, params=None):
    """
    Analyze query execution plan using EXPLAIN.

    Returns:
        dict with plan analysis including cost, time, node type, and recommendations
    """
    if params is None:
        params = []

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get query plan in JSON format
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

            return analysis
        except Exception:
            # If EXPLAIN fails, return None (query might be invalid)
            return None
        finally:
            cursor.close()


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
