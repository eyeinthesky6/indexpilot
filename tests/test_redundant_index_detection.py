"""Tests for redundant index detection"""

from unittest.mock import MagicMock, Mock, patch

from src.redundant_index_detection import (
    find_redundant_indexes,
    is_redundant_index_detection_enabled,
    suggest_index_consolidation,
)


def test_is_redundant_index_detection_enabled():
    """Test redundant index detection enabled check"""
    assert is_redundant_index_detection_enabled() in [True, False]


@patch("src.redundant_index_detection.get_cursor")
def test_find_redundant_indexes(mock_get_cursor):
    """Test finding redundant indexes"""
    # Mock database cursor
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    # Configure context manager behavior - get_cursor() returns a context manager
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=mock_cursor)
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager

    result = find_redundant_indexes(schema_name="public")
    assert isinstance(result, list)


@patch("src.redundant_index_detection.find_redundant_indexes")
def test_suggest_index_consolidation(mock_find):
    """Test suggesting index consolidation"""
    mock_find.return_value = []
    result = suggest_index_consolidation(schema_name="public")
    assert isinstance(result, list)
