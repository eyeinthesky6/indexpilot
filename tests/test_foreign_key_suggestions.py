"""Tests for foreign key index suggestions"""

from unittest.mock import Mock, patch

from src.foreign_key_suggestions import (
    analyze_join_patterns_for_fk,
    find_foreign_keys_without_indexes,
    is_foreign_key_suggestions_enabled,
    suggest_foreign_key_indexes,
)


def test_is_foreign_key_suggestions_enabled():
    """Test foreign key suggestions enabled check"""
    assert is_foreign_key_suggestions_enabled() in [True, False]


@patch("src.foreign_key_suggestions.get_connection")
def test_find_foreign_keys_without_indexes(mock_conn):
    """Test finding foreign keys without indexes"""
    # Mock database connection
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

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
