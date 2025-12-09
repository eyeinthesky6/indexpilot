"""Predictive Indexing Algorithm Implementation

Based on "Predictive Indexing for Fast Search"
arXiv:1901.07064

This module implements Predictive Indexing ML concepts for utility forecasting,
helping to improve index recommendation accuracy by predicting index utility
based on historical patterns and query characteristics.

Enhanced with actual ML model (scikit-learn) for accurate utility prediction.

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
import threading
from typing import Any

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # np is set to None when numpy is not available
    # This is handled at runtime with NUMPY_AVAILABLE checks
    np: Any = None  # type: ignore[assignment,unused-ignore]


try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    RandomForestRegressor: Any = None  # type: ignore[assignment,unused-ignore]
    StandardScaler: Any = None  # type: ignore[assignment,unused-ignore]

from src.config_loader import ConfigLoader
from src.db import get_cursor

logger = logging.getLogger(__name__)

# ML model storage (in-memory, could be persisted to DB)
_model: Any | None = None
_scaler: Any | None = None
_model_lock = threading.Lock()
_model_trained = False
_model_version = 0

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_predictive_indexing_enabled() -> bool:
    """Check if Predictive Indexing enhancement is enabled"""
    return _config_loader.get_bool("features.predictive_indexing.enabled", True)


def get_predictive_indexing_config() -> dict[str, Any]:
    """Get Predictive Indexing configuration"""
    return {
        "enabled": is_predictive_indexing_enabled(),
        "weight": _config_loader.get_float("features.predictive_indexing.weight", 0.3),
        "min_historical_samples": _config_loader.get_int(
            "features.predictive_indexing.min_historical_samples", 10
        ),
        "use_historical_data": _config_loader.get_bool(
            "features.predictive_indexing.use_historical_data", True
        ),
        "use_ml_model": _config_loader.get_bool("features.predictive_indexing.use_ml_model", True),
        "ml_min_samples": _config_loader.get_int("features.predictive_indexing.ml_min_samples", 50),
    }


def predict_index_utility(
    table_name: str,
    field_name: str,
    estimated_build_cost: float,
    queries_over_horizon: float,
    extra_cost_per_query_without_index: float,
    table_size_info: dict[str, Any] | None = None,
    field_selectivity: float | None = None,
) -> dict[str, Any]:
    """
    Predict index utility using Predictive Indexing ML concepts.

    Based on "Predictive Indexing for Fast Search" (arXiv:1901.07064),
    this function forecasts the utility of creating an index by analyzing:
    - Historical index performance (if available)
    - Query patterns and characteristics
    - Table and field properties
    - Cost-benefit ratios

    Args:
        table_name: Name of the table
        field_name: Name of the field to index
        estimated_build_cost: Estimated cost to build the index
        queries_over_horizon: Number of queries expected over time horizon
        extra_cost_per_query_without_index: Additional cost per query without index
        table_size_info: Optional dict with table size information
        field_selectivity: Optional field selectivity (0.0 to 1.0)

    Returns:
        dict with:
            - utility_score: Predicted utility (0.0 to 1.0)
            - confidence: Confidence in prediction (0.0 to 1.0)
            - method: Method used ("historical", "pattern_based", "heuristic_fallback")
            - factors: Dict of contributing factors
    """
    if not is_predictive_indexing_enabled():
        return {
            "utility_score": 0.5,
            "confidence": 0.0,
            "method": "disabled",
            "factors": {},
        }

    config = get_predictive_indexing_config()

    # Extract features for prediction
    # Convert to int for row_count (functions expect int)
    row_count_val = table_size_info.get("row_count", 0) if table_size_info else 0
    row_count = (
        int(row_count_val) if row_count_val and isinstance(row_count_val, int | float) else 0
    )
    index_overhead_percent_val = (
        table_size_info.get("index_overhead_percent", 0.0) if table_size_info else 0.0
    )
    index_overhead_percent = (
        float(index_overhead_percent_val) if index_overhead_percent_val else 0.0
    )
    selectivity = float(field_selectivity) if field_selectivity is not None else 0.5

    # Calculate base cost-benefit ratio
    total_query_cost = queries_over_horizon * extra_cost_per_query_without_index
    cost_benefit_ratio = (
        total_query_cost / estimated_build_cost if estimated_build_cost > 0 else 0.0
    )

    # Method 1: Use ML model if available and enabled
    config = get_predictive_indexing_config()
    if config.get("use_ml_model", True) and SKLEARN_AVAILABLE:
        # Train model if not trained
        if not _model_trained:
            _train_ml_model()

        # Try ML prediction
        ml_prediction = _predict_with_ml_model(
            cost_benefit_ratio,
            row_count,
            selectivity,
            queries_over_horizon,
            index_overhead_percent,
        )

        if ml_prediction.get("method") == "ml_model" and ml_prediction.get("confidence", 0) > 0.5:
            return ml_prediction

    # Method 2: Use historical data if available
    if config.get("use_historical_data", True):
        historical_prediction = _predict_from_historical_data(
            table_name, field_name, row_count, selectivity
        )
        if historical_prediction["confidence"] > 0.5:
            return historical_prediction

    # Method 3: Pattern-based prediction using query characteristics (fallback)
    pattern_prediction = _predict_from_patterns(
        table_name,
        field_name,
        cost_benefit_ratio,
        row_count,
        selectivity,
        queries_over_horizon,
        index_overhead_percent,
    )

    return pattern_prediction


def _extract_ml_features(
    cost_benefit_ratio: float,
    row_count: int,
    selectivity: float,
    queries_over_horizon: float,
    index_overhead_percent: float,
):
    """
    Extract features for ML model prediction.

    Args:
        cost_benefit_ratio: Cost-benefit ratio
        row_count: Table row count
        selectivity: Field selectivity
        queries_over_horizon: Number of queries
        index_overhead_percent: Index overhead percentage

    Returns:
        numpy array of features
    """
    if not NUMPY_AVAILABLE or np is None:
        return None

    features = [
        np.log1p(cost_benefit_ratio),  # Log scale for cost-benefit
        np.log1p(row_count) / 20.0,  # Normalized log of row count
        selectivity,  # Already 0-1
        np.log1p(queries_over_horizon) / 10.0,  # Normalized log of queries
        index_overhead_percent / 100.0,  # Normalize to 0-1
    ]
    return np.array(features, dtype=np.float32)


def _load_ml_training_data(min_samples: int = 50):
    """
    Load training data for ML model from historical index performance.

    Returns:
        Tuple of (features, labels) or None if insufficient data
    """
    try:
        with get_cursor() as cursor:
            # Get historical index performance data
            query = """
                SELECT
                    details_json->>'estimated_build_cost' as build_cost,
                    details_json->>'queries_over_horizon' as queries,
                    details_json->>'field_selectivity' as selectivity,
                    details_json->>'row_count' as row_count,
                    details_json->>'index_overhead_percent' as overhead,
                    details_json->>'improvement_pct' as improvement
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                    AND details_json->>'improvement_pct' IS NOT NULL
                    AND details_json->>'estimated_build_cost' IS NOT NULL
                    AND details_json->>'queries_over_horizon' IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1000
            """

            cursor.execute(query)
            results = cursor.fetchall()

            if len(results) < min_samples:
                return None

            features_list = []
            labels_list = []

            for row in results:
                try:
                    build_cost = float(row.get("build_cost", 0) or 0)
                    queries = float(row.get("queries", 0) or 0)
                    selectivity = float(row.get("selectivity", 0.5) or 0.5)
                    row_count = float(row.get("row_count", 0) or 0)
                    overhead = float(row.get("overhead", 0) or 0)
                    improvement = float(row.get("improvement", 0) or 0)

                    if build_cost <= 0 or queries <= 0:
                        continue

                    # Calculate cost-benefit ratio
                    extra_cost = build_cost / queries if queries > 0 else 0
                    cost_benefit = (queries * extra_cost) / build_cost if build_cost > 0 else 0

                    # Extract features (convert row_count to int)
                    row_count_int = int(row_count) if isinstance(row_count, int | float) else 0
                    features = _extract_ml_features(
                        cost_benefit, row_count_int, selectivity, queries, overhead
                    )

                    # Label: improvement percentage normalized to 0-1
                    label = min(1.0, max(0.0, improvement / 100.0))

                    features_list.append(features)
                    labels_list.append(label)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Skipping invalid training sample: {e}")
                    continue

            if len(features_list) < min_samples or not NUMPY_AVAILABLE or np is None:
                return None

            X = np.vstack(features_list)
            y = np.array(labels_list, dtype=np.float32)

            logger.info(f"Loaded {len(X)} training samples for Predictive Indexing ML model")
            return X, y

    except Exception as e:
        logger.warning(f"Failed to load ML training data: {e}")
        return None


def _train_ml_model(force_retrain: bool = False) -> bool:
    """
    Train ML model for utility prediction.

    Args:
        force_retrain: Force retraining even if model exists

    Returns:
        True if model was trained successfully
    """
    if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
        return False

    config = get_predictive_indexing_config()
    if not config.get("use_ml_model", True):
        return False

    min_samples = config.get("ml_min_samples", 50)

    global _model, _scaler, _model_trained, _model_version

    with _model_lock:
        if _model_trained and not force_retrain:
            return True

        training_data = _load_ml_training_data(min_samples=min_samples)
        if training_data is None:
            logger.debug("Insufficient training data for Predictive Indexing ML model")
            return False

        X, y = training_data

        try:
            # Scale features
            if StandardScaler is None or RandomForestRegressor is None:
                return False
            # Type narrowing: after None check, these are guaranteed to be classes
            # Use type: ignore for pyright since it doesn't understand the None check
            scaler_class = StandardScaler  # type: ignore[assignment]
            model_class = RandomForestRegressor  # type: ignore[assignment]
            _scaler = scaler_class()
            X_scaled = _scaler.fit_transform(X)  # type: ignore[union-attr]

            # Train Random Forest model (good for non-linear relationships)
            _model = model_class(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=1,
            )

            _model.fit(X_scaled, y)  # type: ignore[union-attr]

            _model_trained = True
            _model_version += 1

            logger.info(
                f"Predictive Indexing ML model trained successfully (version {_model_version})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to train Predictive Indexing ML model: {e}")
            return False


def _predict_with_ml_model(
    cost_benefit_ratio: float,
    row_count: int,
    selectivity: float,
    queries_over_horizon: float,
    index_overhead_percent: float,
) -> dict[str, Any]:
    """
    Predict utility using trained ML model.

    Args:
        cost_benefit_ratio: Cost-benefit ratio
        row_count: Table row count
        selectivity: Field selectivity
        queries_over_horizon: Number of queries
        index_overhead_percent: Index overhead percentage

    Returns:
        dict with prediction results
    """
    if (
        not SKLEARN_AVAILABLE
        or not NUMPY_AVAILABLE
        or not _model_trained
        or _model is None
        or _scaler is None
    ):
        return {
            "utility_score": 0.5,
            "confidence": 0.0,
            "method": "ml_unavailable",
        }

    try:
        # Extract features
        features = _extract_ml_features(
            cost_benefit_ratio, row_count, selectivity, queries_over_horizon, index_overhead_percent
        )
        if features is None or _scaler is None or _model is None or np is None:
            return {
                "utility_score": 0.5,
                "confidence": 0.0,
                "method": "ml_model_unavailable",
                "factors": {},
            }

        # Scale features
        features_scaled = _scaler.transform(features.reshape(1, -1))

        # Predict
        prediction = _model.predict(features_scaled)[0]

        # Clamp to 0-1 range
        utility_score = float(max(0.0, min(1.0, prediction)))

        # Confidence based on model training status
        confidence = 0.8 if _model_trained else 0.3

        return {
            "utility_score": utility_score,
            "confidence": confidence,
            "method": "ml_model",
        }
    except Exception as e:
        logger.warning(f"ML model prediction failed: {e}")
        return {
            "utility_score": 0.5,
            "confidence": 0.0,
            "method": "ml_error",
        }


def _predict_from_historical_data(
    table_name: str, field_name: str, row_count: int, selectivity: float
) -> dict[str, Any]:
    """
    Predict utility from historical index performance data.

    Analyzes past index creations and their outcomes to predict future utility.
    """
    config = get_predictive_indexing_config()
    min_samples = config.get("min_historical_samples", 10)

    try:
        with get_cursor() as cursor:
            # Query historical index performance from mutation_log
            # Look for similar indexes (same table/field pattern) and their outcomes
            historical_query = """
                SELECT
                    details_json->>'improvement_pct' as improvement_pct,
                    details_json->>'query_cost_before' as cost_before,
                    details_json->>'query_cost_after' as cost_after,
                    created_at
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                    AND table_name = %s
                    AND field_name = %s
                    AND details_json->>'improvement_pct' IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
            """

            cursor.execute(historical_query, [table_name, field_name])
            results = cursor.fetchall()

            # Use safe access to prevent tuple index errors

            if len(results) >= min_samples:
                # Calculate average improvement
                improvements = []
                for row in results:
                    improvement_str = row.get("improvement_pct")
                    if improvement_str:
                        try:
                            improvement = float(improvement_str)
                            if improvement > 0:
                                improvements.append(improvement)
                        except (ValueError, TypeError):
                            continue

                if improvements:
                    avg_improvement = sum(improvements) / len(improvements)
                    # Convert improvement percentage to utility score (0.0 to 1.0)
                    # 20% improvement = 0.5 utility, 50%+ = 1.0 utility
                    utility_score = min(1.0, max(0.0, avg_improvement / 50.0))
                    confidence = min(
                        1.0, len(improvements) / 50.0
                    )  # More samples = higher confidence

                    return {
                        "utility_score": utility_score,
                        "confidence": confidence,
                        "method": "historical",
                        "factors": {
                            "avg_improvement_pct": avg_improvement,
                            "sample_count": len(improvements),
                            "historical_data_available": True,
                        },
                    }

    except Exception as e:
        logger.debug(f"Could not use historical data for prediction: {e}")

    return {
        "utility_score": 0.5,
        "confidence": 0.0,
        "method": "historical_unavailable",
        "factors": {},
    }


def _predict_from_patterns(
    table_name: str,
    field_name: str,
    cost_benefit_ratio: float,
    row_count: int,
    selectivity: float,
    queries_over_horizon: float,
    index_overhead_percent: float,
) -> dict[str, Any]:
    """
    Predict utility from query patterns and characteristics.

    Uses pattern-based heuristics inspired by Predictive Indexing concepts
    to forecast index utility without requiring historical data.
    """
    factors: dict[str, Any] = {}

    # Factor 1: Cost-benefit ratio (higher = better utility)
    cost_benefit_score = min(1.0, cost_benefit_ratio / 2.0)  # 2x benefit = full score
    factors["cost_benefit_score"] = cost_benefit_score

    # Factor 2: Query volume (more queries = higher utility)
    # Normalize: 1000 queries = 0.5, 5000+ = 1.0
    query_volume_score = min(1.0, queries_over_horizon / 5000.0)
    factors["query_volume_score"] = query_volume_score

    # Factor 3: Selectivity (moderate selectivity = best utility)
    # Very low selectivity (boolean flags) = low utility
    # Very high selectivity (unique) = good utility
    # Moderate (0.1-0.5) = excellent utility
    if selectivity < 0.01:
        selectivity_score = 0.2  # Very low selectivity (boolean-like)
    elif selectivity < 0.1:
        selectivity_score = 0.9  # Excellent selectivity range
    elif selectivity < 0.5:
        selectivity_score = 0.8  # Good selectivity range
    else:
        selectivity_score = 0.6  # High selectivity (still useful)
    factors["selectivity_score"] = selectivity_score

    # Factor 4: Table size (larger tables benefit more from indexes)
    # Small tables (<1K) = 0.3, Medium (1K-10K) = 0.6, Large (>10K) = 1.0
    if row_count < 1000:
        table_size_score = 0.3
    elif row_count < 10000:
        table_size_score = 0.6
    else:
        table_size_score = 1.0
    factors["table_size_score"] = table_size_score

    # Factor 5: Index overhead (lower overhead = better utility)
    # 0% overhead = 1.0, 50%+ overhead = 0.3
    overhead_score = max(0.3, 1.0 - (index_overhead_percent / 50.0))
    factors["overhead_score"] = overhead_score

    # Weighted combination of factors
    weights = {
        "cost_benefit": 0.35,
        "query_volume": 0.25,
        "selectivity": 0.20,
        "table_size": 0.10,
        "overhead": 0.10,
    }

    utility_score = (
        cost_benefit_score * weights["cost_benefit"]
        + query_volume_score * weights["query_volume"]
        + selectivity_score * weights["selectivity"]
        + table_size_score * weights["table_size"]
        + overhead_score * weights["overhead"]
    )

    # Confidence based on data quality
    # Higher confidence if we have good selectivity and query volume data
    confidence = min(1.0, (selectivity_score + query_volume_score) / 2.0)

    return {
        "utility_score": utility_score,
        "confidence": confidence,
        "method": "pattern_based",
        "factors": factors,
    }


def refine_heuristic_decision(
    heuristic_decision: bool,
    heuristic_confidence: float,
    utility_prediction: dict[str, Any],
) -> tuple[bool, float, str]:
    """
    Refine heuristic decision using Predictive Indexing utility prediction.

    Combines heuristic cost-benefit analysis with ML-based utility prediction
    for more accurate index recommendations.

    Args:
        heuristic_decision: Heuristic decision (True/False)
        heuristic_confidence: Heuristic confidence (0.0 to 1.0)
        utility_prediction: Utility prediction from predict_index_utility()

    Returns:
        Tuple of (refined_decision: bool, refined_confidence: float, reason: str)
    """
    if not is_predictive_indexing_enabled():
        return heuristic_decision, heuristic_confidence, "predictive_indexing_disabled"

    config = get_predictive_indexing_config()
    ml_weight = config.get("weight", 0.3)
    heuristic_weight = 1.0 - ml_weight

    utility_score = utility_prediction.get("utility_score", 0.5)
    ml_confidence = utility_prediction.get("confidence", 0.5)
    method = utility_prediction.get("method", "pattern_based")

    # Combine heuristic and ML predictions
    # Heuristic decision: 1.0 if True, 0.0 if False
    heuristic_score = 1.0 if heuristic_decision else 0.0

    # Combined score
    combined_score = (heuristic_score * heuristic_weight) + (utility_score * ml_weight)

    # Refined decision: True if combined score > 0.5
    refined_decision = combined_score > 0.5

    # Refined confidence: Weighted average of heuristic and ML confidence
    refined_confidence = (heuristic_confidence * heuristic_weight) + (ml_confidence * ml_weight)

    # Determine reason
    if refined_decision != heuristic_decision:
        if refined_decision:
            reason = f"ml_override_positive_{method}"
        else:
            reason = f"ml_override_negative_{method}"
    else:
        if heuristic_decision:
            reason = f"heuristic_ml_agree_positive_{method}"
        else:
            reason = f"heuristic_ml_agree_negative_{method}"

    return refined_decision, refined_confidence, reason
