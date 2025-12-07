"""Enhanced simulation features: data skew, tenant diversity, realistic patterns"""

import logging
import random
from typing import cast

from src.type_definitions import TenantCharacteristics, TenantConfig

logger = logging.getLogger(__name__)


def generate_skewed_distribution(total_items: int, skew_factor: float = 0.8) -> list[int]:
    """
    Generate a power-law (80/20) distribution for realistic data skew.

    Args:
        total_items: Total number of items to distribute
        skew_factor: Skew factor (0.8 = 80/20 rule)

    Returns:
        List of item counts per tenant (sorted descending)
    """
    if total_items <= 0:
        return []

    # Power-law distribution: few tenants have most data
    # Using Pareto distribution (80/20 rule)
    distribution: list[int] = []
    remaining = total_items

    # Generate distribution until we've allocated all items
    while remaining > 0 and len(distribution) < total_items:
        # Power-law: each next value is smaller
        # Using inverse of rank to create skew
        rank = len(distribution) + 1
        # Pareto: value = base / rank^alpha
        # alpha = 1 gives 80/20 rule
        alpha: float = 1.0
        base_value: float = float(total_items) * (1.0 - skew_factor)
        rank_float: float = float(rank)
        rank_power: float = rank_float**alpha
        value = int(base_value / rank_power)

        # Ensure we don't exceed remaining
        value = min(value, remaining, total_items // 10)  # Cap at 10% of total
        if value > 0:
            distribution.append(value)
            remaining -= value
        else:
            # Distribute remaining evenly among remaining slots
            if remaining > 0:
                per_slot = remaining // max(1, total_items - len(distribution))
                distribution.append(per_slot)
                remaining -= per_slot
            else:
                break

    # Sort descending (hot tenants first)
    distribution.sort(reverse=True)
    return distribution


def assign_tenant_characteristics(tenant_id: int, num_tenants: int = 100) -> TenantCharacteristics:
    """
    Assign realistic characteristics to a tenant for diversity.

    Args:
        tenant_id: Tenant ID
        num_tenants: Total number of tenants (optional, default 100)

    Returns:
        dict with tenant characteristics
    """
    # Create tenant "personas" for diversity
    persona_types = ["startup", "enterprise", "growing", "established", "niche"]
    persona = persona_types[tenant_id % len(persona_types)]

    # Assign characteristics based on persona
    if persona == "startup":
        # Small, fast-growing, high query volume relative to data
        data_multiplier = 0.5
        query_multiplier = 1.5
        spike_probability = 0.2  # More volatile
    elif persona == "enterprise":
        # Large, stable, moderate query volume
        data_multiplier = 2.0
        query_multiplier = 1.0
        spike_probability = 0.05  # Less volatile
    elif persona == "growing":
        # Medium, increasing, moderate spikes
        data_multiplier = 1.0
        query_multiplier = 1.2
        spike_probability = 0.15
    elif persona == "established":
        # Large, stable, predictable
        data_multiplier = 1.5
        query_multiplier = 0.8
        spike_probability = 0.1
    else:  # niche
        # Small, specialized, variable
        data_multiplier = 0.7
        query_multiplier = 1.3
        spike_probability = 0.25

    # Add some randomness
    data_multiplier *= random.uniform(0.8, 1.2)
    query_multiplier *= random.uniform(0.9, 1.1)

    return cast(
        TenantCharacteristics,
        {
            "persona": persona,
            "data_multiplier": data_multiplier,
            "query_multiplier": query_multiplier,
            "spike_probability": spike_probability,
            "query_pattern": _assign_query_pattern(tenant_id, persona),
        },
    )


def _assign_query_pattern(tenant_id: int, persona: str) -> str:
    """Assign query pattern based on tenant persona."""
    patterns = ["email", "phone", "industry", "mixed"]

    # Different personas favor different patterns
    if persona == "startup":
        # Startups query email more (user lookups)
        return patterns[tenant_id % 2]  # email or phone
    elif persona == "enterprise":
        # Enterprises use mixed patterns
        return "mixed"
    elif persona == "growing":
        # Growing companies use industry patterns
        return "industry"
    else:
        # Others use mixed
        return patterns[tenant_id % len(patterns)]


def create_realistic_tenant_distribution(
    num_tenants: int,
    base_contacts: int,
    base_queries: int,
) -> list[TenantConfig]:
    """
    Create realistic tenant distribution with data skew and diversity.

    Args:
        num_tenants: Number of tenants
        base_contacts: Base number of contacts per tenant
        base_queries: Base number of queries per tenant

    Returns:
        List of tenant configurations with realistic distribution
    """
    # Generate skewed distribution for contacts
    total_contacts = num_tenants * base_contacts
    contact_distribution = generate_skewed_distribution(total_contacts, skew_factor=0.8)

    # Pad or trim to match num_tenants
    while len(contact_distribution) < num_tenants:
        contact_distribution.append(base_contacts)
    contact_distribution = contact_distribution[:num_tenants]

    # Generate query distribution (may differ from data distribution)
    total_queries = num_tenants * base_queries
    query_distribution = generate_skewed_distribution(total_queries, skew_factor=0.75)
    while len(query_distribution) < num_tenants:
        query_distribution.append(base_queries)
    query_distribution = query_distribution[:num_tenants]

    # Create tenant configurations
    tenant_configs = []
    for i in range(num_tenants):
        characteristics = assign_tenant_characteristics(i, num_tenants)

        # Apply multipliers
        contacts = int(contact_distribution[i] * characteristics["data_multiplier"])
        queries = int(query_distribution[i] * characteristics["query_multiplier"])

        tenant_configs.append(
            cast(
                TenantConfig,
                {
                    "tenant_index": i,
                    "contacts": max(10, contacts),  # Minimum 10 contacts
                    "queries": max(10, queries),  # Minimum 10 queries
                    "orgs": max(1, int(contacts / 10)),  # ~10 contacts per org
                    "interactions": max(10, int(contacts * 2)),  # ~2 interactions per contact
                    "query_pattern": characteristics["query_pattern"],
                    "spike_probability": characteristics["spike_probability"],
                    "persona": characteristics["persona"],
                },
            )
        )

    return tenant_configs
