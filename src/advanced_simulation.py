"""Advanced simulation features: production data patterns, chaos engineering, e-commerce patterns"""

import logging
import random
import time
from typing import Any

from src.simulation_enhancements import assign_tenant_characteristics

logger = logging.getLogger(__name__)


def generate_ecommerce_patterns(tenant_id: int, persona: str) -> dict[str, Any]:
    """
    Generate e-commerce specific query patterns.

    Patterns:
    - Product search (LIKE queries on product names)
    - Category filtering (WHERE category = X)
    - Price range queries (WHERE price BETWEEN X AND Y)
    - Order history lookups (WHERE customer_id = X)
    - Inventory checks (WHERE stock > 0)

    Args:
        tenant_id: Tenant ID
        persona: Tenant persona

    Returns:
        Query pattern configuration
    """
    patterns = {
        "product_search": {
            "frequency": 0.3,  # 30% of queries
            "query_type": "SELECT",
            "pattern": "LIKE",
            "fields": ["product_name", "description"],
            "complexity": "medium",
        },
        "category_filter": {
            "frequency": 0.2,
            "query_type": "SELECT",
            "pattern": "EQUALS",
            "fields": ["category_id", "subcategory_id"],
            "complexity": "low",
        },
        "price_range": {
            "frequency": 0.15,
            "query_type": "SELECT",
            "pattern": "RANGE",
            "fields": ["price", "discounted_price"],
            "complexity": "medium",
        },
        "order_history": {
            "frequency": 0.2,
            "query_type": "SELECT",
            "pattern": "EQUALS",
            "fields": ["customer_id", "order_id"],
            "complexity": "low",
        },
        "inventory_check": {
            "frequency": 0.15,
            "query_type": "SELECT",
            "pattern": "COMPARISON",
            "fields": ["stock_quantity", "available"],
            "complexity": "low",
        },
    }

    # Adjust based on persona
    if persona == "enterprise":
        # Enterprise: more complex queries, more joins
        patterns["product_search"]["complexity"] = "high"
        patterns["category_filter"]["frequency"] = 0.1
        patterns["price_range"]["frequency"] = 0.1
    elif persona == "startup":
        # Startup: simpler queries, more product searches
        patterns["product_search"]["frequency"] = 0.4
        patterns["category_filter"]["frequency"] = 0.3

    return patterns


def generate_analytics_patterns(tenant_id: int, persona: str) -> dict[str, Any]:
    """
    Generate analytics-specific query patterns.

    Patterns:
    - Aggregation queries (SUM, COUNT, AVG)
    - Time-series queries (WHERE date BETWEEN X AND Y)
    - Group by queries (GROUP BY category, region)
    - Window functions (ROW_NUMBER, RANK)
    - Cross-table joins for reporting

    Args:
        tenant_id: Tenant ID
        persona: Tenant persona

    Returns:
        Query pattern configuration
    """
    patterns = {
        "aggregation": {
            "frequency": 0.25,
            "query_type": "SELECT",
            "pattern": "AGGREGATE",
            "functions": ["SUM", "COUNT", "AVG", "MAX", "MIN"],
            "complexity": "high",
        },
        "time_series": {
            "frequency": 0.3,
            "query_type": "SELECT",
            "pattern": "RANGE",
            "fields": ["created_at", "updated_at", "event_date"],
            "complexity": "medium",
        },
        "group_by": {
            "frequency": 0.2,
            "query_type": "SELECT",
            "pattern": "GROUP_BY",
            "fields": ["category", "region", "status"],
            "complexity": "high",
        },
        "window_functions": {
            "frequency": 0.15,
            "query_type": "SELECT",
            "pattern": "WINDOW",
            "functions": ["ROW_NUMBER", "RANK", "DENSE_RANK"],
            "complexity": "high",
        },
        "cross_table_join": {
            "frequency": 0.1,
            "query_type": "SELECT",
            "pattern": "JOIN",
            "join_count": random.randint(2, 5),
            "complexity": "very_high",
        },
    }

    # Adjust based on persona
    if persona == "enterprise":
        # Enterprise: more complex analytics
        patterns["window_functions"]["frequency"] = 0.25
        patterns["cross_table_join"]["frequency"] = 0.2
    elif persona == "startup":
        # Startup: simpler aggregations
        patterns["aggregation"]["frequency"] = 0.4
        patterns["time_series"]["frequency"] = 0.4

    return patterns


class ChaosEngine:
    """Chaos engineering: inject failures to test resilience."""

    def __init__(self):
        self.enabled = False
        self.failure_rate = 0.0  # 0.0-1.0
        self.failure_types = []

    def inject_failure(self, failure_type: str) -> bool:
        """
        Inject a failure based on type and rate.

        Args:
            failure_type: Type of failure (network, database, timeout, etc.)

        Returns:
            True if failure should be injected
        """
        if not self.enabled:
            return False

        if random.random() < self.failure_rate:
            logger.warning(f"Chaos engineering: Injecting {failure_type} failure")
            return True
        return False

    def simulate_network_failure(self) -> None:
        """Simulate network failure (connection timeout)."""
        if self.inject_failure("network"):
            time.sleep(random.uniform(0.1, 0.5))  # Simulate delay
            raise ConnectionError("Simulated network failure")

    def simulate_database_timeout(self) -> None:
        """Simulate database timeout."""
        if self.inject_failure("timeout"):
            time.sleep(random.uniform(1.0, 3.0))  # Simulate long delay
            raise TimeoutError("Simulated database timeout")

    def simulate_connection_pool_exhaustion(self) -> None:
        """Simulate connection pool exhaustion."""
        if self.inject_failure("pool_exhaustion"):
            raise ConnectionError("Simulated connection pool exhaustion")

    def enable(self, failure_rate: float = 0.1) -> None:
        """Enable chaos engineering."""
        self.enabled = True
        self.failure_rate = failure_rate
        logger.info(f"Chaos engineering enabled (failure rate: {failure_rate:.1%})")

    def disable(self) -> None:
        """Disable chaos engineering."""
        self.enabled = False
        logger.info("Chaos engineering disabled")


