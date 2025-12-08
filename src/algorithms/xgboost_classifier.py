"""XGBoost Pattern Classification Algorithm Implementation

Based on "XGBoost: A Scalable Tree Boosting System"
arXiv:1603.02754

This module implements XGBoost for advanced pattern classification in query
pattern learning, helping to improve index recommendation accuracy by classifying
query patterns and scoring recommendations using machine learning.

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
import threading
from typing import Any

import numpy as np
from numpy.typing import NDArray

try:
    import xgboost as xgb  # type: ignore[import-not-found]

    XGBOOST_AVAILABLE = True
except ImportError:
    xgb = None  # type: ignore[assignment]
    XGBOOST_AVAILABLE = False

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection, safe_get_row_value

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Model storage (in-memory, could be persisted to DB)
# Type annotation: use Any to avoid issues when xgb is None (XGBoost not installed)
_model: Any | None = None

_model_lock = threading.Lock()
_model_trained = False
_model_version = 0
_model_training_timestamp: float | None = None


def is_xgboost_enabled() -> bool:
    """Check if XGBoost enhancement is enabled"""
    if not XGBOOST_AVAILABLE or xgb is None:
        return False
    return _config_loader.get_bool("features.xgboost.enabled", True)


def get_xgboost_config() -> dict[str, Any]:
    """Get XGBoost configuration"""
    return {
        "enabled": is_xgboost_enabled(),
        "weight": _config_loader.get_float("features.xgboost.weight", 0.4),
        "min_samples_for_training": _config_loader.get_int(
            "features.xgboost.min_samples_for_training", 50
        ),
        "retrain_interval_hours": _config_loader.get_int(
            "features.xgboost.retrain_interval_hours", 24
        ),
        "n_estimators": _config_loader.get_int("features.xgboost.n_estimators", 100),
        "max_depth": _config_loader.get_int("features.xgboost.max_depth", 6),
        "learning_rate": _config_loader.get_float("features.xgboost.learning_rate", 0.1),
    }


def _extract_features(
    table_name: str,
    field_name: str | None,
    query_type: str,
    duration_ms: float | None = None,
    occurrence_count: int | None = None,
    avg_duration_ms: float | None = None,
    p95_duration_ms: float | None = None,
    row_count: int | None = None,
    selectivity: float | None = None,
) -> NDArray[np.float32]:
    """
    Extract features for XGBoost classification.

    Args:
        table_name: Table name
        field_name: Field name (optional)
        query_type: Query type (SELECT, INSERT, etc.)
        duration_ms: Query duration in milliseconds
        occurrence_count: Number of occurrences
        avg_duration_ms: Average duration in milliseconds
        p95_duration_ms: 95th percentile duration
        row_count: Table row count
        selectivity: Field selectivity (0.0 to 1.0)

    Returns:
        numpy array of features
    """
    features: list[float] = []

    # Feature 1: Query type encoding (one-hot like)
    query_type_map = {"SELECT": 1.0, "INSERT": 2.0, "UPDATE": 3.0, "DELETE": 4.0}
    features.append(query_type_map.get(query_type, 0.0))

    # Feature 2: Has field name (1.0 if field_name exists, 0.0 otherwise)
    features.append(1.0 if field_name else 0.0)

    # Feature 3: Duration (normalized, log scale)
    if duration_ms is not None:
        features.append(np.log1p(duration_ms) / 10.0)  # Log scale, normalized
    else:
        features.append(0.0)

    # Feature 4: Occurrence count (normalized)
    if occurrence_count is not None:
        features.append(min(1.0, occurrence_count / 1000.0))  # Normalize to 0-1
    else:
        features.append(0.0)

    # Feature 5: Average duration (normalized, log scale)
    if avg_duration_ms is not None:
        features.append(np.log1p(avg_duration_ms) / 10.0)
    else:
        features.append(0.0)

    # Feature 6: P95 duration (normalized, log scale)
    if p95_duration_ms is not None:
        features.append(np.log1p(p95_duration_ms) / 10.0)
    else:
        features.append(0.0)

    # Feature 7: Row count (normalized, log scale)
    if row_count is not None:
        features.append(np.log1p(row_count) / 15.0)  # Log scale, normalized
    else:
        features.append(0.0)

    # Feature 8: Selectivity
    if selectivity is not None:
        features.append(selectivity)
    else:
        features.append(0.5)  # Default to medium selectivity

    # Feature 9: Table name hash (simple hash for categorical encoding)
    # Use first few characters to create a simple hash
    table_hash = hash(table_name) % 1000 / 1000.0
    features.append(table_hash)

    # Feature 10: Field name hash (if available)
    if field_name:
        field_hash = hash(field_name) % 1000 / 1000.0
        features.append(field_hash)
    else:
        features.append(0.0)

    return np.array(features, dtype=np.float32)


def _generate_dummy_training_data(
    num_samples: int = 100,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """
    Generate dummy training data for testing when database is unavailable.

    Args:
        num_samples: Number of samples to generate

    Returns:
        Tuple of (features, labels)
    """
    features_list: list[NDArray[np.float32]] = []
    labels_list: list[float] = []

    # Generate diverse dummy data
    query_types = ["SELECT", "INSERT", "UPDATE", "DELETE"]
    table_names = ["users", "orders", "products", "contacts", "orgs"]
    field_names = ["id", "name", "email", "created_at", "status"]

    for i in range(num_samples):
        table_name = table_names[i % len(table_names)]
        field_name = field_names[i % len(field_names)]
        query_type = query_types[i % len(query_types)]

        # Generate realistic dummy values
        duration_ms = 10.0 + (i % 1000) * 0.5  # 10-510ms
        occurrence_count = 1 + (i % 100)
        avg_duration_ms = duration_ms * 0.9
        p95_duration_ms = duration_ms * 1.2
        row_count = 1000 + (i % 10000) * 100
        selectivity = 0.1 + (i % 9) * 0.1  # 0.1-0.9

        features = _extract_features(
            table_name=table_name,
            field_name=field_name,
            query_type=query_type,
            duration_ms=duration_ms,
            occurrence_count=occurrence_count,
            avg_duration_ms=avg_duration_ms,
            p95_duration_ms=p95_duration_ms,
            row_count=row_count,
            selectivity=selectivity,
        )

        # Generate label: higher for slower queries (more benefit from indexing)
        label = min(1.0, max(0.0, np.log1p(avg_duration_ms) / 7.0))

        features_list.append(features)
        labels_list.append(label)

    X = np.vstack(features_list)
    y = np.array(labels_list, dtype=np.float32)

    logger.info(f"Generated {len(X)} dummy training samples for XGBoost")
    return X, y


def _load_training_data(
    min_samples: int = 50,
    use_dummy_on_failure: bool = True,
) -> tuple[NDArray[np.float32], NDArray[np.float32]] | None:
    """
    Load training data from query_stats and mutation_log.
    Falls back to dummy data if database is unavailable (useful for tests).

    Args:
        min_samples: Minimum number of samples required
        use_dummy_on_failure: If True, generate dummy data when DB fails

    Returns:
        Tuple of (features, labels) or None if insufficient data
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get query patterns with performance data
            query = """
                SELECT
                    qs.table_name,
                    qs.field_name,
                    qs.query_type,
                    qs.duration_ms,
                    COUNT(*) OVER (PARTITION BY qs.table_name, qs.field_name, qs.query_type) as occurrence_count,
                    AVG(qs.duration_ms) OVER (PARTITION BY qs.table_name, qs.field_name, qs.query_type) as avg_duration_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY qs.duration_ms)
                        OVER (PARTITION BY qs.table_name, qs.field_name, qs.query_type) as p95_duration_ms
                FROM query_stats qs
                WHERE qs.created_at >= NOW() - INTERVAL '7 days'
                ORDER BY qs.created_at DESC
                LIMIT 10000
            """

            cursor.execute(query)
            query_results = cursor.fetchall()

            if len(query_results) < min_samples:
                logger.debug(f"Insufficient training data: {len(query_results)} < {min_samples}")
                return None

            # Get table sizes for row_count feature
            table_sizes: dict[str, int] = {}
            cursor.execute(
                """
                SELECT schemaname, tablename, n_tup_ins + n_tup_upd as row_count
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            """
            )
            for row in cursor.fetchall():
                table_sizes[row["tablename"]] = row.get("row_count", 0) or 0

            # Get index outcomes from mutation_log (labels)
            index_outcomes: dict[str, float] = {}
            cursor.execute(
                """
                SELECT
                    table_name,
                    field_name,
                    CASE
                        WHEN details_json->>'improvement_pct' IS NOT NULL THEN
                            CAST(details_json->>'improvement_pct' AS FLOAT)
                        ELSE NULL
                    END as improvement_pct
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                    AND created_at >= NOW() - INTERVAL '30 days'
            """
            )
            for row in cursor.fetchall():
                table_name = row["table_name"]
                field_name = row.get("field_name", "")
                improvement = row.get("improvement_pct")
                if improvement is not None:
                    key = f"{table_name}:{field_name}"
                    # Store positive improvement as label
                    index_outcomes[key] = max(0.0, improvement / 100.0)  # Normalize to 0-1

            # Build features and labels
            features_list: list[NDArray[np.float32]] = []
            labels_list: list[float] = []

            for query_row in query_results:
                table_name = query_row["table_name"]
                field_name = query_row.get("field_name")
                query_type = query_row.get("query_type", "SELECT")
                duration_ms = query_row.get("duration_ms", 0) or 0
                occurrence_count = query_row.get("occurrence_count", 0) or 0
                avg_duration_ms = query_row.get("avg_duration_ms", 0) or 0
                p95_duration_ms = query_row.get("p95_duration_ms", 0) or 0
                row_count = table_sizes.get(table_name, 0)

                # Try to calculate selectivity from database (improved feature engineering)
                selectivity = None
                try:
                    if table_name and field_name:
                        # Use approximate selectivity from pg_stats if available
                        cursor.execute(
                            """
                            SELECT n_distinct
                            FROM pg_stats
                            WHERE schemaname = 'public'
                                AND tablename = %s
                                AND attname = %s
                        """,
                            (table_name, field_name),
                        )
                        result = cursor.fetchone()
                        n_distinct = safe_get_row_value(result, 0, None) or safe_get_row_value(result, "n_distinct", None)
                        if n_distinct is not None:
                            # Convert to selectivity (0.0-1.0)
                            # n_distinct can be negative (meaning -1 * selectivity), or positive
                            if isinstance(n_distinct, int | float) and n_distinct != 0:
                                if n_distinct < 0:
                                    # Negative means it's already a ratio
                                    selectivity = abs(n_distinct)
                                else:
                                    # Positive means distinct count
                                    selectivity = min(1.0, max(0.0, n_distinct / max(row_count, 1)))
                except Exception:
                    pass  # Selectivity calculation optional

                # Extract features
                features = _extract_features(
                    table_name=table_name,
                    field_name=field_name,
                    query_type=query_type,
                    duration_ms=duration_ms,
                    occurrence_count=occurrence_count,
                    avg_duration_ms=avg_duration_ms,
                    p95_duration_ms=p95_duration_ms,
                    row_count=row_count,
                    selectivity=selectivity,
                )

                # Get label (improvement if index was created, otherwise use duration-based)
                key = f"{table_name}:{field_name or '*'}"
                if key in index_outcomes:
                    label = index_outcomes[key]
                else:
                    # Use duration as proxy: slow queries = high value for indexing
                    # Normalize: 1000ms+ = 1.0, 100ms = 0.5, 10ms = 0.1
                    label = min(1.0, max(0.0, np.log1p(avg_duration_ms or duration_ms) / 7.0))

                features_list.append(features)
                labels_list.append(label)

            if len(features_list) < min_samples:
                logger.debug(
                    f"Insufficient samples after processing: {len(features_list)} < {min_samples}"
                )
                return None

            X = np.vstack(features_list)
            y = np.array(labels_list, dtype=np.float32)

            logger.info(f"Loaded {len(X)} training samples for XGBoost")
            return X, y

    except Exception as e:
        logger.warning(f"Failed to load training data from database: {e}")
        # Fall back to dummy data if enabled (useful for tests)
        if use_dummy_on_failure:
            logger.info("Using dummy training data as fallback")
            return _generate_dummy_training_data(num_samples=max(min_samples, 100))
        return None


