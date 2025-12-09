"""Tests for foreign key index suggestions"""

from unittest.mock import MagicMock, Mock, patch

from src.foreign_key_suggestions import (
    analyze_join_patterns_for_fk,
    find_foreign_keys_without_indexes,
    is_foreign_key_suggestions_enabled,
    suggest_foreign_key_indexes,
)


def test_is_foreign_key_suggestions_enabled():
    """Test foreign key suggestions enabled check"""
    assert is_foreign_key_suggestions_enabled() in [True, False]


@patch("src.foreign_key_suggestions.get_cursor")
def test_find_foreign_keys_without_indexes(mock_get_cursor):
    """Test finding foreign keys without indexes"""
    # Mock database cursor
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    # Configure context manager behavior - get_cursor() returns a context manager
    context_manager = MagicMock()
    context_manager.__enter__ = Mock(return_value=mock_cursor)
    context_manager.__exit__ = Mock(return_value=None)
    mock_get_cursor.return_value = context_manager

    result = find_foreign_keys_without_indexes(schema_name="public")
    assert isinstance(result, list)


@patch("src.foreign_key_suggestions.find_foreign_keys_without_indexes")
def test_suggest_foreign_key_indexes(mock_find):
    """Test suggesting foreign key indexes"""
    mock_find.return_value = []
    result = suggest_foreign_key_indexes(schema_name="public")
    assert isinstance(result, list)


@patch("src.foreign_key_suggestions.suggest_foreign_key_indexes")
def test_analyze_join_patterns_for_fk(mock_suggest):
    """Test analyzing join patterns for foreign keys"""
    mock_suggest.return_value = []
    result = analyze_join_patterns_for_fk(schema_name="public")
    assert isinstance(result, list)
