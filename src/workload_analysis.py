"""Workload analysis - read/write ratio tracking"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_workload_analysis_enabled() -> bool:
    """Check if workload analysis is enabled"""
    return _config_loader.get_bool("features.workload_analysis.enabled", True)


def get_workload_config() -> dict[str, Any]:
    """Get workload analysis configuration"""
    return {
        "enabled": is_workload_analysis_enabled(),
        "time_window_hours": _config_loader.get_int("features.workload_analysis.time_window_hours", 24),
        "read_heavy_threshold": _config_loader.get_float(
            "features.workload_analysis.read_heavy_threshold", 0.7
        ),
        "write_heavy_threshold": _config_loader.get_float(
            "features.workload_analysis.write_heavy_threshold", 0.3
        ),
    }


def analyze_workload(
    table_name: str | None = None,
    time_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Analyze workload read/write ratio for a table or all tables.

    Args:
        table_name: Table name (None = analyze all tables)
        time_window_hours: Time window for analysis

    Returns:
        dict with workload analysis results
    """
    if not is_workload_analysis_enabled():
        return {"skipped": True, "reason": "workload_analysis_disabled"}

    result: JSONDict = {
        "timestamp": None,
        "time_window_hours": time_window_hours,
        "tables": [],
        "overall": {},
    }

    try:
        from datetime import datetime

        result["timestamp"] = datetime.now().isoformat()

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get read/write statistics from query_stats
                if table_name:
                    query = """
                        SELECT
                            table_name,
                            query_type,
                            COUNT(*) as query_count,
                            SUM(duration_ms) as total_duration_ms,
                            AVG(duration_ms) as avg_duration_ms
                        FROM query_stats
                        WHERE table_name = %s
                          AND created_at >= NOW() - INTERVAL '1 hour' * %s
                        GROUP BY table_name, query_type
                        ORDER BY table_name, query_type
                    """
                    cursor.execute(query, (table_name, time_window_hours))
                else:
                    query = """
                        SELECT
                            table_name,
                            query_type,
                            COUNT(*) as query_count,
                            SUM(duration_ms) as total_duration_ms,
                            AVG(duration_ms) as avg_duration_ms
                        FROM query_stats
                        WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
                        GROUP BY table_name, query_type
                        ORDER BY table_name, query_type
                    """
                    cursor.execute(query, (time_window_hours,))

                stats = cursor.fetchall()

                # Group by table
                table_stats: dict[str, dict[str, Any]] = {}
                for stat in stats:
                    table = stat["table_name"]
                    query_type = stat["query_type"]
                    count = int(stat["query_count"]) if stat["query_count"] else 0

                    if table not in table_stats:
                        table_stats[table] = {
                            "table_name": table,
                            "read_queries": 0,
                            "write_queries": 0,
                            "total_queries": 0,
                            "read_duration_ms": 0.0,
                            "write_duration_ms": 0.0,
                            "total_duration_ms": 0.0,
                        }

                    if query_type in ["SELECT", "READ"]:
                        table_stats[table]["read_queries"] += count
                        table_stats[table]["read_duration_ms"] += float(
                            stat["total_duration_ms"] or 0
                        )
                    elif query_type in ["INSERT", "UPDATE", "DELETE", "WRITE"]:
                        table_stats[table]["write_queries"] += count
                        table_stats[table]["write_duration_ms"] += float(
                            stat["total_duration_ms"] or 0
                        )

                    table_stats[table]["total_queries"] += count
                    table_stats[table]["total_duration_ms"] += float(
                        stat["total_duration_ms"] or 0
                    )

                # Calculate ratios and workload type
                config = get_workload_config()
                read_heavy_threshold = config["read_heavy_threshold"]
                write_heavy_threshold = config["write_heavy_threshold"]

                overall_read = 0
                overall_write = 0
                overall_total = 0

                for table, stats_data in table_stats.items():
                    total = stats_data["total_queries"]
                    if total > 0:
                        read_ratio = stats_data["read_queries"] / total
                        write_ratio = stats_data["write_queries"] / total

                        if read_ratio >= read_heavy_threshold:
                            workload_type = "read_heavy"
                        elif write_ratio >= write_heavy_threshold:
                            workload_type = "write_heavy"
                        else:
                            workload_type = "balanced"

                        stats_data["read_ratio"] = read_ratio
                        stats_data["write_ratio"] = write_ratio
                        stats_data["workload_type"] = workload_type

                        overall_read += stats_data["read_queries"]
                        overall_write += stats_data["write_queries"]
                        overall_total += total

                    result["tables"].append(stats_data)

                # Calculate overall workload
                if overall_total > 0:
                    overall_read_ratio = overall_read / overall_total
                    overall_write_ratio = overall_write / overall_total

                    if overall_read_ratio >= read_heavy_threshold:
                        overall_workload = "read_heavy"
                    elif overall_write_ratio >= write_heavy_threshold:
                        overall_workload = "write_heavy"
                    else:
                        overall_workload = "balanced"

                    result["overall"] = {
                        "read_queries": overall_read,
                        "write_queries": overall_write,
                        "total_queries": overall_total,
                        "read_ratio": overall_read_ratio,
                        "write_ratio": overall_write_ratio,
                        "workload_type": overall_workload,
                    }

                logger.info(
                    f"Workload analysis: {len(result['tables'])} tables analyzed, "
                    f"overall workload: {result['overall'].get('workload_type', 'unknown')}"
                )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to analyze workload: {e}")
        result["error"] = str(e)

    return result


def get_workload_recommendation(
    table_name: str, workload_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Get index recommendation based on workload type.

    Args:
        table_name: Table name
        workload_data: Workload analysis data (if None, will analyze)

    Returns:
        dict with workload-based recommendation
    """
    if workload_data is None:
        workload_data = analyze_workload(table_name=table_name)

    if workload_data.get("skipped"):
        return {"recommendation": "unknown", "reason": workload_data.get("reason")}

    # Find table in workload data
    table_info = None
    for table in workload_data.get("tables", []):
        if table["table_name"] == table_name:
            table_info = table
            break

    if not table_info:
        return {"recommendation": "unknown", "reason": "no_workload_data"}

    workload_type = table_info.get("workload_type", "balanced")
    read_ratio = table_info.get("read_ratio", 0.5)

    if workload_type == "read_heavy":
        return {
            "recommendation": "aggressive",
            "workload_type": workload_type,
            "read_ratio": read_ratio,
            "reason": f"Read-heavy workload ({read_ratio:.1%} reads) - more aggressive indexing recommended",
            "suggestion": "Create indexes more aggressively, prioritize read performance",
        }
    elif workload_type == "write_heavy":
        return {
            "recommendation": "conservative",
            "workload_type": workload_type,
            "read_ratio": read_ratio,
            "reason": f"Write-heavy workload ({1-read_ratio:.1%} writes) - conservative indexing recommended",
            "suggestion": "Be conservative with index creation, prioritize write performance",
        }
    else:
        return {
            "recommendation": "balanced",
            "workload_type": workload_type,
            "read_ratio": read_ratio,
            "reason": f"Balanced workload - standard indexing approach",
            "suggestion": "Use standard cost-benefit thresholds",
        }