def train_model(force_retrain: bool = False) -> bool:
    """
    Train XGBoost model on historical query patterns.

    Args:
        force_retrain: Force retraining even if model exists

    Returns:
        True if model was trained successfully, False otherwise
    """
    if not is_xgboost_enabled():
        return False

    if not XGBOOST_AVAILABLE or xgb is None:
        logger.warning("XGBoost library not available")
        return False

    config = get_xgboost_config()
    min_samples = config.get("min_samples_for_training", 50)

    global _model, _model_trained, _model_version, _model_training_timestamp
    with _model_lock:
        # Check if model needs retraining
        if _model_trained and not force_retrain:
            logger.debug("XGBoost model already trained, skipping")
            return True

        # Load training data
        training_data = _load_training_data(min_samples=min_samples)
        if training_data is None:
            logger.warning("Insufficient training data for XGBoost")
            return False

        X, y = training_data

        try:
            # Create and train XGBoost model
            # Following XGBoost paper (arXiv:1603.02754): gradient boosting with regularization
            model = xgb.XGBRegressor(
                n_estimators=config.get("n_estimators", 100),
                max_depth=config.get("max_depth", 6),
                learning_rate=config.get("learning_rate", 0.1),
                objective="reg:squarederror",  # Regression for utility prediction
                # Regularization (L1 and L2) as per XGBoost paper
                reg_alpha=0.1,  # L1 regularization (Lasso)
                reg_lambda=1.0,  # L2 regularization (Ridge)
                # Tree construction parameters
                min_child_weight=1,  # Minimum sum of instance weight needed in a child
                gamma=0.0,  # Minimum loss reduction required to make a split
                subsample=0.8,  # Subsample ratio of training instances
                colsample_bytree=0.8,  # Subsample ratio of columns when constructing each tree
                # Other parameters
                random_state=42,
                n_jobs=1,  # Single thread to avoid conflicts
            )

            # Train model
            model.fit(X, y)

            # Update model
            import time

            _model = model
            _model_trained = True
            _model_version += 1
            _model_training_timestamp = time.time()

            # Log feature importance (XGBoost paper emphasizes feature importance)
            try:
                feature_importance = model.feature_importances_
                # Feature names for reference
                feature_names = [
                    "query_type",
                    "has_field",
                    "duration",
                    "occurrence_count",
                    "avg_duration",
                    "p95_duration",
                    "row_count",
                    "selectivity",
                    "table_hash",
                    "field_hash",
                ]
                # Create importance dict
                importance_dict = {
                    name: float(imp)
                    for name, imp in zip(feature_names, feature_importance, strict=False)
                    if imp > 0.01  # Only log significant features
                }
                # Sort by importance
                sorted_importance = dict(
                    sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
                )
                logger.info(f"XGBoost top features: {sorted_importance}")
            except Exception:
                pass  # Feature importance not critical

            logger.info(f"XGBoost model trained successfully (version {_model_version})")
            return True

        except Exception as e:
            logger.error(f"Failed to train XGBoost model: {e}")
            return False