_chaos_engine = ChaosEngine()


def get_chaos_engine() -> ChaosEngine:
    """Get global chaos engine instance."""
    return _chaos_engine


def create_production_like_queries(
    tenant_id: int,
    table_name: str,
    query_count: int,
    pattern_type: str = "mixed",
) -> list[dict[str, Any]]:
    """
    Create production-like queries based on anonymized patterns.

    Args:
        tenant_id: Tenant ID
        table_name: Table name
        query_count: Number of queries to generate
        pattern_type: Type of pattern (ecommerce, analytics, mixed)

    Returns:
        List of query configurations
    """
    # Get tenant persona
    tenant_chars = assign_tenant_characteristics(tenant_id)
    persona = tenant_chars.get("persona", "established")

    queries = []

    if pattern_type == "ecommerce":
        patterns = generate_ecommerce_patterns(tenant_id, persona)
    elif pattern_type == "analytics":
        patterns = generate_analytics_patterns(tenant_id, persona)
    else:  # mixed
        # Mix of ecommerce and analytics
        ecommerce_patterns = generate_ecommerce_patterns(tenant_id, persona)
        analytics_patterns = generate_analytics_patterns(tenant_id, persona)
        patterns = {**ecommerce_patterns, **analytics_patterns}
        # Normalize frequencies
        total_freq = sum(p.get("frequency", 0) for p in patterns.values())
        if total_freq > 0:
            for p in patterns.values():
                p["frequency"] = p.get("frequency", 0) / total_freq

    # Generate queries based on patterns
    for _ in range(query_count):
        # Select pattern based on frequency
        rand = random.random()
        cumulative = 0.0
        selected_pattern = None

        for pattern_name, pattern_config in patterns.items():
            cumulative += pattern_config.get("frequency", 0)
            if rand <= cumulative:
                selected_pattern = pattern_name
                break

        if selected_pattern:
            pattern = patterns[selected_pattern]
            query_config = {
                "tenant_id": tenant_id,
                "table_name": table_name,
                "pattern": selected_pattern,
                "query_type": pattern.get("query_type", "SELECT"),
                "complexity": pattern.get("complexity", "medium"),
                "fields": pattern.get("fields", []),
            }
            queries.append(query_config)

    return queries


def simulate_chaos_scenario(
    scenario: str,
    duration_seconds: int = 60,
    failure_rate: float = 0.2,
) -> dict[str, Any]:
    """
    Simulate a chaos engineering scenario.

    Args:
        scenario: Scenario name (network_failure, timeout, pool_exhaustion, mixed)
        duration_seconds: How long to run the scenario
        failure_rate: Rate of failures (0.0-1.0)

    Returns:
        Scenario results
    """
    chaos = get_chaos_engine()
    chaos.enable(failure_rate=failure_rate)

    results = {
        "scenario": scenario,
        "duration_seconds": duration_seconds,
        "failure_rate": failure_rate,
        "started_at": time.time(),
        "failures_injected": 0,
        "operations_attempted": 0,
        "operations_succeeded": 0,
        "operations_failed": 0,
    }

    end_time = time.time() + duration_seconds

    try:
        while time.time() < end_time:
            results["operations_attempted"] += 1

            try:
                if scenario == "network_failure":
                    chaos.simulate_network_failure()
                elif scenario == "timeout":
                    chaos.simulate_database_timeout()
                elif scenario == "pool_exhaustion":
                    chaos.simulate_connection_pool_exhaustion()
                elif scenario == "mixed":
                    # Randomly select failure type
                    failure_type = random.choice(["network", "timeout", "pool_exhaustion"])
                    if failure_type == "network":
                        chaos.simulate_network_failure()
                    elif failure_type == "timeout":
                        chaos.simulate_database_timeout()
                    else:
                        chaos.simulate_connection_pool_exhaustion()

                results["operations_succeeded"] += 1
            except (ConnectionError, TimeoutError) as e:
                results["operations_failed"] += 1
                results["failures_injected"] += 1
                logger.debug(f"Chaos scenario failure: {e}")

            time.sleep(0.1)  # Small delay between operations

    finally:
        chaos.disable()

    results["ended_at"] = time.time()
    results["success_rate"] = (
        results["operations_succeeded"] / results["operations_attempted"]
        if results["operations_attempted"] > 0
        else 0.0
    )

    logger.info(
        f"Chaos scenario {scenario} completed: "
        f"{results['operations_succeeded']}/{results['operations_attempted']} succeeded "
        f"({results['success_rate']:.1%})"
    )

    return results
