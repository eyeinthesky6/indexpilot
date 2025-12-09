"""Query pattern learning from history for improved interception"""

# INTEGRATION NOTE: XGBoost ML Enhancement
# Status: ✅ Implemented
# Enhancement: XGBoost (arXiv:1603.02754) for advanced pattern classification
# Integration: Use XGBoost model for pattern classification and index recommendation scoring
# See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

import logging
import threading
from datetime import datetime
from typing import Any

from src.algorithms.xgboost_classifier import (
    classify_pattern,
    is_xgboost_enabled,
    score_recommendation,
    train_model,
)
from src.db import get_cursor

logger = logging.getLogger(__name__)

# Pattern learning cache (in-memory, could be persisted to DB)
_pattern_cache: dict[str, dict[str, Any]] = {}
_pattern_cache_lock = threading.Lock()
_cache_ttl = 3600  # 1 hour

# Slow query patterns (learned from history)
_slow_query_patterns: dict[str, dict[str, Any]] = {}
_slow_patterns_lock = threading.Lock()

# Fast query patterns (allowlist candidates)
_fast_query_patterns: dict[str, dict[str, Any]] = {}
_fast_patterns_lock = threading.Lock()


def learn_from_slow_queries(
    time_window_hours: int = 24,
    slow_threshold_ms: float = 1000.0,
    min_occurrences: int = 3,
) -> dict[str, Any]:
    """
    Learn patterns from slow queries in history.

    Analyzes query_stats to identify patterns that consistently cause slow queries.

    Args:
        time_window_hours: Time window to analyze
        slow_threshold_ms: Duration threshold for "slow" queries (default: 1000ms)
        min_occurrences: Minimum occurrences to consider a pattern (default: 3)

    Returns:
        dict with learned patterns and statistics
    """
    with get_cursor() as cursor:
        # Get slow queries from query_stats
        cursor.execute(
            """
            SELECT
                table_name,
                field_name,
                query_type,
                COUNT(*) as occurrence_count,
                AVG(duration_ms) as avg_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                MAX(duration_ms) as max_duration_ms
            FROM query_stats
            WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
              AND duration_ms >= %s
            GROUP BY table_name, field_name, query_type
            HAVING COUNT(*) >= %s
            ORDER BY avg_duration_ms DESC
        """,
            (time_window_hours, slow_threshold_ms, min_occurrences),
        )

        slow_queries = cursor.fetchall()

        learned_patterns: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "time_window_hours": time_window_hours,
            "slow_threshold_ms": slow_threshold_ms,
            "patterns": [],
            "summary": {
                "total_patterns": 0,
                "total_slow_queries": 0,
                "avg_duration_ms": 0.0,
            },
        }

        total_duration = 0.0
        total_count = 0

        with _slow_patterns_lock:
            for query in slow_queries:
                table_name = query["table_name"]
                field_name = query.get("field_name", "")
                query_type = query.get("query_type", "SELECT")
                avg_duration = query.get("avg_duration_ms", 0) or 0
                occurrence_count = query.get("occurrence_count", 0) or 0

                # Create pattern signature
                pattern_key = f"{table_name}:{field_name}:{query_type}"

                pattern = {
                    "table_name": table_name,
                    "field_name": field_name,
                    "query_type": query_type,
                    "pattern_key": pattern_key,
                    "avg_duration_ms": round(avg_duration, 2),
                    "p95_duration_ms": round(query.get("p95_duration_ms", 0) or 0, 2),
                    "max_duration_ms": round(query.get("max_duration_ms", 0) or 0, 2),
                    "occurrence_count": occurrence_count,
                    "risk_level": _calculate_risk_level(avg_duration, occurrence_count),
                }

                patterns_list = learned_patterns["patterns"]
                if isinstance(patterns_list, list):
                    patterns_list.append(pattern)
                _slow_query_patterns[pattern_key] = pattern

                total_duration += avg_duration * occurrence_count
                total_count += occurrence_count

        if total_count > 0:
            learned_patterns["summary"]["avg_duration_ms"] = round(total_duration / total_count, 2)
        patterns_list = learned_patterns["patterns"]
        pattern_count = len(patterns_list) if isinstance(patterns_list, list) else 0
        summary = learned_patterns["summary"]
        if isinstance(summary, dict):
            summary["total_patterns"] = pattern_count
            summary["total_slow_queries"] = total_count

        logger.info(f"Learned {pattern_count} slow query patterns from {total_count} slow queries")

        return learned_patterns


