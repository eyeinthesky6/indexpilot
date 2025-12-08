"""Tests for workload analysis"""

from unittest.mock import Mock, patch

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


@patch("src.workload_analysis.get_connection")
def test_analyze_workload(mock_conn):
    """Test workload analysis"""
    # Mock database connection
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

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
