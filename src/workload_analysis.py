"""Workload analysis - advanced characterization with query template clustering and access pattern mining

Based on VLDB 2021: "Workload Characterization for Index Tuning"
- Query template clustering for similar query identification
- Access pattern mining for common usage patterns
- Enhanced workload classification beyond read/write ratios
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

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
        "time_window_hours": _config_loader.get_int(
            "features.workload_analysis.time_window_hours", 24
        ),
        "read_heavy_threshold": _config_loader.get_float(
            "features.workload_analysis.read_heavy_threshold", 0.7
        ),
        "write_heavy_threshold": _config_loader.get_float(
            "features.workload_analysis.write_heavy_threshold", 0.3
        ),
        # Enhanced analysis settings (VLDB 2021)
        "enhanced_analysis": _config_loader.get_bool(
            "features.workload_analysis.enhanced_analysis", True
        ),
        "query_template_clustering": _config_loader.get_bool(
            "features.workload_analysis.query_template_clustering", True
        ),
        "pattern_similarity_threshold": _config_loader.get_float(
            "features.workload_analysis.pattern_similarity_threshold", 0.8
        ),
        "min_cluster_size": _config_loader.get_int(
            "features.workload_analysis.min_cluster_size", 3
        ),
        "dominant_pattern_threshold": _config_loader.get_float(
            "features.workload_analysis.dominant_pattern_threshold", 0.05
        ),
    }


def analyze_workload(
    table_name: str | None = None,
    time_window_hours: int = 24,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """
    Analyze workload read/write ratio for a table, tenant, or all tables.

    Args:
        table_name: Table name (None = analyze all tables)
        time_window_hours: Time window for analysis
        tenant_id: Tenant ID (None = all tenants)

    Returns:
        dict with workload analysis results
    """
    if not is_workload_analysis_enabled():
        return {"skipped": True, "reason": "workload_analysis_disabled"}

    result: dict[str, Any] = {
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
                if table_name and tenant_id:
                    query = """
                        SELECT
                            table_name,
                            query_type,
                            COUNT(*) as query_count,
                            SUM(duration_ms) as total_duration_ms,
                            AVG(duration_ms) as avg_duration_ms
                        FROM query_stats
                        WHERE table_name = %s
                          AND tenant_id = %s
                          AND created_at >= NOW() - INTERVAL '1 hour' * %s
                        GROUP BY table_name, query_type
                        ORDER BY table_name, query_type
                    """
                    cursor.execute(query, (table_name, tenant_id, time_window_hours))
                elif table_name:
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
                elif tenant_id:
                    query = """
                        SELECT
                            table_name,
                            query_type,
                            COUNT(*) as query_count,
                            SUM(duration_ms) as total_duration_ms,
                            AVG(duration_ms) as avg_duration_ms
                        FROM query_stats
                        WHERE tenant_id = %s
                          AND created_at >= NOW() - INTERVAL '1 hour' * %s
                        GROUP BY table_name, query_type
                        ORDER BY table_name, query_type
                    """
                    cursor.execute(query, (tenant_id, time_window_hours))
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
                    table_stats[table]["total_duration_ms"] += float(stat["total_duration_ms"] or 0)

                # Calculate ratios and workload type
                config = get_workload_config()
                read_heavy_threshold = config["read_heavy_threshold"]
                write_heavy_threshold = config["write_heavy_threshold"]

                overall_read = 0
                overall_write = 0
                overall_total = 0

                for _table, stats_data in table_stats.items():
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

                    tables_list = result["tables"]
                    if isinstance(tables_list, list):
                        tables_list.append(stats_data)

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

                tables_count = len(result["tables"]) if isinstance(result["tables"], list) else 0
                overall = result.get("overall", {})
                workload_type = (
                    overall.get("workload_type", "unknown")
                    if isinstance(overall, dict)
                    else "unknown"
                )
                logger.info(
                    f"Workload analysis: {tables_count} tables analyzed, "
                    f"overall workload: {workload_type}"
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
            "reason": f"Write-heavy workload ({1 - read_ratio:.1%} writes) - conservative indexing recommended",
            "suggestion": "Be conservative with index creation, prioritize write performance",
        }
    else:
        return {
            "recommendation": "balanced",
            "workload_type": workload_type,
            "read_ratio": read_ratio,
            "reason": "Balanced workload - standard indexing approach",
            "suggestion": "Use standard cost-benefit thresholds",
        }


def extract_query_template(query: str) -> str:
    """
    Extract query template by normalizing literals and identifiers.

    Args:
        query: Raw SQL query string

    Returns:
        Normalized query template
    """
    if not query:
        return ""

    # Convert to uppercase for normalization
    template = query.upper()

    # Replace numeric literals with placeholders
    template = re.sub(r"\b\d+\b", "?", template)

    # Replace string literals with placeholders
    template = re.sub(r"'[^']*'", "?", template)
    template = re.sub(r'"[^"]*"', "?", template)

    # Normalize whitespace
    template = re.sub(r"\s+", " ", template.strip())

    return template


def extract_query_signature(query_record: dict[str, Any]) -> str:
    """
    Extract query signature from available metadata (since full query text isn't stored).

    Creates a signature based on query_type, table_name, and field_name patterns.

    Args:
        query_record: Query record from query_stats table

    Returns:
        Query signature string for clustering
    """
    query_type = query_record.get('query_type', 'UNKNOWN')
    table_name = query_record.get('table_name', 'UNKNOWN')
    field_name = query_record.get('field_name', '')

    # Create signature: QUERY_TYPE:TABLE_NAME[:FIELD_NAME]
    if field_name:
        signature = f"{query_type}:{table_name}:{field_name}"
    else:
        signature = f"{query_type}:{table_name}"

    return signature


def cluster_query_patterns(
    queries: list[dict[str, Any]], similarity_threshold: float | None = None
) -> list[dict[str, Any]]:
    """
    Cluster similar queries using template-based similarity.

    Args:
        queries: List of query records with 'query_text' field
        similarity_threshold: Similarity threshold for clustering (0.0-1.0)

    Returns:
        List of query clusters with statistics
    """
    if not queries:
        return []

    # Get config settings
    config = get_workload_config()
    min_cluster_size = config.get("min_cluster_size", 3)

    # Extract templates and group by template
    template_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for query in queries:
        # Extract query signature from metadata
        # Extract query template (normalize query to signature)
        query_str = query.get("query", "") if isinstance(query, dict) else str(query)
        signature = extract_query_template(query_str)
        template_groups[signature].append(query)

    # Convert to cluster format
    clusters = []
    for template, cluster_queries in template_groups.items():
        if len(cluster_queries) < min_cluster_size:  # Use config threshold
            continue

        # Calculate cluster statistics
        total_duration = sum(q.get("duration_ms", 0) for q in cluster_queries)
        avg_duration = total_duration / len(cluster_queries)
        total_executions = len(cluster_queries)

        # Identify most common table
        table_counter = Counter(q.get("table_name", "") for q in cluster_queries)
        primary_table = table_counter.most_common(1)[0][0] if table_counter else ""

        # Parse signature to get components
        parts = template.split(':')
        query_type = parts[0] if len(parts) > 0 else 'UNKNOWN'
        table_name_parsed = parts[1] if len(parts) > 1 else primary_table
        field_name = parts[2] if len(parts) > 2 else ''

        clusters.append(
            {
                "signature": template,
                "query_type": query_type,
                "table_name": table_name_parsed,
                "field_name": field_name,
                "query_count": total_executions,
                "total_duration_ms": total_duration,
                "avg_duration_ms": avg_duration,
                "importance_score": total_executions * avg_duration,
            }
        )

    # Sort by total duration (most expensive clusters first)
    clusters.sort(key=lambda x: x["total_duration_ms"], reverse=True)

    return clusters


def analyze_access_patterns(
    table_name: str,
    time_window_hours: int = 24,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """
    Analyze access patterns for a specific table using query template clustering.

    Based on VLDB 2021 approach for identifying common access patterns.

    Args:
        table_name: Table name to analyze
        time_window_hours: Time window for analysis
        tenant_id: Optional tenant ID filter

    Returns:
        Dict with access pattern analysis
    """
    result = {
        "table_name": table_name,
        "time_window_hours": time_window_hours,
        "query_clusters": [],
        "access_patterns": [],
        "dominant_patterns": [],
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get detailed query information for the table
                if tenant_id:
                    query = """
                        SELECT
                            table_name,
                            field_name,
                            query_type,
                            duration_ms,
                            created_at
                        FROM query_stats
                        WHERE table_name = %s
                          AND tenant_id = %s
                          AND created_at >= NOW() - INTERVAL '1 hour' * %s
                        ORDER BY created_at DESC
                        LIMIT 1000
                    """
                    cursor.execute(query, (table_name, tenant_id, time_window_hours))
                else:
                    query = """
                        SELECT
                            table_name,
                            field_name,
                            query_type,
                            duration_ms,
                            created_at
                        FROM query_stats
                        WHERE table_name = %s
                          AND created_at >= NOW() - INTERVAL '1 hour' * %s
                        ORDER BY created_at DESC
                        LIMIT 1000
                    """
                    cursor.execute(query, (table_name, time_window_hours))

                queries = cursor.fetchall()

                if not queries:
                    result["status"] = "no_queries_found"
                    return result

                # Cluster queries by pattern (using available metadata)
                query_clusters = cluster_query_patterns(queries)

                # Analyze access patterns from clusters
                access_patterns = analyze_cluster_patterns(query_clusters)

                # Identify dominant patterns
                dominant_patterns = identify_dominant_patterns(access_patterns, query_clusters)

                result.update(
                    {
                        "query_clusters": query_clusters,
                        "access_patterns": access_patterns,
                        "dominant_patterns": dominant_patterns,
                        "total_queries_analyzed": len(queries),
                        "total_clusters": len(query_clusters),
                        "status": "success",
                    }
                )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to analyze access patterns for {table_name}: {e}")
        result["error"] = str(e)
        result["status"] = "error"

    return result


def analyze_cluster_patterns(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Analyze query clusters to identify access patterns.

    Args:
        clusters: List of query clusters

    Returns:
        List of identified access patterns
    """
    patterns = []

    for cluster in clusters:
        signature = cluster["signature"]
        query_type = cluster["query_type"]
        table_name = cluster["table_name"]
        field_name = cluster["field_name"]

        # Identify pattern type based on metadata
        pattern_type = classify_query_pattern_from_metadata(query_type, field_name)
        frequency = cluster["query_count"]
        avg_cost = cluster["avg_duration_ms"]
        importance_score = cluster["importance_score"]

        patterns.append(
            {
                "pattern_type": pattern_type,
                "signature": signature,
                "query_type": query_type,
                "table_name": table_name,
                "field_name": field_name,
                "frequency": frequency,
                "avg_cost_ms": avg_cost,
                "importance_score": importance_score,
            }
        )

    # Sort by importance
    patterns.sort(key=lambda x: x["importance_score"], reverse=True)

    return patterns


def classify_query_pattern(template: str) -> str:
    """
    Classify query pattern based on template analysis.

    Args:
        template: Normalized query template

    Returns:
        Pattern classification string
    """
    template_upper = template.upper()

    # SELECT patterns
    if template_upper.startswith("SELECT"):
        if "WHERE" in template_upper:
            if "ORDER BY" in template_upper:
                return "selective_ordered_select"
            elif "JOIN" in template_upper:
                return "selective_join_select"
            else:
                return "selective_point_select"
        elif "ORDER BY" in template_upper:
            return "full_table_scan_ordered"
        else:
            return "full_table_scan"

    # INSERT patterns
    elif template_upper.startswith("INSERT"):
        if "SELECT" in template_upper:
            return "insert_select"
        else:
            return "bulk_insert"

    # UPDATE patterns
    elif template_upper.startswith("UPDATE"):
        if "WHERE" in template_upper:
            return "selective_update"
        else:
            return "bulk_update"

    # DELETE patterns
    elif template_upper.startswith("DELETE"):
        if "WHERE" in template_upper:
            return "selective_delete"
        else:
            return "bulk_delete"

    # Other patterns
    else:
        return "other"


def classify_query_pattern_from_metadata(query_type: str, field_name: str = "") -> str:
    """
    Classify query pattern based on available metadata.

    Args:
        query_type: Query type from query_stats (SELECT, INSERT, etc.)
        field_name: Field name if available

    Returns:
        Pattern classification string
    """
    if query_type == "SELECT":
        if field_name:
            return "selective_field_query"
        else:
            return "table_scan_query"
    elif query_type in ["INSERT", "UPDATE", "DELETE"]:
        if field_name:
            return "targeted_modification"
        else:
            return "bulk_modification"
    else:
        return "other_query"


def identify_dominant_patterns(
    access_patterns: list[dict[str, Any]], clusters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Identify dominant access patterns that should influence indexing decisions.

    Args:
        access_patterns: List of access patterns
        clusters: Original query clusters

    Returns:
        List of dominant patterns with indexing recommendations
    """
    dominant_patterns: list[dict[str, Any]] = []

    # Get config settings
    config = get_workload_config()
    dominant_threshold = config.get("dominant_pattern_threshold", 0.05)

    # Calculate total importance for normalization
    total_importance = sum(p["importance_score"] for p in access_patterns)

    if total_importance == 0:
        return dominant_patterns

    # Identify patterns that represent > threshold of total workload
    for pattern in access_patterns:
        importance_ratio = pattern["importance_score"] / total_importance

        if importance_ratio > dominant_threshold:  # More than threshold % of workload
            # Generate indexing recommendation based on pattern
            index_recommendation = generate_pattern_index_recommendation(pattern)

            dominant_patterns.append(
                {
                    **pattern,
                    "importance_ratio": importance_ratio,
                    "index_recommendation": index_recommendation,
                }
            )

    return dominant_patterns


def generate_pattern_index_recommendation(pattern: dict[str, Any]) -> dict[str, Any]:
    """
    Generate indexing recommendation based on access pattern.

    Args:
        pattern: Access pattern information

    Returns:
        Dict with index recommendation details
    """
    pattern_type = pattern["pattern_type"]
    table_name = pattern["table_name"]
    frequency = pattern["frequency"]

    recommendation = {
        "table": table_name,
        "priority": "medium",
        "reason": f"Pattern '{pattern_type}' appears {frequency} times",
        "suggested_indexes": [],
    }

    # Pattern-specific recommendations
    if pattern_type in ["selective_point_select", "selective_ordered_select"]:
        recommendation.update(
            {
                "priority": "high",
                "reason": f"High-frequency selective queries ({frequency} occurrences) - index recommended",
                "suggested_indexes": [
                    {"type": "btree", "columns": ["id"], "reason": "Primary key lookups"},
                    {"type": "btree", "columns": ["created_at"], "reason": "Temporal filtering"},
                ],
            }
        )

    elif pattern_type == "selective_join_select":
        recommendation.update(
            {
                "priority": "high",
                "reason": f"Join queries ({frequency} occurrences) - foreign key indexes recommended",
                "suggested_indexes": [
                    {"type": "btree", "columns": ["foreign_key_id"], "reason": "Foreign key joins"}
                ],
            }
        )

    elif pattern_type in ["full_table_scan_ordered", "selective_ordered_select"]:
        recommendation.update(
            {
                "priority": "medium",
                "reason": f"Ordered queries ({frequency} occurrences) - consider composite indexes",
                "suggested_indexes": [
                    {
                        "type": "btree",
                        "columns": ["sort_column", "filter_column"],
                        "reason": "ORDER BY optimization",
                    }
                ],
            }
        )

    return recommendation


def get_enhanced_workload_recommendation(
    table_name: str, access_patterns: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Get enhanced workload recommendation using access pattern analysis.

    Args:
        table_name: Table name to analyze
        access_patterns: Pre-computed access patterns (optional)

    Returns:
        Enhanced workload recommendation with pattern-based insights
    """
    if access_patterns is None:
        access_patterns = analyze_access_patterns(table_name)

    if access_patterns.get("status") != "success":
        # Fall back to basic workload analysis
        return get_workload_recommendation(table_name)

    # Analyze dominant patterns for comprehensive recommendation
    dominant_patterns = access_patterns.get("dominant_patterns", [])
    query_clusters = access_patterns.get("query_clusters", [])

    # Get basic workload info
    basic_workload = analyze_workload(table_name=table_name)
    if basic_workload.get("skipped"):
        return {"recommendation": "unknown", "reason": "workload_analysis_disabled"}

    # Find table workload info
    table_info = None
    for table in basic_workload.get("tables", []):
        if table["table_name"] == table_name:
            table_info = table
            break

    if not table_info:
        return {"recommendation": "unknown", "reason": "no_workload_data"}

    workload_type = table_info.get("workload_type", "balanced")
    read_ratio = table_info.get("read_ratio", 0.5)

    # Enhance recommendation with pattern analysis
    recommendation = {
        "workload_type": workload_type,
        "read_ratio": read_ratio,
        "dominant_patterns": len(dominant_patterns),
        "query_clusters": len(query_clusters),
        "enhancement_applied": True,
    }

    # Adjust recommendation based on dominant patterns
    if dominant_patterns:
        # Check for high-priority selective queries
        selective_patterns = [
            p
            for p in dominant_patterns
            if p["pattern_type"] in ["selective_point_select", "selective_join_select"]
        ]

        if selective_patterns and workload_type == "read_heavy":
            recommendation.update(
                {
                    "recommendation": "very_aggressive",
                    "reason": f"Read-heavy workload with {len(selective_patterns)} high-value selective patterns",
                    "suggestion": "Create indexes aggressively for optimal read performance",
                    "pattern_insights": [p["pattern_type"] for p in selective_patterns[:3]],
                }
            )
        elif selective_patterns:
            recommendation.update(
                {
                    "recommendation": "aggressive",
                    "reason": f"Found {len(selective_patterns)} selective query patterns",
                    "suggestion": "Prioritize indexes for selective query patterns",
                    "pattern_insights": [p["pattern_type"] for p in selective_patterns[:3]],
                }
            )
        else:
            # Use basic workload logic
            recommendation.update(get_workload_recommendation(table_name, basic_workload))
    else:
        # No dominant patterns, use basic analysis
        recommendation.update(get_workload_recommendation(table_name, basic_workload))

    return recommendation
