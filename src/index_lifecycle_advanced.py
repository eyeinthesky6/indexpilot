"""Advanced index lifecycle management: predictive maintenance, versioning, A/B testing"""

import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.index_health import monitor_index_health
from src.monitoring import get_monitoring
from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)

# Index versioning storage (in-memory, could be persisted to DB)
_index_versions: dict[str, list[dict[str, Any]]] = {}
_version_lock = threading.Lock()

# A/B testing experiments
_ab_experiments: dict[str, dict[str, Any]] = {}
_ab_lock = threading.Lock()

# Predictive maintenance models (simple linear regression for now)
_bloat_predictions: dict[str, dict[str, Any]] = {}
_prediction_lock = threading.Lock()


def track_index_version(
    index_name: str,
    table_name: str,
    index_definition: str,
    created_by: str = "auto_indexer",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Track a new version of an index for versioning and rollback.

    Args:
        index_name: Name of the index
        table_name: Table the index is on
        index_definition: Full CREATE INDEX statement
        created_by: Who/what created this version
        metadata: Additional metadata (performance metrics, etc.)

    Returns:
        Version record
    """
    if not is_system_enabled():
        logger.debug("Index versioning skipped: system is disabled")
        return {}

    version_record = {
        "index_name": index_name,
        "table_name": table_name,
        "index_definition": index_definition,
        "created_by": created_by,
        "created_at": datetime.now().isoformat(),
        "metadata": metadata or {},
    }

    with _version_lock:
        if index_name not in _index_versions:
            _index_versions[index_name] = []
        _index_versions[index_name].append(version_record)

    logger.info(
        f"Tracked version for index {index_name} (version {len(_index_versions[index_name])})"
    )
    return version_record


def get_index_versions(index_name: str) -> list[dict[str, Any]]:
    """
    Get all versions of an index.

    Args:
        index_name: Name of the index

    Returns:
        List of version records (oldest first)
    """
    with _version_lock:
        return _index_versions.get(index_name, []).copy()


def rollback_index_version(index_name: str, version_index: int = -1) -> dict[str, Any]:
    """
    Rollback to a previous index version.

    Args:
        index_name: Name of the index
        version_index: Version to rollback to (-1 = previous version)

    Returns:
        Rollback result
    """
    if not is_system_enabled():
        logger.warning("Index rollback skipped: system is disabled")
        return {"status": "disabled"}

    with _version_lock:
        versions = _index_versions.get(index_name, [])
        if not versions:
            return {"status": "error", "error": "No versions found"}

        if abs(version_index) > len(versions):
            return {"status": "error", "error": "Invalid version index"}

        target_version = versions[version_index]
        previous_definition = target_version["index_definition"]

    # Drop current index and recreate from previous version
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Drop current index
                cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')
                conn.commit()

                # Recreate from previous version
                cursor.execute(previous_definition)
                conn.commit()

                logger.info(f"Rolled back index {index_name} to version {version_index}")
                return {
                    "status": "success",
                    "index_name": index_name,
                    "version_index": version_index,
                    "definition": previous_definition,
                }
            finally:
                cursor.close()
    except Exception as e:
        logger.error(f"Failed to rollback index {index_name}: {e}")
        return {"status": "error", "error": str(e)}


def predict_index_bloat(
    index_name: str,
    days_ahead: int = 7,
    historical_days: int = 30,
) -> dict[str, Any]:
    """
    Predict index bloat using simple linear regression on historical data.

    Args:
        index_name: Name of the index
        days_ahead: Days to predict ahead
        historical_days: Days of history to use

    Returns:
        Prediction with confidence interval
    """
    if not is_system_enabled():
        return {"status": "disabled"}

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get historical index size data
                cursor.execute(
                    """
                    SELECT
                        created_at,
                        details_json->>'index_name' as idx_name,
                        (details_json->>'size_bytes')::bigint as size_bytes
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                      AND details_json->>'index_name' = %s
                      AND created_at >= NOW() - INTERVAL '1 day' * %s
                    ORDER BY created_at ASC
                """,
                    (index_name, historical_days),
                )

                history = cursor.fetchall()

                if len(history) < 2:
                    return {
                        "status": "insufficient_data",
                        "index_name": index_name,
                        "message": "Not enough historical data for prediction",
                    }

                # Simple linear regression: size = a * days + b
                # Calculate growth rate
                sizes = [float(h["size_bytes"] or 0) for h in history]
                days = [(h["created_at"] - history[0]["created_at"]).days for h in history]

                if len(set(days)) < 2:
                    # All data points at same time, use average growth
                    avg_growth = (sizes[-1] - sizes[0]) / max(1, len(sizes) - 1)
                else:
                    # Linear regression
                    n = len(days)
                    sum_x = sum(days)
                    sum_y = sum(sizes)
                    sum_xy = sum(d * s for d, s in zip(days, sizes))
                    sum_x2 = sum(d * d for d in days)

                    denominator = n * sum_x2 - sum_x * sum_x
                    if denominator == 0:
                        avg_growth = (sizes[-1] - sizes[0]) / max(1, len(sizes) - 1)
                    else:
                        slope = (n * sum_xy - sum_x * sum_y) / denominator
                        avg_growth = slope

                current_size = sizes[-1]
                predicted_size = current_size + (avg_growth * days_ahead)
                predicted_bloat_percent = (
                    ((predicted_size - current_size) / current_size * 100)
                    if current_size > 0
                    else 0
                )

                prediction = {
                    "status": "success",
                    "index_name": index_name,
                    "current_size_bytes": current_size,
                    "predicted_size_bytes": max(0, predicted_size),
                    "predicted_bloat_percent": predicted_bloat_percent,
                    "growth_rate_bytes_per_day": avg_growth,
                    "days_ahead": days_ahead,
                    "confidence": "medium" if len(history) >= 5 else "low",
                }

                # Store prediction
                with _prediction_lock:
                    _bloat_predictions[index_name] = prediction

                return prediction
            finally:
                cursor.close()
    except Exception as e:
        logger.error(f"Failed to predict bloat for {index_name}: {e}")
        return {"status": "error", "error": str(e)}


def predict_reindex_needs(
    bloat_threshold_percent: float = 20.0,
    prediction_days: int = 7,
) -> list[dict[str, Any]]:
    """
    Predict which indexes will need REINDEX in the near future.

    Args:
        bloat_threshold_percent: Bloat threshold to trigger REINDEX
        prediction_days: Days ahead to predict

    Returns:
        List of indexes predicted to need REINDEX
    """
    if not is_system_enabled():
        return []

    # Get current index health
    health_data = monitor_index_health(bloat_threshold_percent=bloat_threshold_percent)
    indexes = health_data.get("indexes", [])

    predicted_needs = []

    for idx in indexes:
        index_name = idx.get("index_name", "")
        if not index_name:
            continue

        # Predict future bloat
        prediction = predict_index_bloat(index_name, days_ahead=prediction_days)

        if prediction.get("status") == "success":
            predicted_bloat = prediction.get("predicted_bloat_percent", 0)
            current_bloat = idx.get("bloat_percent", 0)

            if (
                predicted_bloat >= bloat_threshold_percent
                or current_bloat >= bloat_threshold_percent
            ):
                predicted_needs.append(
                    {
                        "index_name": index_name,
                        "table_name": idx.get("table_name", ""),
                        "current_bloat_percent": current_bloat,
                        "predicted_bloat_percent": predicted_bloat,
                        "predicted_size_bytes": prediction.get("predicted_size_bytes", 0),
                        "recommended_action": "REINDEX",
                        "confidence": prediction.get("confidence", "low"),
                    }
                )

    return predicted_needs


def create_ab_experiment(
    experiment_name: str,
    table_name: str,
    variant_a: dict[str, Any],
    variant_b: dict[str, Any],
    traffic_split: float = 0.5,
) -> dict[str, Any]:
    """
    Create an A/B test experiment for different index strategies.

    Args:
        experiment_name: Name of the experiment
        table_name: Table to test on
        variant_a: Index strategy A (e.g., {"type": "btree", "columns": ["field1"]})
        variant_b: Index strategy B (e.g., {"type": "hash", "columns": ["field1"]})
        traffic_split: Percentage of traffic for variant A (0.0-1.0)

    Returns:
        Experiment configuration
    """
    if not is_system_enabled():
        return {"status": "disabled"}

    experiment = {
        "experiment_name": experiment_name,
        "table_name": table_name,
        "variant_a": variant_a,
        "variant_b": variant_b,
        "traffic_split": traffic_split,
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "results": {"variant_a": {}, "variant_b": {}},
    }

    with _ab_lock:
        _ab_experiments[experiment_name] = experiment

    logger.info(f"Created A/B experiment: {experiment_name}")
    return experiment


def get_ab_experiment(experiment_name: str) -> dict[str, Any] | None:
    """Get A/B experiment configuration."""
    with _ab_lock:
        return _ab_experiments.get(experiment_name)


def record_ab_result(
    experiment_name: str,
    variant: str,
    query_duration_ms: float,
    query_type: str = "unknown",
) -> None:
    """
    Record a query result for an A/B experiment.

    Args:
        experiment_name: Name of the experiment
        variant: "a" or "b"
        query_duration_ms: Query duration in milliseconds
        query_type: Type of query
    """
    with _ab_lock:
        if experiment_name not in _ab_experiments:
            return

        experiment = _ab_experiments[experiment_name]
        variant_key = f"variant_{variant}"

        if variant_key not in experiment["results"]:
            experiment["results"][variant_key] = {
                "query_count": 0,
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
                "query_types": defaultdict(int),
            }

        results = experiment["results"][variant_key]
        results["query_count"] += 1
        results["total_duration_ms"] += query_duration_ms
        results["avg_duration_ms"] = results["total_duration_ms"] / results["query_count"]
        results["query_types"][query_type] += 1


def get_ab_results(experiment_name: str) -> dict[str, Any] | None:
    """
    Get A/B experiment results and determine winner.

    Returns:
        Results with winner determination
    """
    with _ab_lock:
        if experiment_name not in _ab_experiments:
            return None

        experiment = _ab_experiments[experiment_name]
        results_a = experiment["results"].get("variant_a", {})
        results_b = experiment["results"].get("variant_b", {})

        avg_a = results_a.get("avg_duration_ms", 0.0)
        avg_b = results_b.get("avg_duration_ms", 0.0)
        count_a = results_a.get("query_count", 0)
        count_b = results_b.get("query_count", 0)

        # Determine winner (lower average duration wins)
        winner = None
        improvement_pct = 0.0

        if count_a > 0 and count_b > 0:
            if avg_a < avg_b:
                winner = "a"
                improvement_pct = ((avg_b - avg_a) / avg_b * 100) if avg_b > 0 else 0
            elif avg_b < avg_a:
                winner = "b"
                improvement_pct = ((avg_a - avg_b) / avg_a * 100) if avg_a > 0 else 0

        return {
            "experiment_name": experiment_name,
            "status": experiment.get("status", "active"),
            "variant_a": {
                "avg_duration_ms": avg_a,
                "query_count": count_a,
                "query_types": dict(results_a.get("query_types", {})),
            },
            "variant_b": {
                "avg_duration_ms": avg_b,
                "query_count": count_b,
                "query_types": dict(results_b.get("query_types", {})),
            },
            "winner": winner,
            "improvement_pct": improvement_pct,
            "statistical_significance": "low" if (count_a < 100 or count_b < 100) else "medium",
        }


def run_predictive_maintenance(
    bloat_threshold_percent: float = 20.0,
    prediction_days: int = 7,
) -> dict[str, Any]:
    """
    Run predictive maintenance: predict which indexes will need attention.

    Args:
        bloat_threshold_percent: Bloat threshold
        prediction_days: Days ahead to predict

    Returns:
        Predictive maintenance report
    """
    if not is_system_enabled():
        return {"status": "disabled"}

    logger.info("Running predictive maintenance...")

    # Predict REINDEX needs
    predicted_needs = predict_reindex_needs(
        bloat_threshold_percent=bloat_threshold_percent,
        prediction_days=prediction_days,
    )

    # Get current health
    health_data = monitor_index_health(bloat_threshold_percent=bloat_threshold_percent)
    summary = health_data.get("summary", {})

    report = {
        "timestamp": datetime.now().isoformat(),
        "current_health": summary,
        "predicted_reindex_needs": predicted_needs,
        "prediction_days": prediction_days,
        "recommendations": [],
    }

    # Generate recommendations
    if predicted_needs:
        report["recommendations"].append(
            {
                "action": "schedule_reindex",
                "count": len(predicted_needs),
                "indexes": [n["index_name"] for n in predicted_needs],
                "priority": "high" if len(predicted_needs) > 5 else "medium",
            }
        )

    monitoring = get_monitoring()
    if predicted_needs:
        monitoring.alert(
            "info",
            f"Predictive maintenance: {len(predicted_needs)} indexes predicted to need REINDEX",
        )

    logger.info(f"Predictive maintenance complete: {len(predicted_needs)} indexes need attention")
    return report
