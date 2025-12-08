"""Tests for XGBoost pattern classification integration"""


from src.algorithms.xgboost_classifier import (
    classify_pattern,
    get_xgboost_config,
    is_xgboost_enabled,
    score_recommendation,
)


def test_xgboost_config():
    """Test XGBoost configuration loading"""
    config = get_xgboost_config()
    assert "enabled" in config
    assert "weight" in config
    assert "min_samples_for_training" in config


def test_xgboost_classify_pattern_basic():
    """Test basic pattern classification"""
    result = classify_pattern(
        table_name="test_table",
        field_name="test_field",
        query_type="SELECT",
        duration_ms=100.0,
        occurrence_count=10,
    )

    assert "classification_score" in result
    assert "confidence" in result
    assert "method" in result
    assert 0.0 <= result["classification_score"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0


def test_xgboost_classify_pattern_without_model():
    """Test pattern classification when model is not trained"""
    # Should return fallback result
    result = classify_pattern(
        table_name="test_table",
        field_name="test_field",
        query_type="SELECT",
    )

    assert result["method"] in [
        "xgboost",
        "fallback",
        "model_unavailable",
        "disabled",
        "library_unavailable",
    ]
    assert "classification_score" in result


def test_xgboost_score_recommendation():
    """Test recommendation scoring"""
    score = score_recommendation(
        table_name="test_table",
        field_name="test_field",
        query_type="SELECT",
        duration_ms=100.0,
        occurrence_count=10,
    )

    assert 0.0 <= score <= 1.0


def test_xgboost_is_enabled():
    """Test XGBoost enabled check"""
    # Should return boolean (may be False if xgboost not installed)
    enabled = is_xgboost_enabled()
    assert isinstance(enabled, bool)


def test_xgboost_classify_with_all_features():
    """Test classification with all features"""
    result = classify_pattern(
        table_name="test_table",
        field_name="test_field",
        query_type="SELECT",
        duration_ms=100.0,
        occurrence_count=10,
        avg_duration_ms=95.0,
        p95_duration_ms=150.0,
        row_count=1000,
        selectivity=0.3,
    )

    assert "classification_score" in result
    assert "confidence" in result
    assert "method" in result


def test_xgboost_classify_without_field():
    """Test classification without field name"""
    result = classify_pattern(
        table_name="test_table",
        field_name=None,
        query_type="SELECT",
    )

    assert "classification_score" in result
    assert result["method"] in [
        "xgboost",
        "fallback",
        "model_unavailable",
        "disabled",
        "library_unavailable",
    ]
