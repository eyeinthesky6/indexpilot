"""Tests for the conservative redundant-index compatibility wrapper."""

from unittest.mock import patch

from src.redundant_index_detection import (
    find_redundant_indexes,
    is_redundant_index_detection_enabled,
    suggest_index_consolidation,
)


def test_is_redundant_index_detection_enabled():
    """Test redundant index detection enabled check"""
    assert is_redundant_index_detection_enabled() in [True, False]


@patch("src.redundant_index_detection.build_index_sprawl_report")
def test_find_redundant_indexes_is_manual_review_only(mock_report):
    mock_report.return_value = {
        "findings": [
            {
                "type": "leading_prefix_overlap",
                "schema": "public",
                "table": "orders",
                "left": {"name": "orders_status_idx", "columns": ["status"]},
                "right": {
                    "name": "orders_status_created_idx",
                    "columns": ["status", "created_at"],
                },
                "constraint_protected": False,
            }
        ]
    }

    findings = find_redundant_indexes(schema_name="public")

    assert findings[0]["finding_type"] == "leading_prefix_overlap"
    assert findings[0]["is_redundant"] is False
    assert findings[0]["safe_to_drop"] is False


@patch("src.redundant_index_detection.find_redundant_indexes")
def test_suggest_index_consolidation(mock_find):
    mock_find.return_value = [
        {
            "table": "public.orders",
            "left_index": "orders_status_idx",
            "right_index": "orders_status_created_idx",
            "finding_type": "leading_prefix_overlap",
            "reason": "manual review",
        }
    ]
    suggestions = suggest_index_consolidation(schema_name="public")

    assert suggestions[0]["action"] == "manual_review"
    assert suggestions[0]["safe_to_drop"] is False
    assert "drop_sql" not in suggestions[0]
