"""Fractal Tree Index Algorithm Implementation

Fractal Tree indexes are write-optimized data structures that provide better write
performance than traditional B-trees by using buffered writes at each node level.

This module implements Fractal Tree concepts for write-optimized index recommendations,
helping to:
- Identify write-heavy workloads that would benefit from Fractal Tree-like behavior
- Recommend index strategies optimized for write performance
- Provide buffered write optimization recommendations

Fractal Tree benefits:
- Faster insertions/deletions than B-trees (buffered writes)
- Better write performance for large data blocks
- Optimized disk writes through node-level buffering
- Suitable for write-heavy workloads

Note: PostgreSQL doesn't natively support Fractal Tree indexes, but this module
provides analysis and recommendations for write-optimized indexing strategies.

Algorithm concepts are not copyrightable; attribution provided as good practice.
"""

import logging

from src.config_loader import ConfigLoader
from src.stats import get_table_row_count
from src.type_definitions import JSONDict
from src.workload_analysis import analyze_workload

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def should_use_fractal_tree_strategy(
    table_name: str,
    field_name: str,
    time_window_hours: int = 24,
) -> JSONDict:
    """
    Determine if Fractal Tree strategy would be beneficial for this table/field.

    Fractal Tree indexes are beneficial for:
    - Write-heavy workloads (high write-to-read ratio)
    - Frequent insertions/deletions
    - Large batch writes
    - Tables with high write frequency
    - Workloads where write performance is critical

    Args:
        table_name: Table name
        field_name: Field name
        time_window_hours: Time window for workload analysis (default: 24 hours)

    Returns:
        dict with Fractal Tree recommendation:
        - should_use_fractal_tree: bool - Whether Fractal Tree strategy is recommended
        - confidence: float - Confidence in recommendation (0.0 to 1.0)
        - reason: str - Reason for recommendation
        - workload_characteristics: dict - Workload analysis details
        - recommendation: str - Specific recommendation
    """
    try:
        # Analyze workload to determine write-heavy characteristics
        workload_info = analyze_workload(
            table_name=table_name,
            time_window_hours=time_window_hours,
        )

        # Get table size
        table_row_count = get_table_row_count(table_name)

        # Extract workload metrics
        read_queries_val = workload_info.get("read_queries", 0)
        read_queries = int(read_queries_val) if isinstance(read_queries_val, int | float) else 0
        write_queries_val = workload_info.get("write_queries", 0)
        write_queries = int(write_queries_val) if isinstance(write_queries_val, int | float) else 0
        total_queries = read_queries + write_queries

        # Calculate write ratio
        write_ratio = float(write_queries) / float(total_queries) if total_queries > 0 else 0.0

        # Fractal Tree configuration thresholds
        write_heavy_threshold = _config_loader.get_float(
            "features.fractal_tree.write_heavy_threshold", 0.4
        )
        min_queries_for_fractal_tree = _config_loader.get_int(
            "features.fractal_tree.min_queries", 100
        )
        min_table_size_for_fractal_tree = _config_loader.get_int(
            "features.fractal_tree.min_table_size", 10000
        )

        # Check if we have enough data for analysis
        if total_queries < min_queries_for_fractal_tree:
            return {
                "should_use_fractal_tree": False,
                "confidence": 0.0,
                "reason": "insufficient_queries",
                "workload_characteristics": {
                    "read_queries": read_queries,
                    "write_queries": write_queries,
                    "total_queries": total_queries,
                    "write_ratio": write_ratio,
                    "table_row_count": table_row_count,
                },
                "recommendation": "fractal_tree_not_applicable",
                "recommendation_detail": (
                    f"Insufficient query data ({total_queries} queries) for Fractal Tree analysis. "
                    f"Need at least {min_queries_for_fractal_tree} queries."
                ),
            }

        # Check if table is large enough
        if table_row_count < min_table_size_for_fractal_tree:
            return {
                "should_use_fractal_tree": False,
                "confidence": 0.0,
                "reason": "table_too_small",
                "workload_characteristics": {
                    "read_queries": read_queries,
                    "write_queries": write_queries,
                    "total_queries": total_queries,
                    "write_ratio": write_ratio,
                    "table_row_count": table_row_count,
                },
                "recommendation": "fractal_tree_not_applicable",
                "recommendation_detail": (
                    f"Table too small ({table_row_count} rows) for Fractal Tree consideration. "
                    f"Need at least {min_table_size_for_fractal_tree} rows."
                ),
            }

        # Calculate Fractal Tree suitability score
        # Fractal Tree benefits from:
        # 1. High write ratio (primary factor)
        # 2. High write frequency (many write operations)
        # 3. Large table size (more benefit from buffered writes)
        # 4. Write-heavy workload pattern
        fractal_tree_score = 0.0
        reasons = []

        # Factor 1: Write ratio (most important for Fractal Tree)
        if write_ratio >= write_heavy_threshold:
            # Higher write ratio = higher score (up to 0.5)
            write_score = min(0.5, (write_ratio - write_heavy_threshold) * 1.5)
            fractal_tree_score += write_score
            reasons.append(f"write_heavy_workload ({write_ratio:.1%} writes)")

        # Factor 2: Write frequency (absolute number of writes)
        if write_queries >= 1000:
            fractal_tree_score += 0.2
            reasons.append(f"high_write_frequency ({write_queries} writes)")
        elif write_queries >= 500:
            fractal_tree_score += 0.1
            reasons.append(f"moderate_write_frequency ({write_queries} writes)")

        # Factor 3: Large table (more benefit from buffered writes)
        if table_row_count >= 100000:
            fractal_tree_score += 0.2
            reasons.append(f"large_table ({table_row_count} rows)")
        elif table_row_count >= 50000:
            fractal_tree_score += 0.1
            reasons.append(f"medium_table ({table_row_count} rows)")

        # Factor 4: Write-heavy pattern (write ratio significantly higher than read)
        if write_ratio > 0.6 and read_queries < write_queries:
            fractal_tree_score += 0.1
            reasons.append("write_dominant_pattern")

        # Check if Fractal Tree strategy is recommended
        min_fractal_tree_score = _config_loader.get_float(
            "features.fractal_tree.min_suitability_score", 0.5
        )
        should_use = fractal_tree_score >= min_fractal_tree_score
        confidence = min(fractal_tree_score, 1.0)

        # Generate recommendation
        if should_use:
            recommendation = "fractal_tree_strategy_recommended"
            recommendation_detail = (
                f"Write-heavy workload ({write_ratio:.1%} writes, {write_queries} write queries) "
                f"would benefit from Fractal Tree-like write-optimized indexing strategy"
            )
        else:
            recommendation = "fractal_tree_strategy_not_recommended"
            if write_ratio < write_heavy_threshold:
                recommendation_detail = (
                    f"Not write-heavy enough ({write_ratio:.1%} writes) - "
                    f"standard B-tree indexing sufficient"
                )
            else:
                recommendation_detail = "Standard indexing strategy sufficient for this workload"

        return {
            "should_use_fractal_tree": should_use,
            "confidence": confidence,
            "reason": "; ".join(reasons) if reasons else "standard_workload",
            "workload_characteristics": {
                "read_queries": read_queries,
                "write_queries": write_queries,
                "total_queries": total_queries,
                "write_ratio": write_ratio,
                "table_row_count": table_row_count,
                "fractal_tree_score": fractal_tree_score,
            },
            "recommendation": recommendation,
            "recommendation_detail": recommendation_detail,
        }

    except Exception as e:
        logger.error(
            f"Error in should_use_fractal_tree_strategy for {table_name}.{field_name}: {e}"
        )
        return {
            "should_use_fractal_tree": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "workload_characteristics": {},
            "recommendation": "error",
        }


