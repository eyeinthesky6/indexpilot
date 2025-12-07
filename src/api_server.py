"""FastAPI server for IndexPilot Dashboard API

Provides REST API endpoints for the Next.js dashboard UI.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_connection
from src.query_analyzer import get_explain_stats
from src.index_health import find_bloated_indexes, monitor_index_health
from src.stats import get_query_stats
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

app = FastAPI(title="IndexPilot API", version="1.0.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
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
        performance_data = []
        index_impact_data = []

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
                    performance_data.append({
                        "timestamp": row[0].isoformat() if row[0] else "",
                        "queryCount": row[1] or 0,
                        "avgLatency": float(row[2] or 0),
                        "p95Latency": float(row[3] or 0),
                        "indexHits": row[4] or 0,
                        "indexMisses": row[5] or 0,
                    })

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
                    improvement_pct = row[3]
                    if improvement_pct:
                        try:
                            improvement = float(improvement_pct)
                        except (ValueError, TypeError):
                            improvement = 0.0
                    else:
                        improvement = 0.0

                    queries = row[4]
                    query_count = int(queries) if queries else 0

                    cost_before = row[5]
                    cost_after = row[6]
                    before_cost = float(cost_before) if cost_before else 0.0
                    after_cost = float(cost_after) if cost_after else 0.0

                    index_impact_data.append({
                        "indexName": row[0] or "",
                        "tableName": row[1] or "",
                        "fieldName": row[2] or "",
                        "improvement": improvement,
                        "queryCount": query_count,
                        "beforeCost": before_cost,
                        "afterCost": after_cost,
                    })

            finally:
                cursor.close()

        return {
            "performance": performance_data,
            "indexImpact": index_impact_data,
            "explainStats": explain_stats,
        }

    except Exception as e:
        logger.error(f"Failed to get performance data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def get_health_data() -> JSONDict:
    """
    Get index health monitoring data.
    
    Returns:
        - indexes: List of index health information
        - summary: Health summary statistics
    """
    try:
        # Get index health data
        health_data = monitor_index_health()
        bloated_indexes = find_bloated_indexes(bloat_threshold_percent=20.0, min_size_mb=1.0)

        # Build index health list
        indexes = []
        healthy_count = 0
        warning_count = 0
        critical_count = 0
        total_size_mb = 0.0
        total_bloat = 0.0

        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get all indexes with their stats
                cursor.execute(
                    """
                    SELECT
                        i.indexname,
                        i.tablename,
                        pg_size_pretty(pg_relation_size(i.indexname::regclass)) as size_pretty,
                        pg_relation_size(i.indexname::regclass) / 1024.0 / 1024.0 as size_mb,
                        COALESCE(s.idx_scan, 0) as usage_count,
                        COALESCE(s.idx_tup_read, 0) as tuples_read,
                        COALESCE(s.idx_tup_fetch, 0) as tuples_fetched
                    FROM pg_indexes i
                    LEFT JOIN pg_stat_user_indexes s ON s.indexrelname = i.indexname
                    WHERE i.schemaname = 'public'
                    ORDER BY pg_relation_size(i.indexname::regclass) DESC
                """
                )

                rows = cursor.fetchall()
                # Build bloated dict - bloated_indexes contains dicts with "indexname" key
                bloated_dict = {}
                for idx in bloated_indexes:
                    idx_name = idx.get("indexname") or idx.get("index_name", "")
                    if idx_name:
                        bloated_dict[idx_name] = idx

                for row in rows:
                    index_name = row[0]
                    table_name = row[1]
                    size_mb = float(row[3] or 0)
                    usage_count = row[4] or 0

                    # Get bloat percentage from bloated dict or calculate from health_data
                    bloat_info = bloated_dict.get(index_name, {})
                    # Try different possible keys for bloat percentage
                    bloat_percent = float(
                        bloat_info.get("bloat_percent")
                        or bloat_info.get("bloat_percentage")
                        or bloat_info.get("estimated_bloat_percent", 0.0)
                    )

                    # Determine health status
                    if bloat_percent >= 50.0:
                        health_status = "critical"
                        critical_count += 1
                    elif bloat_percent >= 20.0:
                        health_status = "warning"
                        warning_count += 1
                    else:
                        health_status = "healthy"
                        healthy_count += 1

                    total_size_mb += size_mb
                    total_bloat += bloat_percent

                    indexes.append({
                        "indexName": index_name,
                        "tableName": table_name,
                        "bloatPercent": bloat_percent,
                        "sizeMB": size_mb,
                        "usageCount": usage_count,
                        "lastUsed": "",  # Would need to track this separately
                        "healthStatus": health_status,
                    })

            finally:
                cursor.close()

        avg_bloat = total_bloat / len(indexes) if indexes else 0.0

        summary = {
            "totalIndexes": len(indexes),
            "healthyIndexes": healthy_count,
            "warningIndexes": warning_count,
            "criticalIndexes": critical_count,
            "totalSizeMB": total_size_mb,
            "avgBloatPercent": avg_bloat,
        }

        return {
            "indexes": indexes,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Failed to get health data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

