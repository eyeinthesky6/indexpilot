"""ML-based query interception using simple classification models"""

import hashlib
import logging
import threading
import time
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.query_interceptor import _analyze_query_complexity

logger = logging.getLogger(__name__)

# ML model storage (in-memory, could be persisted)
_ml_models: dict[str, Any] = {}
_model_lock = threading.Lock()

# Training data cache
_training_data: list[dict[str, Any]] = []
_training_lock = threading.Lock()

# Feature cache for queries
_query_features: dict[str, dict[str, Any]] = {}
_feature_cache_lock = threading.Lock()


class SimpleQueryClassifier:
    """
    Simple rule-based classifier that can be enhanced with ML models later.

    Uses weighted features to classify queries as safe/unsafe.
    """

    def __init__(self):
        self.feature_weights = {
            "complexity_score": 0.3,
            "join_count": 0.15,
            "subquery_depth": 0.15,
            "has_limit": -0.1,  # Negative = good
            "has_where": -0.1,
            "estimated_cost": 0.2,
            "table_size_factor": 0.1,
        }
        self.threshold = 0.5  # Above this = block

    def extract_features(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Extract features from a query for classification."""
        complexity = _analyze_query_complexity(query)

        # Normalize features to 0-1 range
        features = {
            "complexity_score": min(1.0, complexity.get("complexity_score", 0) / 100.0),
            "join_count": min(1.0, complexity.get("join_count", 0) / 10.0),
            "subquery_depth": min(1.0, complexity.get("subquery_depth", 0) / 5.0),
            "has_limit": 1.0 if "LIMIT" in query.upper() else 0.0,
            "has_where": 1.0 if "WHERE" in query.upper() else 0.0,
            "estimated_cost": 0.0,  # Will be filled by EXPLAIN if available
            "table_size_factor": 0.0,  # Will be filled by table stats if available
        }

        return features

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Predict if query should be blocked.

        Returns:
            dict with prediction and confidence
        """
        # Weighted sum of features
        score = 0.0
        for feature, value in features.items():
            weight = self.feature_weights.get(feature, 0.0)
            score += weight * value

        # Normalize to 0-1
        normalized_score = min(1.0, max(0.0, (score + 1.0) / 2.0))

        should_block = normalized_score >= self.threshold
        confidence = abs(normalized_score - self.threshold) * 2  # Higher = more confident

        return {
            "should_block": should_block,
            "risk_score": normalized_score,
            "confidence": confidence,
            "features": features,
        }

    def update_weights(self, feedback: list[dict[str, Any]]) -> None:
        """
        Update feature weights based on feedback (simple gradient descent).

        Args:
            feedback: List of {features, actual_blocked, predicted_blocked}
        """
        learning_rate = 0.01

        for item in feedback:
            features = item.get("features", {})
            actual = 1.0 if item.get("actual_blocked", False) else 0.0
            predicted = item.get("predicted_blocked", 0.0)

            error = actual - predicted

            # Update weights
            for feature, value in features.items():
                if feature in self.feature_weights:
                    self.feature_weights[feature] += learning_rate * error * value
                    # Clip weights to reasonable range
                    self.feature_weights[feature] = max(
                        -1.0, min(1.0, self.feature_weights[feature])
                    )


def train_classifier_from_history(
    time_window_hours: int = 24,
    min_samples: int = 50,
) -> dict[str, Any]:
    """
    Train classifier from query history.

    Args:
        time_window_hours: Time window to analyze
        min_samples: Minimum samples needed for training

    Returns:
        Training results
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get query history with performance data
                # Note: query_stats doesn't store query_text, only query_type
                # We'll use query_type to construct a representative query pattern
                cursor.execute(
                    """
                    SELECT
                        query_type,
                        duration_ms,
                        table_name,
                        field_name,
                        created_at
                    FROM query_stats
                    WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
                    ORDER BY created_at DESC
                    LIMIT 10000
                """,
                    (time_window_hours,),
                )

                queries = cursor.fetchall()

                if len(queries) < min_samples:
                    return {
                        "status": "insufficient_data",
                        "samples": len(queries),
                        "min_samples": min_samples,
                    }

                # Prepare training data
                training_samples = []
                slow_threshold_ms = 1000.0  # Queries slower than this are "bad"

                classifier = SimpleQueryClassifier()

                for query in queries:
                    # Construct a representative query pattern from query_type and table/field
                    query_type = query.get("query_type", "")
                    table_name = query.get("table_name", "")
                    field_name = query.get("field_name", "")
                    
                    # Build a representative query pattern for feature extraction
                    if query_type == "SELECT" and field_name:
                        query_text = f"SELECT * FROM {table_name} WHERE {field_name} = ?"
                    elif query_type == "SELECT":
                        query_text = f"SELECT * FROM {table_name}"
                    else:
                        query_text = f"{query_type} FROM {table_name}"
                    
                    duration_ms = float(query.get("duration_ms", 0.0))
                    is_slow = duration_ms >= slow_threshold_ms

                    # Extract features
                    features = classifier.extract_features(query_text)

                    training_samples.append(
                        {
                            "features": features,
                            "actual_blocked": is_slow,
                            "duration_ms": duration_ms,
                        }
                    )

                # Train classifier
                feedback = [
                    {
                        "features": s["features"],
                        "actual_blocked": s["actual_blocked"],
                        "predicted_blocked": classifier.predict(s["features"])["should_block"],
                    }
                    for s in training_samples
                ]

                classifier.update_weights(feedback)

                # Store model
                with _model_lock:
                    _ml_models["default_classifier"] = classifier

                # Calculate accuracy
                correct = 0
                for sample in training_samples:
                    prediction = classifier.predict(sample["features"])
                    if prediction["should_block"] == sample["actual_blocked"]:
                        correct += 1

                accuracy = correct / len(training_samples) if training_samples else 0.0

                logger.info(
                    f"Trained ML classifier: {len(training_samples)} samples, "
                    f"accuracy: {accuracy:.1%}"
                )

                return {
                    "status": "success",
                    "samples": len(training_samples),
                    "accuracy": accuracy,
                    "weights": classifier.feature_weights,
                }
            finally:
                cursor.close()
    except Exception as e:
        logger.error(f"Failed to train classifier: {e}")
        return {"status": "error", "error": str(e)}


def predict_query_risk_ml(
    query: str,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Predict query risk using ML model.

    Args:
        query: SQL query
        params: Query parameters
        use_cache: Use cached features if available

    Returns:
        Prediction with risk score and recommendation
    """
    # Check cache
    query_hash = hashlib.md5(query.encode()).hexdigest()
    if use_cache:
        with _feature_cache_lock:
            if query_hash in _query_features:
                cached = _query_features[query_hash]
                # Use cached features if recent (< 1 hour)
                if time.time() - cached.get("timestamp", 0) < 3600:
                    features = cached["features"]
                else:
                    features = None
            else:
                features = None
    else:
        features = None

    # Extract features if not cached
    if features is None:
        classifier = SimpleQueryClassifier()
        features = classifier.extract_features(query, params)

        # Cache features
        with _feature_cache_lock:
            _query_features[query_hash] = {
                "features": features,
                "timestamp": time.time(),
            }

    # Get classifier
    with _model_lock:
        ml_classifier: SimpleQueryClassifier | None = _ml_models.get("default_classifier")
        if ml_classifier is None:
            # Use default classifier if no trained model
            ml_classifier = SimpleQueryClassifier()

    # Predict
    prediction = ml_classifier.predict(features)

    return {
        "should_block": prediction["should_block"],
        "risk_score": prediction["risk_score"],
        "confidence": prediction["confidence"],
        "method": "ml" if _ml_models.get("default_classifier") else "default",
        "features": features,
    }


def get_ml_model_status() -> dict[str, Any]:
    """Get status of ML models."""
    with _model_lock:
        has_model = "default_classifier" in _ml_models
        model_info = {}

        if has_model:
            classifier = _ml_models["default_classifier"]
            model_info = {
                "type": "SimpleQueryClassifier",
                "weights": classifier.feature_weights,
                "threshold": classifier.threshold,
            }

        return {
            "has_model": has_model,
            "model_info": model_info,
            "cached_features": len(_query_features),
        }
