"""FastAPI server for IndexPilot Dashboard API

Provides REST API endpoints for the Next.js dashboard UI.
"""

import logging
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_connection
from src.index_health import monitor_index_health
from src.query_analyzer import get_explain_stats
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

app = FastAPI(
    title="IndexPilot API",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> JSONDict:
    """Health check endpoint"""
    return {"status": "ok", "service": "IndexPilot API"}


@app.get("/api/performance")
async def get_performance_data() -> JSONDict:
    """
    Get performance metrics for the dashboard.

    Returns:
        - performance: List of performance data points over time
        - indexImpact: List of index impact analysis
        - explainStats: EXPLAIN integration statistics
    """
    try:
        # Get EXPLAIN statistics
        explain_stats = get_explain_stats()

        # Get query performance data (last 24 hours, hourly buckets)
        performance_data: list[JSONDict] = []
        index_impact_data: list[JSONDict] = []

        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get hourly query performance metrics
                # Note: query_stats doesn't track index usage directly, so we estimate based on query patterns
                cursor.execute(
                    """
                    SELECT
                        DATE_TRUNC('hour', created_at) as hour,
                        COUNT(*) as query_count,
                        AVG(duration_ms) as avg_latency,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_latency,
                        0 as index_hits,  -- Would need EXPLAIN analysis to determine actual index usage
                        0 as index_misses  -- Would need EXPLAIN analysis to determine actual index usage
                    FROM query_stats
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY DATE_TRUNC('hour', created_at)
                    ORDER BY hour DESC
                    LIMIT 24
                """
                )

                rows = cursor.fetchall()
                for row in rows:
                    # Type narrow row tuple elements
                    timestamp_val = row[0] if len(row) > 0 else None
                    query_count_val = row[1] if len(row) > 1 else 0
                    avg_latency_val = row[2] if len(row) > 2 else 0
                    p95_latency_val = row[3] if len(row) > 3 else 0
                    index_hits_val = row[4] if len(row) > 4 else 0
                    index_misses_val = row[5] if len(row) > 5 else 0

                    timestamp_str = ""
                    if timestamp_val is not None and hasattr(timestamp_val, "isoformat"):
                        timestamp_str = timestamp_val.isoformat()

                    query_count = int(query_count_val) if isinstance(query_count_val, (int, float)) else 0
                    avg_latency = float(avg_latency_val) if isinstance(avg_latency_val, (int, float)) else 0.0
                    p95_latency = float(p95_latency_val) if isinstance(p95_latency_val, (int, float)) else 0.0
                    index_hits = int(index_hits_val) if isinstance(index_hits_val, (int, float)) else 0
                    index_misses = int(index_misses_val) if isinstance(index_misses_val, (int, float)) else 0

                    performance_data.append(
                        {
                            "timestamp": timestamp_str,
                            "queryCount": query_count,
                            "avgLatency": avg_latency,
                            "p95Latency": p95_latency,
                            "indexHits": index_hits,
                            "indexMisses": index_misses,
                        }
                    )

                # Get index impact data from mutation_log (extract from details_json)
                cursor.execute(
                    """
                    SELECT
                        details_json->>'index_name' as index_name,
                        table_name,
                        field_name,
                        details_json->>'improvement_pct' as improvement_pct,
                        details_json->>'queries_over_horizon' as queries_analyzed,
                        details_json->>'estimated_query_cost_without_index' as cost_before,
                        details_json->>'estimated_query_cost_with_index' as cost_after
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                      AND created_at >= NOW() - INTERVAL '7 days'
                      AND details_json->>'improvement_pct' IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 50
                """
                )

                rows = cursor.fetchall()
                for row in rows:
                    # Type narrow row tuple elements
                    index_name_val = row[0] if len(row) > 0 else None
                    table_name_val = row[1] if len(row) > 1 else None
                    field_name_val = row[2] if len(row) > 2 else None
                    improvement_pct = row[3] if len(row) > 3 else None
                    queries = row[4] if len(row) > 4 else None
                    cost_before = row[5] if len(row) > 5 else None
                    cost_after = row[6] if len(row) > 6 else None

                    if improvement_pct:
                        if isinstance(improvement_pct, (int, float, str)):
                            try:
                                improvement = float(improvement_pct)
                            except (ValueError, TypeError):
                                improvement = 0.0
                        else:
                            improvement = 0.0
                    else:
                        improvement = 0.0

                    if isinstance(queries, (int, float, str)):
                        try:
                            query_count = int(queries)
                        except (ValueError, TypeError):
                            query_count = 0
                    else:
                        query_count = 0

                    if isinstance(cost_before, (int, float, str)):
                        try:
                            before_cost = float(cost_before)
                        except (ValueError, TypeError):
                            before_cost = 0.0
                    else:
                        before_cost = 0.0

                    if isinstance(cost_after, (int, float, str)):
                        try:
                            after_cost = float(cost_after)
                        except (ValueError, TypeError):
                            after_cost = 0.0
                    else:
                        after_cost = 0.0

                    index_name = str(index_name_val) if index_name_val is not None else ""
                    table_name = str(table_name_val) if table_name_val is not None else ""
                    field_name = str(field_name_val) if field_name_val is not None else ""

                    index_impact_data.append(
                        {
                            "indexName": index_name,
                            "tableName": table_name,
                            "fieldName": field_name,
                            "improvement": improvement,
                            "queryCount": query_count,
                            "beforeCost": before_cost,
                            "afterCost": after_cost,
                        }
                    )

            finally:
                cursor.close()

        # Convert lists to list[JSONValue] for JSONDict compatibility
        performance_data_list: list[JSONValue] = [cast(JSONValue, item) for item in performance_data]
        index_impact_data_list: list[JSONValue] = [cast(JSONValue, item) for item in index_impact_data]

        return {
            "performance": performance_data_list,
            "indexImpact": index_impact_data_list,
            "explainStats": explain_stats,
        }

    except Exception as e:
        logger.error(f"Failed to get performance data: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/health")
async def get_health_data() -> JSONDict:
    """
    Get index health monitoring data.

    Returns:
        - indexes: List of index health information
        - summary: Health summary statistics
    """
    try:
        # Get index health data using existing monitor_index_health function
        health_data = monitor_index_health(bloat_threshold_percent=20.0, min_size_mb=1.0)

        if health_data.get("status") == "disabled":
            return {
                "indexes": [],
                "summary": {
                    "totalIndexes": 0,
                    "healthyIndexes": 0,
                    "warningIndexes": 0,
                    "criticalIndexes": 0,
                    "totalSizeMB": 0.0,
                    "avgBloatPercent": 0.0,
                },
            }

        # Transform health_data indexes to dashboard format
        indexes: list[JSONDict] = []
        healthy_count = 0
        warning_count = 0
        critical_count = 0
        total_size_mb = 0.0
        total_bloat = 0.0

        health_indexes_val: JSONValue = health_data.get("indexes", [])
        if not isinstance(health_indexes_val, list):
            health_indexes: list[JSONDict] = []
        else:
            # Filter and type narrow to JSONDict
            health_indexes = []
            for idx in health_indexes_val:
                if isinstance(idx, dict):
                    health_indexes.append(idx)  # isinstance already narrows to dict, which is JSONDict

        for idx in health_indexes:
            index_name_val = idx.get("indexname", "")
            table_name_val = idx.get("tablename", "")
            size_mb_val = idx.get("size_mb", 0.0)
            usage_count_val = idx.get("index_scans", 0)
            is_bloated_val = idx.get("is_bloated", False)
            scan_efficiency_val = idx.get("scan_efficiency", 0.0)

            index_name = str(index_name_val) if isinstance(index_name_val, str) else ""
            table_name = str(table_name_val) if isinstance(table_name_val, str) else ""
            size_mb = float(size_mb_val) if isinstance(size_mb_val, (int, float)) else 0.0
            usage_count = int(usage_count_val) if isinstance(usage_count_val, (int, float)) else 0
            is_bloated = bool(is_bloated_val) if isinstance(is_bloated_val, bool) else False
            scan_efficiency = float(scan_efficiency_val) if isinstance(scan_efficiency_val, (int, float)) else 0.0

            # Estimate bloat percentage (simplified - based on scan efficiency)
            # Lower efficiency = higher bloat estimate
            if is_bloated:
                bloat_percent = (
                    max(20.0, (1.0 - scan_efficiency) * 100.0) if scan_efficiency > 0 else 30.0
                )
            else:
                bloat_percent = (1.0 - scan_efficiency) * 50.0 if scan_efficiency > 0 else 0.0

            # Determine health status
            health_status_val = idx.get("health_status", "healthy")
            health_status = str(health_status_val) if isinstance(health_status_val, str) else "healthy"

            if health_status == "bloated":
                if bloat_percent >= 50.0:
                    health_status = "critical"
                    critical_count += 1
                else:
                    health_status = "warning"
                    warning_count += 1
            elif health_status == "underutilized":
                health_status = "warning"
                warning_count += 1
            else:
                health_status = "healthy"
                healthy_count += 1

            total_size_mb += size_mb
            total_bloat += bloat_percent

            created_at_val = idx.get("created_at", "")
            last_used = str(created_at_val) if isinstance(created_at_val, str) else ""

            indexes.append(
                {
                    "indexName": index_name,
                    "tableName": table_name,
                    "bloatPercent": round(bloat_percent, 1),
                    "sizeMB": round(size_mb, 2),
                    "usageCount": usage_count,
                    "lastUsed": last_used,
                    "healthStatus": health_status,
                }
            )

        avg_bloat = total_bloat / float(len(indexes)) if len(indexes) > 0 else 0.0

        # Convert summary values to JSONValue-compatible types
        summary: JSONDict = {
            "totalIndexes": len(indexes),
            "healthyIndexes": healthy_count,
            "warningIndexes": warning_count,
            "criticalIndexes": critical_count,
            "totalSizeMB": round(total_size_mb, 2),
            "avgBloatPercent": round(avg_bloat, 1),
        }

        # Convert indexes to list[JSONValue] for JSONDict compatibility
        indexes_list: list[JSONValue] = [cast(JSONValue, item) for item in indexes]

        return {
            "indexes": indexes_list,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Failed to get health data: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/explain-stats")
async def get_explain_stats_endpoint() -> JSONDict:
    """
    Get EXPLAIN integration statistics.

    Returns:
        EXPLAIN success rate and usage metrics
    """
    try:
        stats = get_explain_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get EXPLAIN stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
