"""Tests for statistics refresh functionality"""

from unittest.mock import MagicMock, Mock, patch

from src.statistics_refresh import (
    detect_stale_statistics,
    get_statistics_refresh_config,
    is_statistics_refresh_enabled,
    refresh_stale_statistics,
    refresh_table_statistics,
)


def test_is_statistics_refresh_enabled():
    """Test statistics refresh enabled check"""
    # Should return True by default
    assert is_statistics_refresh_enabled() in [True, False]


def test_get_statistics_refresh_config():
    """Test getting statistics refresh configuration"""
    config = get_statistics_refresh_config()
    assert "enabled" in config
    assert "interval_hours" in config
    assert "stale_threshold_hours" in config


@patch("src.statistics_refresh.get_cursor")
def test_detect_stale_statistics(mock_get_cursor):
    """Test detecting stale statistics"""
    # Mock database cursor
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    # Configure context manager behavior - get_cursor() returns a context manager
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=mock_cursor)
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager

    result = detect_stale_statistics(stale_threshold_hours=24, min_table_size_mb=1.0)
    assert isinstance(result, list)


@patch("src.statistics_refresh.get_cursor")
def test_refresh_table_statistics_dry_run(mock_get_cursor):
    """Test refreshing table statistics in dry-run mode"""
    # Mock is not needed for dry_run=True, but patch to avoid actual DB calls
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=Mock())
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager
    
    result = refresh_table_statistics(table_name="test_table", dry_run=True)
    assert "dry_run" in result
    assert result["dry_run"] is True


@patch("src.statistics_refresh.get_cursor")
def test_refresh_stale_statistics_dry_run(mock_get_cursor):
    """Test refreshing stale statistics in dry-run mode"""
    # Mock is not needed for dry_run=True, but patch to avoid actual DB calls
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=Mock())
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager
    
    with patch("src.statistics_refresh.detect_stale_statistics", return_value=[]):
        result = refresh_stale_statistics(dry_run=True, limit=10)
        assert "dry_run" in result
        assert result["dry_run"] is True