def learn_from_fast_queries(
    time_window_hours: int = 24,
    fast_threshold_ms: float = 10.0,
    min_occurrences: int = 10,
) -> dict[str, Any]:
    """
    Learn patterns from fast queries to build allowlist.

    Identifies query patterns that consistently perform well.

    Args:
        time_window_hours: Time window to analyze
        fast_threshold_ms: Duration threshold for "fast" queries (default: 10ms)
        min_occurrences: Minimum occurrences to consider a pattern (default: 10)

    Returns:
        dict with learned fast patterns
    """
    with get_cursor() as cursor:
        # Get fast queries from query_stats
        cursor.execute(
            """
            SELECT
                table_name,
                field_name,
                query_type,
                COUNT(*) as occurrence_count,
                AVG(duration_ms) as avg_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms
            FROM query_stats
            WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
              AND duration_ms <= %s
            GROUP BY table_name, field_name, query_type
            HAVING COUNT(*) >= %s
            ORDER BY occurrence_count DESC
        """,
            (time_window_hours, fast_threshold_ms, min_occurrences),
        )

        fast_queries = cursor.fetchall()

        learned_patterns = {
            "timestamp": datetime.now().isoformat(),
            "time_window_hours": time_window_hours,
            "fast_threshold_ms": fast_threshold_ms,
            "patterns": [],
            "summary": {
                "total_patterns": 0,
                "total_fast_queries": 0,
            },
        }

        total_count = 0

        with _fast_patterns_lock:
            for query in fast_queries:
                table_name = query["table_name"]
                field_name = query.get("field_name", "")
                query_type = query.get("query_type", "SELECT")
                avg_duration = query.get("avg_duration_ms", 0) or 0
                occurrence_count = query.get("occurrence_count", 0) or 0

                # Create pattern signature
                pattern_key = f"{table_name}:{field_name}:{query_type}"

                pattern = {
                    "table_name": table_name,
                    "field_name": field_name,
                    "query_type": query_type,
                    "pattern_key": pattern_key,
                    "avg_duration_ms": round(avg_duration, 2),
                    "p95_duration_ms": round(query.get("p95_duration_ms", 0) or 0, 2),
                    "occurrence_count": occurrence_count,
                    "confidence": min(
                        1.0, occurrence_count / 100.0
                    ),  # Higher count = more confidence
                }

                patterns_list = learned_patterns["patterns"]
                if isinstance(patterns_list, list):
                    patterns_list.append(pattern)
                _fast_query_patterns[pattern_key] = pattern

                total_count += occurrence_count

        patterns_list = learned_patterns["patterns"]
        pattern_count = len(patterns_list) if isinstance(patterns_list, list) else 0
        summary = learned_patterns["summary"]
        if isinstance(summary, dict):
            summary["total_patterns"] = pattern_count
            summary["total_fast_queries"] = total_count

        logger.info(f"Learned {pattern_count} fast query patterns from {total_count} fast queries")

        return learned_patterns


def _calculate_risk_level(avg_duration_ms: float, occurrence_count: int) -> str:
    """Calculate risk level for a slow query pattern."""
    if avg_duration_ms > 5000 or occurrence_count > 100:
        return "critical"
    elif avg_duration_ms > 2000 or occurrence_count > 50:
        return "high"
    elif avg_duration_ms > 1000 or occurrence_count > 20:
        return "medium"
    else:
        return "low"


def match_query_pattern(
    table_name: str, field_name: str | None = None, query_type: str = "SELECT"
) -> dict[str, Any] | None:
    """
    Match a query against learned patterns.

    Enhanced with XGBoost classification for improved accuracy.

    Args:
        table_name: Table name
        field_name: Field name (optional)
        query_type: Query type (SELECT, INSERT, etc.)

    Returns:
        Pattern match dict if found, None otherwise
    """
    pattern_key = f"{table_name}:{field_name or '*'}:{query_type}"

    # Check slow patterns first
    with _slow_patterns_lock:
        if pattern_key in _slow_query_patterns:
            pattern = _slow_query_patterns[pattern_key]
            result = {
                "matched": True,
                "pattern_type": "slow",
                "pattern": pattern,
                "recommendation": "block"
                if pattern.get("risk_level") in ["critical", "high"]
                else "warn",
            }

            # Enhance with XGBoost classification if enabled
            if is_xgboost_enabled():
                xgboost_result = classify_pattern(
                    table_name=table_name,
                    field_name=field_name,
                    query_type=query_type,
                    avg_duration_ms=pattern.get("avg_duration_ms"),
                    p95_duration_ms=pattern.get("p95_duration_ms"),
                    occurrence_count=pattern.get("occurrence_count"),
                )
                result["xgboost_classification"] = xgboost_result
                # Adjust recommendation based on XGBoost score
                xgboost_score = xgboost_result.get("classification_score", 0.5)
                if xgboost_score > 0.7 and result["recommendation"] == "warn":
                    result["recommendation"] = "block"  # Upgrade to block if high score
                elif xgboost_score < 0.3 and result["recommendation"] == "block":
                    result["recommendation"] = "warn"  # Downgrade to warn if low score

            return result

    # Check fast patterns
    with _fast_patterns_lock:
        if pattern_key in _fast_query_patterns:
            pattern = _fast_query_patterns[pattern_key]
            result = {
                "matched": True,
                "pattern_type": "fast",
                "pattern": pattern,
                "recommendation": "allow",
            }

            # Enhance with XGBoost classification if enabled
            if is_xgboost_enabled():
                xgboost_result = classify_pattern(
                    table_name=table_name,
                    field_name=field_name,
                    query_type=query_type,
                    avg_duration_ms=pattern.get("avg_duration_ms"),
                    occurrence_count=pattern.get("occurrence_count"),
                )
                result["xgboost_classification"] = xgboost_result

            return result

    # If no pattern match but XGBoost is enabled, try XGBoost classification
    if is_xgboost_enabled():
        xgboost_result = classify_pattern(
            table_name=table_name,
            field_name=field_name,
            query_type=query_type,
        )
        if xgboost_result.get("method") == "xgboost":
            xgboost_score = xgboost_result.get("classification_score", 0.5)
            if xgboost_score > 0.7:
                return {
                    "matched": True,
                    "pattern_type": "xgboost_predicted_slow",
                    "pattern": None,
                    "recommendation": "warn",
                    "xgboost_classification": xgboost_result,
                }

    return None