def classify_pattern(
    table_name: str,
    field_name: str | None = None,
    query_type: str = "SELECT",
    duration_ms: float | None = None,
    occurrence_count: int | None = None,
    avg_duration_ms: float | None = None,
    p95_duration_ms: float | None = None,
    row_count: int | None = None,
    selectivity: float | None = None,
) -> dict[str, Any]:
    """
    Classify query pattern using XGBoost model.

    Args:
        table_name: Table name
        field_name: Field name (optional)
        query_type: Query type (SELECT, INSERT, etc.)
        duration_ms: Query duration in milliseconds
        occurrence_count: Number of occurrences
        avg_duration_ms: Average duration in milliseconds
        p95_duration_ms: 95th percentile duration
        row_count: Table row count
        selectivity: Field selectivity (0.0 to 1.0)

    Returns:
        dict with:
            - classification_score: Predicted utility score (0.0 to 1.0)
            - confidence: Confidence in prediction (0.0 to 1.0)
            - method: Method used ("xgboost" or "fallback")
    """
    if not is_xgboost_enabled():
        return {
            "classification_score": 0.5,
            "confidence": 0.0,
            "method": "disabled",
        }

    if not XGBOOST_AVAILABLE or xgb is None:
        return {
            "classification_score": 0.5,
            "confidence": 0.0,
            "method": "library_unavailable",
        }

    with _model_lock:
        # Only use model if already trained - don't auto-train (can hang in tests)
        if not _model_trained or _model is None:
            return {
                "classification_score": 0.5,
                "confidence": 0.0,
                "method": "model_unavailable",
            }

        try:
            # Extract features
            features = _extract_features(
                table_name=table_name,
                field_name=field_name,
                query_type=query_type,
                duration_ms=duration_ms,
                occurrence_count=occurrence_count,
                avg_duration_ms=avg_duration_ms,
                p95_duration_ms=p95_duration_ms,
                row_count=row_count,
                selectivity=selectivity,
            )

            # Reshape for single prediction
            features_2d = features.reshape(1, -1)

            # Predict
            prediction = _model.predict(features_2d)[0]
            # XGBoost regression returns continuous value, clamp to 0-1
            classification_score = float(np.clip(prediction, 0.0, 1.0))

            # Confidence based on model certainty (for regression, use prediction variance)
            # For simplicity, use a fixed confidence based on model training status
            confidence = 0.7 if _model_trained else 0.3

            return {
                "classification_score": classification_score,
                "confidence": confidence,
                "method": "xgboost",
            }

        except Exception as e:
            logger.warning(f"XGBoost classification failed: {e}, using fallback")
            return {
                "classification_score": 0.5,
                "confidence": 0.0,
                "method": "fallback",
            }


