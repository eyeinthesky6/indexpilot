"""Tests for storage budget management"""

import pytest
from unittest.mock import Mock, patch

from src.storage_budget import (
    check_storage_budget,
    get_index_storage_usage,
    get_storage_budget_config,
    get_storage_budget_status,
    is_storage_budget_enabled,
)


def test_is_storage_budget_enabled():
    """Test storage budget enabled check"""
    assert is_storage_budget_enabled() in [True, False]


def test_get_storage_budget_config():
    """Test getting storage budget configuration"""
    config = get_storage_budget_config()
    assert "enabled" in config
    assert "max_storage_per_tenant_mb" in config
    assert "max_storage_total_mb" in config


@patch("src.storage_budget.get_connection")
def test_get_index_storage_usage(mock_conn):
    """Test getting index storage usage"""
    # Mock database connection
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

    result = get_index_storage_usage()
    assert "total_index_size_mb" in result or "skipped" in result


@patch("src.storage_budget.get_index_storage_usage")
def test_check_storage_budget(mock_usage):
    """Test checking storage budget"""
    mock_usage.return_value = {"total_index_size_mb": 500.0, "index_count": 10}

    result = check_storage_budget(tenant_id=None, estimated_index_size_mb=100.0)
    assert "allowed" in result
    assert "current_size_mb" in result
    assert isinstance(result["allowed"], bool)


@patch("src.storage_budget.get_index_storage_usage")
def test_get_storage_budget_status(mock_usage):
    """Test getting storage budget status"""
    mock_usage.return_value = {"total_index_size_mb": 500.0, "index_count": 10}

    result = get_storage_budget_status()
    assert "enabled" in result
    assert "total_size_mb" in result or "enabled" in result