def build_allowlist_from_history(
    time_window_hours: int = 24,
    confidence_threshold: float = 0.8,
) -> set[str]:
    """
    Build allowlist of query patterns from history.

    Args:
        time_window_hours: Time window to analyze
        confidence_threshold: Minimum confidence to add to allowlist (default: 0.8)

    Returns:
        Set of pattern keys to allowlist
    """
    fast_patterns = learn_from_fast_queries(time_window_hours=time_window_hours, min_occurrences=20)

    allowlist: set[str] = set()

    for pattern in fast_patterns.get("patterns", []):
        confidence = pattern.get("confidence", 0.0)
        if confidence >= confidence_threshold:
            allowlist.add(pattern["pattern_key"])

    logger.info(f"Built allowlist with {len(allowlist)} patterns")
    return allowlist


def build_blocklist_from_history(
    time_window_hours: int = 24,
    risk_threshold: str = "medium",
) -> set[str]:
    """
    Build blocklist of query patterns from history.

    Args:
        time_window_hours: Time window to analyze
        risk_threshold: Minimum risk level to block (default: "medium")

    Returns:
        Set of pattern keys to blocklist
    """
    slow_patterns = learn_from_slow_queries(time_window_hours=time_window_hours, min_occurrences=3)

    blocklist: set[str] = set()
    risk_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    threshold_level = risk_levels.get(risk_threshold, 2)

    for pattern in slow_patterns.get("patterns", []):
        risk_level = pattern.get("risk_level", "low")
        if risk_levels.get(risk_level, 0) >= threshold_level:
            blocklist.add(pattern["pattern_key"])

    logger.info(f"Built blocklist with {len(blocklist)} patterns")
    return blocklist


def get_pattern_statistics() -> dict[str, Any]:
    """Get statistics on learned patterns."""
    with _slow_patterns_lock, _fast_patterns_lock:
        stats = {
            "slow_patterns": len(_slow_query_patterns),
            "fast_patterns": len(_fast_query_patterns),
            "slow_patterns_detail": list(_slow_query_patterns.values()),
            "fast_patterns_detail": list(_fast_query_patterns.values()),
        }

        # Add XGBoost status if enabled
        if is_xgboost_enabled():
            stats["xgboost_enabled"] = True
            # Try to train model to check if it's available
            try:
                train_model(force_retrain=False)
                stats["xgboost_model_available"] = True
            except Exception:
                stats["xgboost_model_available"] = False
        else:
            stats["xgboost_enabled"] = False

        return stats


def get_index_recommendation_score(
    table_name: str,
    field_name: str,
    query_type: str = "SELECT",
    duration_ms: float | None = None,
    occurrence_count: int | None = None,
    avg_duration_ms: float | None = None,
    row_count: int | None = None,
    selectivity: float | None = None,
) -> float:
    """
    Get index recommendation score using XGBoost classification.

    Enhanced version that uses XGBoost for pattern classification to improve
    recommendation accuracy.

    Args:
        table_name: Table name
        field_name: Field name
        query_type: Query type
        duration_ms: Query duration in milliseconds
        occurrence_count: Number of occurrences
        avg_duration_ms: Average duration in milliseconds
        row_count: Table row count
        selectivity: Field selectivity (0.0 to 1.0)

    Returns:
        Recommendation score (0.0 to 1.0), higher = better recommendation
    """
    if is_xgboost_enabled():
        return score_recommendation(
            table_name=table_name,
            field_name=field_name,
            query_type=query_type,
            duration_ms=duration_ms,
            occurrence_count=occurrence_count,
            avg_duration_ms=avg_duration_ms,
            row_count=row_count,
            selectivity=selectivity,
        )
    else:
        # Fallback to basic pattern matching
        pattern_match = match_query_pattern(table_name, field_name, query_type)
        if pattern_match:
            if pattern_match.get("pattern_type") == "slow":
                return 0.8  # High score for slow patterns
            elif pattern_match.get("pattern_type") == "fast":
                return 0.2  # Low score for fast patterns
        return 0.5  # Neutral score