def get_fractal_tree_index_recommendation(
    table_name: str,
    field_name: str,
    query_patterns: JSONDict,
    time_window_hours: int = 24,
) -> JSONDict:
    """
    Get Fractal Tree-based index type recommendation for write-heavy workloads.

    Since PostgreSQL doesn't natively support Fractal Tree indexes, this function:
    1. Identifies when Fractal Tree strategy would be beneficial
    2. Recommends PostgreSQL index types that provide similar write-optimized benefits
    3. Suggests index strategies that optimize write performance

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information
        time_window_hours: Time window for workload analysis (default: 24 hours)

    Returns:
        dict with index recommendation:
        - index_type: str - Recommended index type (btree, hash, etc.)
        - use_fractal_tree_strategy: bool - Whether to use Fractal Tree-like approach
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for recommendation
        - fractal_tree_insights: dict - Fractal Tree-specific insights
    """
    try:
        # Check if Fractal Tree strategy is recommended
        fractal_tree_analysis = should_use_fractal_tree_strategy(
            table_name=table_name,
            field_name=field_name,
            time_window_hours=time_window_hours,
        )

        should_use_val = fractal_tree_analysis.get("should_use_fractal_tree", False)
        should_use = (
            bool(should_use_val) if isinstance(should_use_val, bool | int | float) else False
        )
        if not should_use:
            # Fractal Tree not recommended, return standard recommendation
            confidence_val = fractal_tree_analysis.get("confidence", 0.0)
            confidence = float(confidence_val) if isinstance(confidence_val, int | float) else 0.0
            reason_val = fractal_tree_analysis.get("recommendation_detail", "standard_indexing")
            reason = str(reason_val) if isinstance(reason_val, str) else "standard_indexing"
            return {
                "index_type": "btree",
                "use_fractal_tree_strategy": False,
                "confidence": 1.0 - confidence,
                "reason": reason,
                "fractal_tree_insights": fractal_tree_analysis,
            }

        # Fractal Tree strategy is recommended
        workload_chars_val = fractal_tree_analysis.get("workload_characteristics", {})
        workload_chars = workload_chars_val if isinstance(workload_chars_val, dict) else {}
        write_ratio_val = workload_chars.get("write_ratio", 0.0)
        write_ratio = float(write_ratio_val) if isinstance(write_ratio_val, int | float) else 0.0

        # For write-heavy workloads, Fractal Tree benefits:
        # - Buffered writes (reduces disk I/O)
        # - Faster insertions/deletions
        # - Better write performance for large batches

        # Strategy 1: For very write-heavy workloads, consider fewer indexes
        # Fractal Tree's buffered writes help, but in PostgreSQL we can:
        # - Use fewer indexes to reduce write overhead
        # - Consider partial indexes to reduce write cost
        # - Use covering indexes to reduce index maintenance

        if write_ratio >= 0.7:
            confidence_val = fractal_tree_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, int | float) else 0.7
            return {
                "index_type": "btree",
                "use_fractal_tree_strategy": True,
                "confidence": confidence,
                "reason": (
                    "Fractal Tree strategy: Very write-heavy workload - "
                    "consider fewer indexes and partial indexes to optimize write performance "
                    "(similar to Fractal Tree's buffered write optimization)"
                ),
                "fractal_tree_insights": fractal_tree_analysis,
                "strategy_recommendations": [
                    "Consider reducing number of indexes to minimize write overhead",
                    "Use partial indexes for filtered queries (reduces write cost)",
                    "Consider covering indexes to reduce index maintenance overhead",
                    "Monitor write performance and adjust index strategy accordingly",
                    "Consider batch writes to optimize write performance",
                ],
            }

        # Strategy 2: For moderate write-heavy workloads, standard B-tree with optimizations
        if write_ratio >= 0.4:
            confidence_val = fractal_tree_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, int | float) else 0.7
            return {
                "index_type": "btree",
                "use_fractal_tree_strategy": True,
                "confidence": confidence,
                "reason": (
                    "Fractal Tree strategy: Write-heavy workload - "
                    "B-tree with write-optimization considerations recommended "
                    "(use partial/covering indexes where beneficial)"
                ),
                "fractal_tree_insights": fractal_tree_analysis,
                "strategy_recommendations": [
                    "Use partial indexes for filtered queries (reduces write cost)",
                    "Consider covering indexes to reduce index maintenance",
                    "Monitor write performance and adjust as needed",
                    "Consider batch writes for better write performance",
                ],
            }

        # Default: B-tree with Fractal Tree-like considerations
        confidence_val = fractal_tree_analysis.get("confidence", 0.7)
        confidence = float(confidence_val) if isinstance(confidence_val, int | float) else 0.7
        return {
            "index_type": "btree",
            "use_fractal_tree_strategy": True,
            "confidence": confidence,
            "reason": (
                "Fractal Tree strategy: B-tree recommended with write-optimization considerations "
                "(use partial/covering indexes where beneficial to reduce write overhead)"
            ),
            "fractal_tree_insights": fractal_tree_analysis,
            "strategy_recommendations": [
                "Consider partial indexes for filtered queries (reduces write cost)",
                "Monitor write performance and adjust index strategy accordingly",
                "Consider batch writes to optimize write performance",
            ],
        }

    except Exception as e:
        logger.error(
            f"Error in get_fractal_tree_index_recommendation for {table_name}.{field_name}: {e}"
        )
        return {
            "index_type": "btree",
            "use_fractal_tree_strategy": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "fractal_tree_insights": {},
        }
