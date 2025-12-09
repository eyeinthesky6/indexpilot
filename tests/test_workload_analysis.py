"""Tests for workload analysis"""

from unittest.mock import MagicMock, Mock, patch

from src.workload_analysis import (
    analyze_workload,
    get_workload_config,
    get_workload_recommendation,
    is_workload_analysis_enabled,
)


def test_is_workload_analysis_enabled():
    """Test workload analysis enabled check"""
    assert is_workload_analysis_enabled() in [True, False]


def test_get_workload_config():
    """Test getting workload configuration"""
    config = get_workload_config()
    assert "enabled" in config
    assert "time_window_hours" in config
    assert "read_heavy_threshold" in config


@patch("src.workload_analysis.get_cursor")
def test_analyze_workload(mock_get_cursor):
    """Test workload analysis"""
    # Mock database cursor
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    # Configure context manager behavior - get_cursor() returns a context manager
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=mock_cursor)
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager

    result = analyze_workload(time_window_hours=24)
    assert "timestamp" in result or "skipped" in result
    assert "tables" in result or "skipped" in result


def test_get_workload_recommendation():
    """Test getting workload recommendation"""
    workload_data = {
        "tables": [
            {
                "table_name": "test_table",
                "read_ratio": 0.8,
                "workload_type": "read_heavy",
            }
        ],
    }

    result = get_workload_recommendation("test_table", workload_data)
    assert "recommendation" in result
    assert result["recommendation"] in ["aggressive", "conservative", "balanced", "unknown"]
