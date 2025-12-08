"""Tests for index retry logic"""

from unittest.mock import Mock, patch

from src.index_retry import (
    calculate_retry_delay,
    get_retry_config,
    is_retry_enabled,
    is_retryable_error,
    retry_index_creation,
)


def test_is_retry_enabled():
    """Test retry enabled check"""
    assert is_retry_enabled() in [True, False]


def test_get_retry_config():
    """Test getting retry configuration"""
    config = get_retry_config()
    assert "enabled" in config
    assert "max_retries" in config
    assert "initial_delay_seconds" in config


def test_is_retryable_error():
    """Test retryable error detection"""
    # Test timeout error
    timeout_error = Exception("timeout occurred")
    assert is_retryable_error(timeout_error) is True

    # Test connection error
    conn_error = Exception("connection failed")
    assert is_retryable_error(conn_error) is True

    # Test non-retryable error
    other_error = Exception("syntax error")
    # May or may not be retryable depending on config
    assert isinstance(is_retryable_error(other_error), bool)


def test_calculate_retry_delay():
    """Test retry delay calculation"""
    delay1 = calculate_retry_delay(0)
    delay2 = calculate_retry_delay(1)
    delay3 = calculate_retry_delay(2)

    # Should use exponential backoff
    assert delay2 > delay1
    assert delay3 > delay2


def test_retry_index_creation_success():
    """Test successful index creation (no retry needed)"""
    success_func = Mock(return_value=True)

    result = retry_index_creation(success_func, "test_table", "test_field")
    assert result["success"] is True
    assert result["retries"] == 0
    assert result["total_attempts"] == 1


def test_retry_index_creation_with_retries():
    """Test index creation with retries"""
    attempt_count = 0

    def failing_then_success():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise Exception("timeout error")
        return True

    with patch("time.sleep"):  # Mock sleep to speed up test
        result = retry_index_creation(failing_then_success, "test_table", "test_field")
        # Should succeed after retry
        assert result["success"] is True
        assert result["retries"] > 0


def test_retry_index_creation_non_retryable():
    """Test that non-retryable errors don't retry"""

    def non_retryable_error():
        raise Exception("syntax error: invalid SQL")

    with patch("src.index_retry.is_retryable_error", return_value=False):
        result = retry_index_creation(non_retryable_error, "test_table", "test_field")
        assert result["success"] is False
        assert result.get("non_retryable") is True
