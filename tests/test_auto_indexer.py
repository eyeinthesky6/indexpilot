"""Tests for auto-indexer decision logic"""

import pytest

from src.auto_indexer import (
    estimate_build_cost,
    estimate_query_cost_without_index,
    should_create_index,
)


def test_should_create_index_positive():
    """Test that index should be created when cost-benefit is favorable"""
    # High query volume, low build cost, high query cost without index
    should_create, confidence, reason = should_create_index(
        estimated_build_cost=10.0, queries_over_horizon=1000, extra_cost_per_query_without_index=0.1
    )
    assert should_create is True


def test_should_create_index_negative():
    """Test that index should NOT be created when cost-benefit is unfavorable"""
    # Low query volume, high build cost
    should_create, confidence, reason = should_create_index(
        estimated_build_cost=1000.0, queries_over_horizon=10, extra_cost_per_query_without_index=0.1
    )
    assert should_create is False


def test_should_create_index_zero_queries():
    """Test that index should NOT be created when there are no queries"""
    should_create, confidence, reason = should_create_index(
        estimated_build_cost=10.0, queries_over_horizon=0, extra_cost_per_query_without_index=0.1
    )
    assert should_create is False


def test_estimate_build_cost():
    """Test build cost estimation"""
    # Disable real plans to get consistent base cost calculation
    cost = estimate_build_cost("contacts", "email", row_count=10000, use_real_plans=False)
    assert cost > 0
    assert cost == 10.0  # 10000 / 1000


@pytest.mark.timeout(5)  # 5 second timeout for this test
def test_estimate_query_cost_without_index():
    """Test query cost estimation without index"""
    # Disable real plans to get consistent base cost calculation
    cost = estimate_query_cost_without_index(
        "contacts", "email", row_count=10000, use_real_plans=False
    )
    assert cost > 0
    # Base cost: max(0.1, 10000 / (10000.0 / 1.0)) = max(0.1, 1.0) = 1.0
    # However, if field selectivity is low (< 0.01), cost is multiplied by 0.5
    # So the actual cost might be 0.5 or 1.0 depending on selectivity
    assert cost in (0.5, 1.0)


def test_cost_benefit_threshold():
    """Test the exact threshold where index creation becomes beneficial"""
    # At threshold: 100 queries * 0.1 cost = 10.0, build_cost = 10.0
    # Should be False (equal, not greater)
    should_create, confidence, reason = should_create_index(
        estimated_build_cost=10.0, queries_over_horizon=100, extra_cost_per_query_without_index=0.1
    )
    assert should_create is False

    # Just above threshold: 101 queries * 0.5 cost = 50.5, build_cost = 10.0 (50.5% improvement)
    # Should be True (meets 5% minimum improvement requirement)
    should_create, confidence, reason = should_create_index(
        estimated_build_cost=10.0, queries_over_horizon=101, extra_cost_per_query_without_index=0.5
    )
    assert should_create is True