def score_recommendation(
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
    Score index recommendation using XGBoost classification.

    Args:
        table_name: Table name
        field_name: Field name
        query_type: Query type
        duration_ms: Query duration
        occurrence_count: Number of occurrences
        avg_duration_ms: Average duration
        row_count: Table row count
        selectivity: Field selectivity

    Returns:
        Recommendation score (0.0 to 1.0)
    """
    result = classify_pattern(
        table_name=table_name,
        field_name=field_name,
        query_type=query_type,
        duration_ms=duration_ms,
        occurrence_count=occurrence_count,
        avg_duration_ms=avg_duration_ms,
        row_count=row_count,
        selectivity=selectivity,
    )

    config = get_xgboost_config()
    weight = config.get("weight", 0.4)

    # Combine XGBoost score with weight
    xgboost_score = result.get("classification_score", 0.5)
    xgboost_confidence = result.get("confidence", 0.0)

    # Weighted score: use XGBoost if confidence is high, otherwise fallback
    if xgboost_confidence > 0.5:
        score = xgboost_score * weight + 0.5 * (1.0 - weight)
        return float(score) if isinstance(score, int | float) else 0.5
    else:
        return 0.5  # Neutral score if model not confident


def get_model_status() -> dict[str, Any]:
    """
    Get XGBoost model status and metadata.

    Returns:
        dict with model status information
    """
    with _model_lock:
        status: dict[str, Any] = {
            "enabled": is_xgboost_enabled(),
            "library_available": xgb is not None,
            "model_trained": _model_trained,
            "model_version": _model_version,
            "model_available": _model is not None,
        }

        if _model_training_timestamp:
            import time

            status["last_training_timestamp"] = float(_model_training_timestamp)
            status["hours_since_training"] = (time.time() - _model_training_timestamp) / 3600.0

        if _model is not None:
            try:
                status["n_estimators"] = _model.n_estimators
                status["max_depth"] = _model.max_depth
                status["learning_rate"] = _model.learning_rate
            except Exception:
                pass

        return status
