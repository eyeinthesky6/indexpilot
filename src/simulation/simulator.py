"""Simulation harness - load generation and benchmark"""

import atexit
import contextlib
import json
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from typing import cast

from psycopg2.extras import RealDictCursor

from src.auto_indexer import analyze_and_create_indexes
from src.db import close_connection_pool, get_connection, init_connection_pool
from src.expression import initialize_tenant_expression
from src.graceful_shutdown import (
    is_shutting_down,
    register_shutdown_handler,
    setup_graceful_shutdown,
)
from src.production_config import get_config, validate_production_config
from src.rollback import enable_system, init_rollback
from src.stats import flush_query_stats, log_query_stat
from src.type_definitions import JSONDict, JSONValue

# Validate production configuration at startup
try:
    config = validate_production_config()
    log_level_val = config.get("LOG_LEVEL", "INFO")
    log_level = log_level_val.upper() if isinstance(log_level_val, str) else "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
except ValueError as e:
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"Configuration validation failed: {e}")
    raise

logger = logging.getLogger(__name__)


# Helper function for flushed output to prevent timeout issues
def print_flush(*args, **kwargs):
    """Print with immediate flush to prevent timeout issues"""
    print(*args, **kwargs)
    sys.stdout.flush()


# Set up graceful shutdown handlers
# For simulations, use unbuffered output to prevent timeout issues
if sys.stdout.isatty():
    # Unbuffered output for interactive terminals
    with contextlib.suppress(AttributeError, ValueError):
        # Fallback for older Python versions or non-reconfigurable streams
        # sys.stdout.reconfigure may not be available on all Python versions
        # Use getattr to avoid type errors - reconfigure is available in Python 3.7+
        reconfigure_method = getattr(sys.stdout, "reconfigure", None)
        if reconfigure_method is not None:
            reconfigure_method(line_buffering=True)

setup_graceful_shutdown()

# Scenario configurations based on real-world patterns
SCENARIOS = {
    "small": {
        "description": "Small SaaS (startup, 10-50 customers)",
        "num_tenants": 10,
        "contacts_per_tenant": 500,
        "orgs_per_tenant": 50,
        "interactions_per_tenant": 1000,
        "queries_per_tenant": 200,
        "spike_probability": 0.1,  # 10% chance of spike
        "spike_multiplier": 3.0,  # 3x normal traffic during spike
        "spike_duration_queries": 20,  # Spike lasts 20 queries
        "estimated_time_minutes": 2,
    },
    "medium": {
        "description": "Medium SaaS (growing business, 100-500 customers)",
        "num_tenants": 50,
        "contacts_per_tenant": 2000,
        "orgs_per_tenant": 200,
        "interactions_per_tenant": 5000,
        "queries_per_tenant": 500,
        "spike_probability": 0.15,  # 15% chance of spike
        "spike_multiplier": 4.0,  # 4x normal traffic during spike
        "spike_duration_queries": 30,  # Spike lasts 30 queries
        "estimated_time_minutes": 10,
    },
    "large": {
        "description": "Large SaaS (established business, 1000+ customers)",
        "num_tenants": 100,
        "contacts_per_tenant": 10000,
        "orgs_per_tenant": 1000,
        "interactions_per_tenant": 20000,
        "queries_per_tenant": 1000,
        "spike_probability": 0.2,  # 20% chance of spike
        "spike_multiplier": 5.0,  # 5x normal traffic during spike
        "spike_duration_queries": 50,  # Spike lasts 50 queries
        "estimated_time_minutes": 45,
    },
    "stress-test": {
        "description": "Stress test (maximum load, 10,000+ customers)",
        "num_tenants": 200,
        "contacts_per_tenant": 50000,
        "orgs_per_tenant": 5000,
        "interactions_per_tenant": 100000,
        "queries_per_tenant": 2000,
        "spike_probability": 0.3,  # 30% chance of spike
        "spike_multiplier": 10.0,  # 10x normal traffic during spike
        "spike_duration_queries": 100,  # Spike lasts 100 queries
        "estimated_time_minutes": 180,
    },
}

# Get configuration values
prod_config = get_config()
min_conn = prod_config.get_int("MIN_CONNECTIONS", 2)
max_conn = prod_config.get_int("MAX_CONNECTIONS", 20)

# Check for startup bypass (config file or environment variable)
try:
    from src.bypass_config import is_feature_enabled, should_skip_initialization

    if should_skip_initialization():
        logger.warning("System initialization skipped per configuration")
        # Skip system initialization - will use direct connections when needed
        init_rollback()  # Still initialize rollback for emergency controls
        # Don't enable system - it's bypassed
        # Note: Connection pool will be initialized on first use if needed
    else:
        # Normal initialization
        init_connection_pool(min_conn=min_conn, max_conn=max_conn)
        init_rollback()

        # Check config file for initial state
        if is_feature_enabled("auto_indexing"):
            enable_system("Configuration file: auto_indexing enabled")
        else:
            from src.rollback import disable_system

            disable_system("Configuration file: auto_indexing disabled")

    # Log bypass status at startup for user visibility
    try:
        from src.bypass_status import log_bypass_status

        log_bypass_status(include_details=True)
    except Exception as e:
        logger.debug(f"Could not log bypass status: {e}")

except ImportError:
    # Config system not available, use normal initialization
    logger.debug("Bypass config system not available, using normal initialization")
    init_connection_pool(min_conn=min_conn, max_conn=max_conn)
    init_rollback()
    enable_system("Simulator initialization")
except Exception as e:
    # Handle any errors in config loading gracefully
    logger.warning(f"Error loading bypass config: {e}, using normal initialization")
    init_connection_pool(min_conn=min_conn, max_conn=max_conn)
    init_rollback()
    enable_system("Simulator initialization (fallback)")

# Register shutdown handler for connection pool cleanup
register_shutdown_handler(close_connection_pool, priority=10)


# Start maintenance background thread for periodic integrity checks
def start_maintenance_background():
    """Start background thread for periodic maintenance tasks"""
    import threading

    from src.maintenance import run_maintenance_tasks

    def maintenance_loop():
        """Run maintenance tasks every hour"""
        maintenance_interval = prod_config.get_int("MAINTENANCE_INTERVAL", 3600)
        while not is_shutting_down():
            try:
                run_maintenance_tasks(force=False)
            except Exception as e:
                logger.error(f"Maintenance task error: {e}")

            # Sleep in small intervals to check for shutdown
            for _ in range(maintenance_interval):
                if is_shutting_down():
                    break
                time.sleep(1)

    thread = threading.Thread(target=maintenance_loop, daemon=True, name="MaintenanceThread")
    thread.start()
    logger.info(
        f"Maintenance background thread started (interval: {prod_config.get_int('MAINTENANCE_INTERVAL', 3600)}s)"
    )


# Start maintenance thread
start_maintenance_background()

# Cleanup on exit (graceful_shutdown handles this, but keep atexit as backup)
atexit.register(close_connection_pool)


def create_tenant(name):
    """Create a new tenant"""
    from src.audit import log_audit_event

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                INSERT INTO tenants (name)
                VALUES (%s)
                RETURNING id
            """,
                (name,),
            )
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Failed to create tenant {name}: no ID returned")
            tenant_id = result["id"]
            conn.commit()

            # Initialize expression profile
            initialize_tenant_expression(tenant_id)

            # Log to audit trail
            log_audit_event(
                "INITIALIZE_TENANT",
                tenant_id=tenant_id,
                details={"tenant_name": name, "action": "tenant_created"},
                severity="info",
            )

            return tenant_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def seed_tenant_data(
    tenant_id, num_contacts=100, num_orgs=20, num_interactions=200, batch_size=1000
):
    """Seed data for a tenant (optimized with executemany for bulk inserts)"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            industries = ["Tech", "Finance", "Healthcare", "Retail", "Manufacturing"]
            interaction_types = ["call", "email", "meeting", "note"]
            now = datetime.now()

            # Create contacts (bulk insert with executemany)
            contacts = []
            print_flush(f"  Seeding {num_contacts} contacts...")
            for batch_start in range(0, num_contacts, batch_size):
                batch_end = min(batch_start + batch_size, num_contacts)
                batch_data = []

                for i in range(batch_start, batch_end):
                    batch_data.append(
                        (
                            tenant_id,
                            f"Contact {i + 1}",
                            f"contact{i + 1}@example.com",
                            f"555-{1000 + i:04d}",
                            f"Custom {i + 1}" if i % 3 == 0 else None,
                            random.randint(1, 100) if i % 5 == 0 else None,
                            now - timedelta(days=random.randint(0, 365)),
                        )
                    )

                # Bulk insert
                cursor.executemany(
                    """
                    INSERT INTO contacts
                    (tenant_id, name, email, phone, custom_text_1, custom_number_1, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    batch_data,
                )

                # Progress output for large batches
                if batch_end % (batch_size * 5) == 0 or batch_end == num_contacts:
                    print_flush(f"    Created {batch_end}/{num_contacts} contacts")

                # Get IDs for inserted contacts (for foreign keys)
                cursor.execute(
                    """
                    SELECT id FROM contacts
                    WHERE tenant_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                """,
                    (tenant_id, batch_end - batch_start),
                )
                batch_contacts = [row["id"] for row in cursor.fetchall()]
                contacts.extend(batch_contacts)

                if batch_end % (batch_size * 5) == 0 or batch_end == num_contacts:
                    print_flush(f"    Created {batch_end}/{num_contacts} contacts")

            # Create organizations (bulk insert)
            orgs = []
            print_flush(f"  Seeding {num_orgs} organizations...")
            for batch_start in range(0, num_orgs, batch_size):
                batch_end = min(batch_start + batch_size, num_orgs)
                org_batch_data: list[tuple[int, str, str, str | None, datetime]] = []

                for i in range(batch_start, batch_end):
                    org_batch_data.append(
                        (
                            tenant_id,
                            f"Org {i + 1}",
                            random.choice(industries),
                            f"Org Custom {i + 1}" if i % 4 == 0 else None,
                            now - timedelta(days=random.randint(0, 365)),
                        )
                    )

                cursor.executemany(
                    """
                    INSERT INTO organizations
                    (tenant_id, name, industry, custom_text_1, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    org_batch_data,
                )

                # Progress output for large batches
                if batch_end % (batch_size * 5) == 0 or batch_end == num_orgs:
                    print_flush(f"    Created {batch_end}/{num_orgs} organizations")

                # Get IDs for inserted orgs
                cursor.execute(
                    """
                    SELECT id FROM organizations
                    WHERE tenant_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                """,
                    (tenant_id, batch_end - batch_start),
                )
                batch_orgs = [row["id"] for row in cursor.fetchall()]
                orgs.extend(batch_orgs)

            # Create interactions (bulk insert)
            print_flush(f"  Seeding {num_interactions} interactions...")
            # Pre-generate random choices for better performance
            contact_choices = contacts if contacts else [None]
            org_choices = orgs if orgs else [None]

            for batch_start in range(0, num_interactions, batch_size):
                batch_end = min(batch_start + batch_size, num_interactions)
                interaction_batch_data: list[
                    tuple[int, int | None, int | None, str, datetime, str]
                ] = []

                for _i in range(batch_start, batch_end):
                    interaction_batch_data.append(
                        (
                            tenant_id,
                            random.choice(contact_choices),
                            random.choice(org_choices),
                            random.choice(interaction_types),
                            now - timedelta(days=random.randint(0, 90)),
                            json.dumps({"duration": random.randint(5, 60)}),
                        )
                    )

                cursor.executemany(
                    """
                    INSERT INTO interactions
                    (tenant_id, contact_id, org_id, type, occurred_at, metadata_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    interaction_batch_data,
                )

                if batch_end % (batch_size * 5) == 0 or batch_end == num_interactions:
                    print_flush(f"    Created {batch_end}/{num_interactions} interactions")

            conn.commit()
            print_flush(
                f"Seeded tenant {tenant_id}: {num_contacts} contacts, {num_orgs} orgs, {num_interactions} interactions"
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def run_query_by_email(tenant_id, max_contact_id=None):
    """Run a query filtering by email"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Random email pattern - scale with data size
            if max_contact_id is None:
                # Get max contact ID for this tenant
                cursor.execute(
                    "SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,)
                )
                result = cursor.fetchone()
                max_contact_id = result["max_id"] if result and result["max_id"] else 10000

            contact_num = random.randint(1, min(max_contact_id, 10000))
            email_pattern = f"%contact{contact_num}%"
            cursor.execute(
                """
                SELECT * FROM contacts
                WHERE tenant_id = %s AND email LIKE %s
                LIMIT 10
            """,
                (tenant_id, email_pattern),
            )
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(
                tenant_id, "contacts", "email", "READ", duration_ms, skip_validation=True
            )
            return duration_ms
        finally:
            cursor.close()


def run_query_by_phone(tenant_id, max_contact_id=None):
    """Run a query filtering by phone"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Scale phone range with data size
            if max_contact_id is None:
                cursor.execute(
                    "SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,)
                )
                result = cursor.fetchone()
                max_contact_id = result["max_id"] if result and result["max_id"] else 10000

            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
            phone_pattern = f"555-{phone_num:04d}"
            cursor.execute(
                """
                SELECT * FROM contacts
                WHERE tenant_id = %s AND phone = %s
                LIMIT 10
            """,
                (tenant_id, phone_pattern),
            )
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(
                tenant_id, "contacts", "phone", "READ", duration_ms, skip_validation=True
            )
            return duration_ms
        finally:
            cursor.close()


def run_query_by_industry(tenant_id):
    """Run a query filtering by industry"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            industries = ["Tech", "Finance", "Healthcare", "Retail", "Manufacturing"]
            industry = random.choice(industries)
            cursor.execute(
                """
                SELECT * FROM organizations
                WHERE tenant_id = %s AND industry = %s
                LIMIT 10
            """,
                (tenant_id, industry),
            )
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(
                tenant_id, "organizations", "industry", "READ", duration_ms, skip_validation=True
            )
            return duration_ms
        finally:
            cursor.close()


def run_query_by_custom_field(tenant_id):
    """Run a query filtering by custom field"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                SELECT * FROM contacts
                WHERE tenant_id = %s AND custom_text_1 IS NOT NULL
                LIMIT 10
            """,
                (tenant_id,),
            )
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(
                tenant_id, "contacts", "custom_text_1", "READ", duration_ms, skip_validation=True
            )
            return duration_ms
        finally:
            cursor.close()


def run_query_by_interaction_type(tenant_id):
    """Run a query filtering by interaction type"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            types = ["call", "email", "meeting", "note"]
            interaction_type = random.choice(types)
            cursor.execute(
                """
                SELECT * FROM interactions
                WHERE tenant_id = %s AND type = %s
                LIMIT 10
            """,
                (tenant_id, interaction_type),
            )
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(
                tenant_id, "interactions", "type", "READ", duration_ms, skip_validation=True
            )
            return duration_ms
        finally:
            cursor.close()


def simulate_tenant_workload(
    tenant_id,
    num_queries=1000,
    query_pattern="mixed",
    _use_cache=False,
    spike_probability=0.15,
    spike_multiplier=4.0,
    spike_duration=30,
    use_advanced_patterns=False,
    tenant_persona="established",
):
    """
    Simulate workload for a tenant with a specific query pattern and optional traffic spikes.
    Optimized to reuse database connections within batches.

    Args:
        tenant_id: Tenant ID
        num_queries: Total number of queries to run
        query_pattern: 'email', 'phone', 'industry', 'mixed', 'ecommerce', or 'analytics'
        _use_cache: Whether to use cached max_contact_id (reserved for future use)
        spike_probability: Probability of entering a spike (0.0-1.0)
        spike_multiplier: Multiplier for queries during spike (e.g., 4.0 = 4x normal)
        spike_duration: Number of queries a spike lasts
        use_advanced_patterns: If True, use e-commerce/analytics patterns when applicable
        tenant_persona: Tenant persona for advanced patterns
    """
    durations = []

    # Get advanced patterns if enabled (Phase 3)
    ecommerce_patterns = None
    analytics_patterns = None
    if use_advanced_patterns:
        try:
            from src.simulation.advanced_simulation import (
                generate_analytics_patterns,
                generate_ecommerce_patterns,
            )

            if query_pattern == "ecommerce":
                ecommerce_patterns = generate_ecommerce_patterns(tenant_id, tenant_persona)
            elif query_pattern == "analytics":
                analytics_patterns = generate_analytics_patterns(tenant_id, tenant_persona)
        except Exception as e:
            logger.debug(f"Could not load advanced patterns: {e}")

    # Cache max_contact_id once at the start
    max_contact_id = None
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,)
            )
            result = cursor.fetchone()
            max_contact_id = result["max_id"] if result and result["max_id"] else 10000
        finally:
            cursor.close()

    # Spike state tracking
    in_spike = False
    spike_queries_remaining = 0
    # Note: spike_started_at removed as it was unused

    # Reuse connection for batches of queries (reduces connection overhead)
    batch_size = 50  # Process queries in batches
    i = 0
    last_print = 0

    while i < num_queries:
        # Check for shutdown signal
        if is_shutting_down():
            print_flush(
                f"  Tenant {tenant_id}: Shutdown requested, stopping at query {i + 1}/{num_queries}"
            )
            break

        # Check if we should enter a spike
        if not in_spike and random.random() < spike_probability:
            in_spike = True
            spike_queries_remaining = spike_duration
            # Note: spike_started_at removed as it was unused
            print_flush(
                f"  Tenant {tenant_id}: [SPIKE] DETECTED at query {i + 1} (will last {spike_duration} queries)"
            )

        # Determine how many queries to run in this iteration
        if in_spike:
            # During spike, run multiple queries per iteration
            queries_this_iteration = min(
                int(spike_multiplier),
                spike_queries_remaining,
                num_queries - i,
                batch_size,  # Limit batch size
            )
            spike_queries_remaining -= queries_this_iteration
            if spike_queries_remaining <= 0:
                in_spike = False
                print_flush(f"  Tenant {tenant_id}: [SPIKE ENDED] at query {i + 1}")
        else:
            queries_this_iteration = min(1, num_queries - i)

        # Reuse connection for this batch
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Run queries for this iteration
                for _ in range(queries_this_iteration):
                    start = time.time()
                    table = "contacts"
                    field = "email"

                    if query_pattern == "email":
                        # 80% email, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """,
                                (tenant_id, email_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "email"
                        else:
                            if random.random() < 0.5:
                                phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                                phone_pattern = f"555-{phone_num:04d}"
                                cursor.execute(
                                    """
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND phone = %s
                                    LIMIT 10
                                """,
                                    (tenant_id, phone_pattern),
                                )
                                _ = cursor.fetchall()
                                table, field = "contacts", "phone"
                            else:
                                industries = [
                                    "Tech",
                                    "Finance",
                                    "Healthcare",
                                    "Retail",
                                    "Manufacturing",
                                ]
                                industry = random.choice(industries)
                                cursor.execute(
                                    """
                                    SELECT * FROM organizations
                                    WHERE tenant_id = %s AND industry = %s
                                    LIMIT 10
                                """,
                                    (tenant_id, industry),
                                )
                                _ = cursor.fetchall()
                                table, field = "organizations", "industry"
                    elif query_pattern == "phone":
                        # 80% phone, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                            phone_pattern = f"555-{phone_num:04d}"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND phone = %s
                                LIMIT 10
                            """,
                                (tenant_id, phone_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "phone"
                        else:
                            if random.random() < 0.5:
                                contact_num = random.randint(1, min(max_contact_id, 10000))
                                email_pattern = f"%contact{contact_num}%"
                                cursor.execute(
                                    """
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND email LIKE %s
                                    LIMIT 10
                                """,
                                    (tenant_id, email_pattern),
                                )
                                _ = cursor.fetchall()
                                table, field = "contacts", "email"
                            else:
                                industries = [
                                    "Tech",
                                    "Finance",
                                    "Healthcare",
                                    "Retail",
                                    "Manufacturing",
                                ]
                                industry = random.choice(industries)
                                cursor.execute(
                                    """
                                    SELECT * FROM organizations
                                    WHERE tenant_id = %s AND industry = %s
                                    LIMIT 10
                                """,
                                    (tenant_id, industry),
                                )
                                _ = cursor.fetchall()
                                table, field = "organizations", "industry"
                    elif query_pattern == "industry":
                        # 80% industry, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            industries = [
                                "Tech",
                                "Finance",
                                "Healthcare",
                                "Retail",
                                "Manufacturing",
                            ]
                            industry = random.choice(industries)
                            cursor.execute(
                                """
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """,
                                (tenant_id, industry),
                            )
                            _ = cursor.fetchall()
                            table, field = "organizations", "industry"
                        else:
                            if random.random() < 0.5:
                                contact_num = random.randint(1, min(max_contact_id, 10000))
                                email_pattern = f"%contact{contact_num}%"
                                cursor.execute(
                                    """
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND email LIKE %s
                                    LIMIT 10
                                """,
                                    (tenant_id, email_pattern),
                                )
                                _ = cursor.fetchall()
                                table, field = "contacts", "email"
                            else:
                                phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                                phone_pattern = f"555-{phone_num:04d}"
                                cursor.execute(
                                    """
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND phone = %s
                                    LIMIT 10
                                """,
                                    (tenant_id, phone_pattern),
                                )
                                _ = cursor.fetchall()
                                table, field = "contacts", "phone"
                    elif query_pattern == "ecommerce" and ecommerce_patterns:
                        # Use e-commerce patterns (Phase 3)
                        pattern_rand = random.random()
                        cumulative = 0.0
                        selected_pattern = None
                        for pattern_name, pattern_config in ecommerce_patterns.items():
                            cumulative += pattern_config.get("frequency", 0)
                            if pattern_rand <= cumulative:
                                selected_pattern = pattern_name
                                break

                        # Generate query based on selected pattern
                        if selected_pattern == "product_search":
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """,
                                (tenant_id, email_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "email"
                        elif selected_pattern == "category_filter":
                            industries = [
                                "Tech",
                                "Finance",
                                "Healthcare",
                                "Retail",
                                "Manufacturing",
                            ]
                            industry = random.choice(industries)
                            cursor.execute(
                                """
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """,
                                (tenant_id, industry),
                            )
                            _ = cursor.fetchall()
                            table, field = "organizations", "industry"
                        else:
                            # Fallback to standard query
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """,
                                (tenant_id, email_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "email"
                    elif query_pattern == "analytics" and analytics_patterns:
                        # Use analytics patterns (Phase 3)
                        pattern_rand = random.random()
                        cumulative = 0.0
                        selected_pattern = None
                        for pattern_name, pattern_config in analytics_patterns.items():
                            cumulative += pattern_config.get("frequency", 0)
                            if pattern_rand <= cumulative:
                                selected_pattern = pattern_name
                                break

                        # Generate query based on selected pattern
                        if selected_pattern == "aggregation":
                            cursor.execute(
                                """
                                SELECT industry, COUNT(*) as count
                                FROM organizations
                                WHERE tenant_id = %s
                                GROUP BY industry
                                LIMIT 10
                            """,
                                (tenant_id,),
                            )
                            _ = cursor.fetchall()
                            table, field = "organizations", "industry"
                        elif selected_pattern == "time_series":
                            cursor.execute(
                                """
                                SELECT DATE(created_at) as date, COUNT(*) as count
                                FROM contacts
                                WHERE tenant_id = %s AND created_at >= NOW() - INTERVAL '30 days'
                                GROUP BY DATE(created_at)
                                ORDER BY date DESC
                                LIMIT 10
                            """,
                                (tenant_id,),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "created_at"
                        else:
                            # Fallback to standard query
                            industries = [
                                "Tech",
                                "Finance",
                                "Healthcare",
                                "Retail",
                                "Manufacturing",
                            ]
                            industry = random.choice(industries)
                            cursor.execute(
                                """
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """,
                                (tenant_id, industry),
                            )
                            _ = cursor.fetchall()
                            table, field = "organizations", "industry"
                    else:  # mixed
                        # Balanced distribution
                        rand = random.random()
                        if rand < 0.3:
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """,
                                (tenant_id, email_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "email"
                        elif rand < 0.6:
                            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                            phone_pattern = f"555-{phone_num:04d}"
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND phone = %s
                                LIMIT 10
                            """,
                                (tenant_id, phone_pattern),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "phone"
                        elif rand < 0.8:
                            industries = [
                                "Tech",
                                "Finance",
                                "Healthcare",
                                "Retail",
                                "Manufacturing",
                            ]
                            industry = random.choice(industries)
                            cursor.execute(
                                """
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """,
                                (tenant_id, industry),
                            )
                            _ = cursor.fetchall()
                            table, field = "organizations", "industry"
                        elif rand < 0.9:
                            interaction_types = ["call", "email", "meeting", "note"]
                            interaction_type = random.choice(interaction_types)
                            cursor.execute(
                                """
                                SELECT * FROM interactions
                                WHERE tenant_id = %s AND type = %s
                                LIMIT 10
                            """,
                                (tenant_id, interaction_type),
                            )
                            _ = cursor.fetchall()
                            table, field = "interactions", "type"
                        else:
                            cursor.execute(
                                """
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND custom_text_1 IS NOT NULL
                                LIMIT 10
                            """,
                                (tenant_id,),
                            )
                            _ = cursor.fetchall()
                            table, field = "contacts", "custom_text_1"

                    duration_ms = (time.time() - start) * 1000
                    log_query_stat(
                        tenant_id, table, field, "READ", duration_ms, skip_validation=True
                    )
                    durations.append(duration_ms)
                    i += 1
            finally:
                cursor.close()

        # Progress reporting (reduced frequency)
        if num_queries > 50 and (i - last_print) >= 50:
            status = "[SPIKE]" if in_spike else "normal"
            print_flush(f"  Tenant {tenant_id}: Completed {i}/{num_queries} queries ({status})")
            last_print = i
            flush_query_stats()  # Flush stats periodically

    # Flush remaining stats
    flush_query_stats()
    return durations


def run_baseline_simulation(
    num_tenants=10,
    queries_per_tenant=200,
    contacts_per_tenant=100,
    orgs_per_tenant=20,
    interactions_per_tenant=200,
    spike_probability=0.15,
    spike_multiplier=4.0,
    spike_duration=30,
    scenario_name=None,
):
    """Run baseline simulation without auto-indexing"""
    print_flush("=" * 60)
    print_flush("BASELINE SIMULATION (No Auto-Indexing)")
    if scenario_name:
        print_flush(f"Scenario: {scenario_name}")
    print_flush("=" * 60)
    print_flush(f"Configuration: {num_tenants} tenants, {queries_per_tenant} queries/tenant")
    print(
        f"Data scale: {contacts_per_tenant} contacts, {orgs_per_tenant} orgs, {interactions_per_tenant} interactions per tenant"
    )
    if spike_probability > 0:
        print(
            f"Traffic spikes: {spike_probability * 100:.0f}% probability, {spike_multiplier}x multiplier, {spike_duration} queries duration"
        )
    print("=" * 60)

    # Create tenants
    tenant_ids = []
    # Use realistic distribution if enabled
    use_realistic_distribution = True  # Can be made configurable
    if use_realistic_distribution:
        try:
            from src.simulation.simulation_enhancements import create_realistic_tenant_distribution

            tenant_configs = create_realistic_tenant_distribution(
                num_tenants=num_tenants,
                base_contacts=contacts_per_tenant,
                base_queries=queries_per_tenant,
            )
            print_flush("Using realistic tenant distribution (data skew and diversity enabled)")
        except Exception as e:
            logger.debug(f"Realistic distribution failed, using uniform: {e}")
            tenant_configs = None
    else:
        tenant_configs = None

    # Check for advanced simulation features (Phase 3)
    use_advanced_patterns = False
    use_chaos_engineering = False
    try:
        from src.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        use_advanced_patterns = config_loader.get_bool(
            "features.advanced_simulation.enabled", False
        )
        use_chaos_engineering = config_loader.get_bool("features.chaos_engineering.enabled", False)
    except Exception:
        pass

    if use_advanced_patterns:
        try:
            logger.info("Advanced simulation patterns enabled (e-commerce/analytics)")
        except Exception as e:
            logger.debug(f"Advanced patterns not available: {e}")
            use_advanced_patterns = False

    if use_chaos_engineering:
        try:
            from src.simulation.advanced_simulation import get_chaos_engine

            chaos_engine = get_chaos_engine()
            chaos_engine.enable(failure_rate=0.05)  # 5% failure rate
            logger.info("Chaos engineering enabled (5% failure rate)")
        except Exception as e:
            logger.debug(f"Chaos engineering not available: {e}")
            use_chaos_engineering = False

    query_patterns = ["email", "phone", "industry", "mixed"]
    all_durations = []

    for i in range(num_tenants):
        tenant_id = create_tenant(f"Tenant {i + 1}")
        tenant_ids.append(tenant_id)

        # Seed data with realistic distribution if available
        if tenant_configs:
            config = tenant_configs[i]
            actual_contacts = config["contacts"]
            actual_orgs = config["orgs"]
            actual_interactions = config["interactions"]
            actual_queries = config["queries"]
            pattern = config["query_pattern"]
            actual_spike_prob = config["spike_probability"]
        else:
            actual_contacts = contacts_per_tenant
            actual_orgs = orgs_per_tenant
            actual_interactions = interactions_per_tenant
            actual_queries = queries_per_tenant
            pattern = query_patterns[i % len(query_patterns)]
            actual_spike_prob = spike_probability

        # Seed data
        print_flush(f"\n[{i + 1}/{num_tenants}] Creating tenant {tenant_id}...")
        if tenant_configs:
            print_flush(
                f"  Persona: {config.get('persona', 'standard')}, "
                f"Contacts: {actual_contacts}, Queries: {actual_queries}"
            )
        # Check for shutdown before seeding
        if is_shutting_down():
            print_flush(f"Shutdown requested, stopping at tenant {i + 1}/{num_tenants}")
            break
        seed_tenant_data(
            tenant_id,
            num_contacts=actual_contacts,
            num_orgs=actual_orgs,
            num_interactions=actual_interactions,
        )

        print_flush(f"Running {actual_queries} queries ({pattern} pattern)...")
        # Get tenant persona for advanced patterns
        tenant_persona = config.get("persona", "established") if tenant_configs else "established"
        durations = simulate_tenant_workload(
            tenant_id,
            actual_queries,
            pattern,
            spike_probability=actual_spike_prob,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            use_advanced_patterns=use_advanced_patterns,
            tenant_persona=tenant_persona,
        )
        all_durations.extend(durations)

        avg_duration = sum(durations) / len(durations)
        sorted_durations = sorted(durations)
        p95 = sorted_durations[int(len(durations) * 0.95)]
        p99 = sorted_durations[int(len(durations) * 0.99)]

        print(f"  Avg: {avg_duration:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")

    # Calculate overall statistics
    overall_avg = sum(all_durations) / len(all_durations)
    sorted_all = sorted(all_durations)
    overall_p95 = sorted_all[int(len(sorted_all) * 0.95)]
    overall_p99 = sorted_all[int(len(sorted_all) * 0.99)]

    print_flush("\n" + "=" * 60)
    print_flush("OVERALL BASELINE STATISTICS")
    print_flush("=" * 60)
    print_flush(f"Total queries: {len(all_durations):,}")
    print_flush(f"Average: {overall_avg:.2f}ms")
    print_flush(f"P95: {overall_p95:.2f}ms")
    print_flush(f"P99: {overall_p99:.2f}ms")

    # Save results
    results = {
        "phase": "baseline",
        "num_tenants": num_tenants,
        "queries_per_tenant": queries_per_tenant,
        "total_queries": len(all_durations),
        "contacts_per_tenant": contacts_per_tenant,
        "orgs_per_tenant": orgs_per_tenant,
        "interactions_per_tenant": interactions_per_tenant,
        "overall_avg_ms": overall_avg,
        "overall_p95_ms": overall_p95,
        "overall_p99_ms": overall_p99,
        "timestamp": datetime.now().isoformat(),
    }

    from src.paths import get_report_path

    results_path = get_report_path("results_baseline.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Final flush of any remaining stats
    flush_query_stats()
    print(f"\nBaseline simulation complete. Results saved to {results_path}")
    return tenant_ids


def _seed_historical_query_stats(
    tenant_ids, contacts_per_tenant, orgs_per_tenant, interactions_per_tenant
):
    """Seed historical query stats spanning 2-3 days for pattern detection"""
    from datetime import datetime, timedelta

    query_patterns = ["email", "phone", "industry", "mixed"]
    # Generate stats for the last 3 days
    days_back = 3
    queries_per_day = 50  # Minimum queries per day for pattern detection

    print_flush(f"  Seeding {days_back} days of historical query stats...")

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            stats_to_insert = []
            total_tenants = len(tenant_ids)
            total_days = days_back

            for day_offset in range(days_back):
                # Calculate date for this day
                target_date = datetime.now() - timedelta(days=day_offset)
                # Distribute queries throughout the day (morning, afternoon, evening)
                hours_in_day = [9, 12, 15, 18, 21]  # Spread across day

                for tenant_idx, tenant_id in enumerate(tenant_ids):
                    # Progress output every 5 tenants or first/last
                    if tenant_idx % 5 == 0 or tenant_idx == 0 or tenant_idx == total_tenants - 1:
                        print_flush(
                            f"    Day {day_offset + 1}/{total_days}, Tenant {tenant_idx + 1}/{total_tenants}..."
                        )
                    pattern = query_patterns[tenant_idx % len(query_patterns)]

                    # Generate queries for this tenant/day
                    queries_this_day = queries_per_day + random.randint(-10, 20)  # Some variation

                    for hour in hours_in_day:
                        queries_this_hour = queries_this_day // len(hours_in_day)
                        for _ in range(queries_this_hour):
                            # Create timestamp for this query
                            minute = random.randint(0, 59)
                            query_time = target_date.replace(
                                hour=hour, minute=minute, second=random.randint(0, 59)
                            )

                            # Determine table/field based on pattern
                            if pattern == "email":
                                table_name, field_name = "contacts", "email"
                                duration_ms = random.uniform(0.8, 2.5)
                            elif pattern == "phone":
                                table_name, field_name = "contacts", "phone"
                                duration_ms = random.uniform(0.9, 2.8)
                            elif pattern == "industry":
                                table_name, field_name = "organizations", "industry"
                                duration_ms = random.uniform(0.7, 2.2)
                            else:  # mixed
                                # Randomly pick a field
                                fields = [
                                    ("contacts", "email"),
                                    ("contacts", "phone"),
                                    ("organizations", "industry"),
                                    ("contacts", "custom_text_1"),
                                    ("interactions", "type"),
                                ]
                                table_name, field_name = random.choice(fields)
                                duration_ms = random.uniform(0.8, 3.0)

                            # Insert with explicit timestamp
                            stats_to_insert.append(
                                (
                                    str(tenant_id),
                                    table_name,
                                    field_name,
                                    "READ",
                                    duration_ms,
                                    query_time,  # Explicit timestamp
                                )
                            )

            # Bulk insert with explicit timestamps
            if stats_to_insert:
                print_flush(f"    Inserting {len(stats_to_insert)} query stats...")
                cursor.executemany(
                    """
                    INSERT INTO query_stats
                    (tenant_id, table_name, field_name, query_type, duration_ms, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    stats_to_insert,
                )
                conn.commit()
                print_flush(
                    f"  Seeded {len(stats_to_insert)} historical query stats across {days_back} days"
                )
        finally:
            cursor.close()


def run_autoindex_simulation(
    tenant_ids=None,
    queries_per_tenant=200,
    contacts_per_tenant=100,
    orgs_per_tenant=20,
    interactions_per_tenant=200,
    warmup_ratio=0.1,
    spike_probability=0.15,
    spike_multiplier=4.0,
    spike_duration=30,
    scenario_name=None,
):
    """Run simulation with auto-indexing enabled"""
    print_flush("=" * 60)
    print_flush("AUTO-INDEX SIMULATION")
    if scenario_name:
        print_flush(f"Scenario: {scenario_name}")
    print_flush("=" * 60)
    print(
        f"Configuration: {len(tenant_ids) if tenant_ids else 'NEW'} tenants, {queries_per_tenant} queries/tenant"
    )
    print(
        f"Data scale: {contacts_per_tenant} contacts, {orgs_per_tenant} orgs, {interactions_per_tenant} interactions per tenant"
    )
    if spike_probability > 0:
        print(
            f"Traffic spikes: {spike_probability * 100:.0f}% probability, {spike_multiplier}x multiplier, {spike_duration} queries duration"
        )
    print("=" * 60)

    if tenant_ids is None:
        # Create new tenants if none provided
        tenant_ids = []
        query_patterns = ["email", "phone", "industry", "mixed"]
        num_tenants = 10

        for i in range(num_tenants):
            tenant_id = create_tenant(f"Tenant Auto {i + 1}")
            tenant_ids.append(tenant_id)
            print(f"[{i + 1}/{num_tenants}] Creating tenant {tenant_id}...")
            seed_tenant_data(
                tenant_id,
                num_contacts=contacts_per_tenant,
                num_orgs=orgs_per_tenant,
                num_interactions=interactions_per_tenant,
            )

    # Seed historical query stats (2-3 days) for pattern detection
    print("\n" + "=" * 60)
    print("SEEDING HISTORICAL QUERY STATS (2-3 days)...")
    print("=" * 60)
    _seed_historical_query_stats(
        tenant_ids, contacts_per_tenant, orgs_per_tenant, interactions_per_tenant
    )

    # Warmup phase - run some queries to collect stats
    print("\n" + "=" * 60)
    print("WARMUP PHASE - Collecting query statistics...")
    print("=" * 60)
    query_patterns = ["email", "phone", "industry", "mixed"]
    warmup_queries = max(
        int(queries_per_tenant * warmup_ratio), 100
    )  # At least 100 queries for warmup

    for i, tenant_id in enumerate(tenant_ids):
        pattern = query_patterns[i % len(query_patterns)]
        if (i + 1) % 10 == 0 or i == 0:
            print(
                f"  Warming up tenant {tenant_id} ({pattern} pattern, {warmup_queries} queries)..."
            )
        simulate_tenant_workload(
            tenant_id,
            warmup_queries,
            pattern,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
        )

    # Run auto-indexer (this will invoke all algorithms)
    print("\n" + "=" * 60)
    print("ANALYZING QUERY PATTERNS AND CREATING INDEXES...")
    print("=" * 60)
    print("  Note: This will test all integrated algorithms:")
    print("    - Predictive Indexing (ML)")
    print("    - CERT (Cardinality Estimation)")
    print("    - QPG (Query Plan Guidance)")
    print("    - Cortex (Correlation Detection)")
    print("    - XGBoost (Pattern Classification)")
    print("    - Constraint Optimizer")
    print("    - Index Type Selection (PGM, ALEX, etc.)")
    # Scale threshold based on number of tenants and queries
    # Lower threshold for smaller datasets - use 5% of warmup queries per tenant
    min_threshold = max(10, int(warmup_queries * 0.05))  # 5% of warmup queries per tenant
    print(f"  Using minimum query threshold: {min_threshold}")
    index_results = analyze_and_create_indexes(
        time_window_hours=1, min_query_threshold=min_threshold
    )
    print("\nIndex Creation Summary:")
    print(f"  Created: {len(index_results['created'])} indexes")
    print(f"  Skipped: {len(index_results['skipped'])} candidates")

    # Check algorithm usage
    try:
        from src.algorithm_tracking import get_algorithm_usage_stats

        algo_stats = get_algorithm_usage_stats(limit=50)
        if algo_stats:
            print(f"\n  Algorithm Usage: {len(algo_stats)} algorithm calls tracked")
            algo_counts: dict[str, int] = {}
            for stat in algo_stats:
                algo_name = stat.get("algorithm_name", "unknown")
                algo_counts[algo_name] = algo_counts.get(algo_name, 0) + 1
            for algo, count in algo_counts.items():
                print(f"    - {algo}: {count} calls")
    except Exception as e:
        print(f"  [INFO] Could not check algorithm usage: {e}")

    if index_results["created"]:
        print("\n  Created indexes:")
        for idx in index_results["created"]:
            print(
                f"    - {idx['table']}.{idx['field']} (queries: {idx['queries']}, cost: {idx['build_cost']:.2f})"
            )

    # Run queries again with indexes in place
    print("\n" + "=" * 60)
    print("RUNNING QUERIES WITH INDEXES...")
    print("=" * 60)
    all_durations = []

    for i, tenant_id in enumerate(tenant_ids):
        pattern = query_patterns[i % len(query_patterns)]
        if (i + 1) % 10 == 0 or i == 0:
            print(f"\nTenant {tenant_id} ({pattern} pattern):")
        durations = simulate_tenant_workload(
            tenant_id,
            queries_per_tenant,
            pattern,
            _use_cache=False,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
        )
        if durations:
            all_durations.extend(durations)

        if (i + 1) % 10 == 0 or i == 0:
            avg_duration = sum(durations) / len(durations)
            sorted_durations = sorted(durations)
            p95 = sorted_durations[int(len(durations) * 0.95)]
            p99 = sorted_durations[int(len(durations) * 0.99)]
            print(f"  Avg: {avg_duration:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")

    # Calculate overall statistics
    overall_avg = sum(all_durations) / len(all_durations)
    sorted_all = sorted(all_durations)
    overall_p95 = sorted_all[int(len(sorted_all) * 0.95)]
    overall_p99 = sorted_all[int(len(sorted_all) * 0.99)]

    print_flush("\n" + "=" * 60)
    print_flush("OVERALL AUTO-INDEX STATISTICS")
    print_flush("=" * 60)
    print_flush(f"Total queries: {len(all_durations):,}")
    print_flush(f"Average: {overall_avg:.2f}ms")
    print_flush(f"P95: {overall_p95:.2f}ms")
    print_flush(f"P99: {overall_p99:.2f}ms")

    # Save results
    results = {
        "phase": "auto_index",
        "num_tenants": len(tenant_ids),
        "queries_per_tenant": queries_per_tenant,
        "total_queries": len(all_durations),
        "contacts_per_tenant": contacts_per_tenant,
        "orgs_per_tenant": orgs_per_tenant,
        "interactions_per_tenant": interactions_per_tenant,
        "warmup_queries": warmup_queries,
        "indexes_created": len(index_results["created"]),
        "indexes_skipped": len(index_results["skipped"]),
        "overall_avg_ms": overall_avg,
        "overall_p95_ms": overall_p95,
        "overall_p99_ms": overall_p99,
        "index_details": index_results["created"],
        "timestamp": datetime.now().isoformat(),
    }

    from src.paths import get_report_path

    results_path = get_report_path("results_with_auto_index.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Final flush of any remaining stats
    flush_query_stats()
    print(f"\nAuto-index simulation complete. Results saved to {results_path}")
    return results


def run_comprehensive_features_for_scenario(
    scenario_name: str,
    num_tenants: int,
    queries_per_tenant: int,
    contacts_per_tenant: int,
    orgs_per_tenant: int,
    interactions_per_tenant: int,
    spike_probability: float,
    spike_multiplier: float,
    spike_duration: int,
) -> JSONDict:
    """
    Run all comprehensive features for a single scenario.

    This function runs:
    - Baseline simulation
    - Auto-index simulation
    - Schema mutations testing
    - A/B testing
    - Predictive maintenance
    - Feature verification

    Args:
        scenario_name: Name of the scenario (for logging)
        num_tenants: Number of tenants
        queries_per_tenant: Queries per tenant
        contacts_per_tenant: Contacts per tenant
        orgs_per_tenant: Organizations per tenant
        interactions_per_tenant: Interactions per tenant
        spike_probability: Probability of traffic spikes
        spike_multiplier: Multiplier for spike traffic
        spike_duration: Duration of spikes in queries

    Returns:
        dict with all feature test results
    """
    import random
    from datetime import datetime

    scenario_results: JSONDict = {
        "scenario": scenario_name,
        "num_tenants": num_tenants,
        "queries_per_tenant": queries_per_tenant,
        "contacts_per_tenant": contacts_per_tenant,
        "orgs_per_tenant": orgs_per_tenant,
        "interactions_per_tenant": interactions_per_tenant,
    }

    # Run baseline simulation
    tenant_ids = run_baseline_simulation(
        num_tenants=num_tenants,
        queries_per_tenant=queries_per_tenant,
        contacts_per_tenant=contacts_per_tenant,
        orgs_per_tenant=orgs_per_tenant,
        interactions_per_tenant=interactions_per_tenant,
        spike_probability=spike_probability,
        spike_multiplier=spike_multiplier,
        spike_duration=spike_duration,
        scenario_name=scenario_name,
    )

    # Run auto-index simulation
    print("\n" + "=" * 80)
    print("Now running auto-index simulation with same tenants...")
    print("=" * 80)
    autoindex_results = run_autoindex_simulation(
        tenant_ids=tenant_ids,
        queries_per_tenant=queries_per_tenant,
        contacts_per_tenant=contacts_per_tenant,
        orgs_per_tenant=orgs_per_tenant,
        interactions_per_tenant=interactions_per_tenant,
        spike_probability=spike_probability,
        spike_multiplier=spike_multiplier,
        spike_duration=spike_duration,
        scenario_name=scenario_name,
    )
    scenario_results["autoindex_results"] = (
        autoindex_results if isinstance(autoindex_results, dict) else {}
    )

    # Test schema mutations during simulation
    print("\n" + "=" * 80)
    print("TESTING SCHEMA MUTATIONS AND AUTO-DETECTION")
    print("=" * 80)

    schema_mutation_results: dict[str, JSONValue] = {}
    try:
        from src.schema_evolution import (
            analyze_schema_change_impact,
            preview_schema_change,
            safe_add_column,
            safe_drop_column,
        )

        # Test 1: Add a test column
        print("\n[SCHEMA TEST] Adding test column to contacts table...")
        try:
            import uuid

            test_field_name = f"simulation_test_field_{uuid.uuid4().hex[:8]}"
            try:
                drop_result = safe_drop_column(
                    table_name="contacts",
                    field_name=test_field_name,
                    force=True,
                )
                if drop_result.get("success"):
                    print(f"  [INFO] Cleaned up existing test column '{test_field_name}'")
            except Exception:
                pass

            add_result = safe_add_column(
                table_name="contacts",
                field_name=test_field_name,
                field_type="TEXT",
                is_nullable=True,
            )
            if add_result.get("success"):
                print("  [OK] Test column added successfully")
                schema_mutation_results["add_column"] = {"success": True}
            else:
                error_msg = add_result.get("error", "")
                if "already exists" in str(error_msg).lower():
                    print("  [OK] Test column already exists (from previous run)")
                    schema_mutation_results["add_column"] = {
                        "success": True,
                        "note": "Column already existed",
                    }
                else:
                    print(f"  [WARNING] Failed: {error_msg}")
                    schema_mutation_results["add_column"] = {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                print("  [OK] Test column already exists (from previous run)")
                schema_mutation_results["add_column"] = {
                    "success": True,
                    "note": "Column already existed",
                }
            else:
                print(f"  [WARNING] Exception: {e}")
                schema_mutation_results["add_column"] = {"success": False, "error": error_msg}

        # Test 2: Analyze impact of dropping email column
        print("\n[SCHEMA TEST] Analyzing impact of dropping email column...")
        try:
            impact = analyze_schema_change_impact(
                table_name="contacts", field_name="email", change_type="DROP_COLUMN"
            )
            affected_indexes = impact.get("affected_indexes", [])
            affected_indexes_list = affected_indexes if isinstance(affected_indexes, list) else []
            print(
                f"  [OK] Impact analysis: {impact.get('affected_queries', 0)} queries, {len(affected_indexes_list)} indexes"
            )
            schema_mutation_results["impact_analysis"] = {
                "success": True,
                "affected_queries": impact.get("affected_queries", 0),
                "affected_indexes": len(affected_indexes_list),
            }
        except Exception as e:
            print(f"  [WARNING] Exception: {e}")
            schema_mutation_results["impact_analysis"] = {"success": False, "error": str(e)}

        # Test 3: Preview schema change
        print("\n[SCHEMA TEST] Previewing schema change (non-destructive)...")
        try:
            preview = preview_schema_change(
                table_name="contacts",
                change_type="ADD_COLUMN",
                field_name="preview_test_field",
                field_type="INTEGER",
            )
            print(f"  [OK] Preview generated: {preview.get('impact') is not None}")
            schema_mutation_results["preview"] = {"success": True}
        except Exception as e:
            print(f"  [WARNING] Exception: {e}")
            schema_mutation_results["preview"] = {"success": False, "error": str(e)}

        # Test 4: Test error detection
        print("\n[SCHEMA TEST] Testing error detection - invalid column name...")
        try:
            invalid_result = safe_add_column(
                table_name="contacts",
                field_name="'; DROP TABLE contacts; --",
                field_type="TEXT",
            )
            if not invalid_result.get("success"):
                print("  [OK] System correctly rejected invalid column name")
                schema_mutation_results["error_detection"] = {
                    "success": True,
                    "rejected_invalid": True,
                }
            else:
                print("  [WARNING] System should have rejected invalid column name")
                schema_mutation_results["error_detection"] = {
                    "success": False,
                    "rejected_invalid": False,
                }
        except Exception as e:
            print(f"  [OK] System correctly caught error: {type(e).__name__}")
            schema_mutation_results["error_detection"] = {
                "success": True,
                "rejected_invalid": True,
                "error_type": type(e).__name__,
            }

    except ImportError as e:
        print(f"  [WARNING] Schema evolution module not available: {e}")
        schema_mutation_results["error"] = f"Module not available: {e}"
    except Exception as e:
        print(f"  [WARNING] Schema mutation testing failed: {e}")
        schema_mutation_results["error"] = str(e)

    scenario_results["schema_mutation_results"] = schema_mutation_results

    # Test A/B experiments
    print("\n" + "=" * 80)
    print("TESTING A/B EXPERIMENTS")
    print("=" * 80)
    ab_test_results: JSONDict = {}
    try:
        from src.index_lifecycle_advanced import (
            create_ab_experiment,
            get_ab_results,
            record_ab_result,
        )

        if isinstance(autoindex_results, dict) and autoindex_results.get("index_details"):
            test_index = autoindex_results["index_details"][0]
            test_table = test_index.get("table", "contacts")
            test_field = test_index.get("field", "email")

            exp_name = f"sim_{scenario_name}_{test_table}_{test_field}"
            print(f"  Creating A/B experiment: {exp_name}")
            create_ab_experiment(
                experiment_name=exp_name,
                table_name=test_table,
                variant_a={"type": "btree", "columns": [test_field]},
                variant_b={"type": "hash", "columns": [test_field]},
                traffic_split=0.5,
                field_name=test_field,
            )

            print("  Recording A/B test results...")
            for _ in range(10):
                record_ab_result(exp_name, "a", 10.5 + (random.random() * 5))
                record_ab_result(exp_name, "b", 12.3 + (random.random() * 5))

            ab_results = get_ab_results(exp_name)
            if ab_results:
                ab_test_results = {
                    "experiment_created": True,
                    "variant_a_queries": ab_results.get("variant_a", {}).get("query_count", 0),
                    "variant_b_queries": ab_results.get("variant_b", {}).get("query_count", 0),
                    "winner": ab_results.get("winner"),
                }
                print("  [OK] A/B experiment completed")
                print(f"    Variant A: {ab_test_results['variant_a_queries']} queries")
                print(f"    Variant B: {ab_test_results['variant_b_queries']} queries")
                winner_val = ab_results.get("winner")
                if winner_val and isinstance(winner_val, str):
                    print(f"    Winner: Variant {winner_val.upper()}")
    except Exception as e:
        print(f"  [WARNING] A/B testing failed: {e}")
        # Create error dict with proper typing
        error_dict: JSONDict = {"error": str(e)}
        ab_test_results = error_dict

    scenario_results["ab_test_results"] = ab_test_results

    # Test predictive maintenance
    print("\n" + "=" * 80)
    print("TESTING PREDICTIVE MAINTENANCE")
    print("=" * 80)
    predictive_results: dict[str, JSONValue] = {}
    try:
        from src.index_lifecycle_advanced import run_predictive_maintenance

        print("  Running predictive maintenance analysis...")
        maintenance_report = run_predictive_maintenance(
            bloat_threshold_percent=20.0, prediction_days=7
        )
        if maintenance_report:
            predicted_needs = maintenance_report.get("predicted_reindex_needs", [])
            recommendations = maintenance_report.get("recommendations", [])
            predictive_results = {
                "predicted_reindex_needs": len(predicted_needs),
                "recommendations": len(recommendations),
                "report_generated": True,
            }
            print("  [OK] Predictive maintenance report generated")
            print(f"    Predicted REINDEX needs: {len(predicted_needs)}")
            print(f"    Recommendations: {len(recommendations)}")
    except Exception as e:
        print(f"  [WARNING] Predictive maintenance failed: {e}")
        predictive_results = {
            "predicted_reindex_needs": 0,
            "recommendations": 0,
            "report_generated": False,
            "error": str(e),
        }

    scenario_results["predictive_maintenance_results"] = predictive_results

    # Run comprehensive feature verification
    print("\n" + "=" * 80)
    print("RUNNING COMPREHENSIVE FEATURE VERIFICATION")
    print("=" * 80)

    from src.simulation.simulation_verification import verify_all_features

    min_indexes = (
        len(autoindex_results.get("index_details", []))
        if isinstance(autoindex_results, dict)
        else 0
    )
    verification_results = verify_all_features(tenant_ids=tenant_ids, min_indexes=min_indexes)
    # Type cast: ComprehensiveVerificationResults is compatible with JSONValue
    scenario_results["verification_results"] = cast(JSONValue, verification_results)

    scenario_results["timestamp"] = datetime.now().isoformat()

    return scenario_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="IndexPilot Simulation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  small       - Small SaaS (startup, 10-50 customers) - ~2 minutes
  medium      - Medium SaaS (growing business, 100-500 customers) - ~10 minutes [DEFAULT]
  large       - Large SaaS (established business, 1000+ customers) - ~45 minutes
  stress-test - Stress test (maximum load, 10,000+ customers) - ~3 hours

Examples:
  # Run medium scenario (default)
  python -m src.simulation.simulator baseline
  python -m src.simulation.simulator autoindex

  # Run specific scenario
  python -m src.simulation.simulator baseline --scenario small
  python -m src.simulation.simulator baseline --scenario large

  # Run stress test
  python -m src.simulation.simulator baseline --scenario stress-test

  # Comprehensive mode (tests all features)
  python -m src.simulation.simulator comprehensive --scenario small
  python -m src.simulation.simulator comprehensive --scenario medium
  python -m src.simulation.simulator comprehensive --scenario large

  # Custom parameters (overrides scenario)
  python -m src.simulation.simulator baseline --tenants 20 --queries 500 --contacts 2000

  # Real-data mode (stock market data)
  python -m src.simulation.simulator real-data --data-dir data/backtesting --timeframe 5min
  python -m src.simulation.simulator real-data --stocks WIPRO,TCS,ITC --queries 1000
        """,
    )

    parser.add_argument(
        "mode",
        choices=["baseline", "autoindex", "scaled", "comprehensive", "real-data"],
        help="Simulation mode",
    )
    parser.add_argument(
        "--scenario",
        choices=["small", "medium", "large", "stress-test"],
        default="medium",
        help="Scenario to run (default: medium)",
    )
    parser.add_argument("--tenants", type=int, help="Number of tenants (overrides scenario)")
    parser.add_argument("--queries", type=int, help="Queries per tenant (overrides scenario)")
    parser.add_argument("--contacts", type=int, help="Contacts per tenant (overrides scenario)")
    parser.add_argument("--orgs", type=int, help="Organizations per tenant (overrides scenario)")
    parser.add_argument(
        "--interactions", type=int, help="Interactions per tenant (overrides scenario)"
    )
    # Real-data mode arguments
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/backtesting",
        help="Directory containing stock market CSV files (default: data/backtesting)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="5min",
        choices=["1min", "5min", "1d"],
        help="Timeframe for stock data (default: 5min)",
    )
    parser.add_argument(
        "--stocks",
        type=str,
        help="Comma-separated list of stock symbols (e.g., WIPRO,TCS,ITC). If not provided, uses all available stocks.",
    )

    args = parser.parse_args()

    # For real-data mode, skip scenario setup
    if args.mode == "real-data":
        # Real-data mode uses different parameters
        queries_per_tenant = args.queries if args.queries else 500
        num_tenants = None  # Not used in real-data mode
        contacts_per_tenant = None
        orgs_per_tenant = None
        interactions_per_tenant = None
        spike_probability = 0.0
        spike_multiplier = 1.0
        spike_duration = 0
        # Note: argparse automatically converts --data-dir to args.data_dir
        # Default values are set in add_argument() above
    else:
        # Get scenario configuration for CRM modes
        scenario = SCENARIOS[args.scenario]
        print_flush(f"\n{'=' * 60}")
        print_flush(f"SCENARIO: {args.scenario.upper()}")
        print_flush(f"Description: {scenario['description']}")
        print_flush(f"Estimated time: ~{scenario['estimated_time_minutes']} minutes")
        print_flush(f"{'=' * 60}\n")

        # Use scenario defaults, but allow overrides
        num_tenants = args.tenants if args.tenants else scenario["num_tenants"]
        queries_per_tenant = args.queries if args.queries else scenario["queries_per_tenant"]
        contacts_per_tenant = args.contacts if args.contacts else scenario["contacts_per_tenant"]
        orgs_per_tenant = args.orgs if args.orgs else scenario["orgs_per_tenant"]
        interactions_per_tenant = (
            args.interactions if args.interactions else scenario["interactions_per_tenant"]
        )
        # Type narrowing: ensure all parameters are proper types (default values if None/Any)
        num_tenants = num_tenants if isinstance(num_tenants, int) else 10
        queries_per_tenant = queries_per_tenant if isinstance(queries_per_tenant, int) else 200
        contacts_per_tenant = contacts_per_tenant if isinstance(contacts_per_tenant, int) else 100
        orgs_per_tenant = orgs_per_tenant if isinstance(orgs_per_tenant, int) else 20
        interactions_per_tenant = (
            interactions_per_tenant if isinstance(interactions_per_tenant, int) else 200
        )
        # Type narrowing: SCENARIOS values are dicts with specific types
        # Cast to proper types since SCENARIOS dict values are not fully typed
        spike_probability = cast(float, scenario["spike_probability"])
        spike_multiplier = cast(float, scenario["spike_multiplier"])
        spike_duration = cast(int, scenario["spike_duration_queries"])

    # Run simulation based on mode
    if args.mode == "baseline":
        # Type narrowing: ensure all parameters are proper types
        num_tenants_val = num_tenants if isinstance(num_tenants, int) else 10
        queries_per_tenant_val = queries_per_tenant if isinstance(queries_per_tenant, int) else 200
        contacts_per_tenant_val = (
            contacts_per_tenant if isinstance(contacts_per_tenant, int) else 100
        )
        orgs_per_tenant_val = orgs_per_tenant if isinstance(orgs_per_tenant, int) else 20
        interactions_per_tenant_val = (
            interactions_per_tenant if isinstance(interactions_per_tenant, int) else 200
        )
        run_baseline_simulation(
            num_tenants=num_tenants_val,
            queries_per_tenant=queries_per_tenant_val,
            contacts_per_tenant=contacts_per_tenant_val,
            orgs_per_tenant=orgs_per_tenant_val,
            interactions_per_tenant=interactions_per_tenant_val,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario,
        )
    elif args.mode == "autoindex":
        # Type narrowing: ensure all parameters are proper types
        queries_per_tenant_val = queries_per_tenant if isinstance(queries_per_tenant, int) else 200
        contacts_per_tenant_val = (
            contacts_per_tenant if isinstance(contacts_per_tenant, int) else 100
        )
        orgs_per_tenant_val = orgs_per_tenant if isinstance(orgs_per_tenant, int) else 20
        interactions_per_tenant_val = (
            interactions_per_tenant if isinstance(interactions_per_tenant, int) else 200
        )
        run_autoindex_simulation(
            tenant_ids=None,
            queries_per_tenant=queries_per_tenant_val,
            contacts_per_tenant=contacts_per_tenant_val,
            orgs_per_tenant=orgs_per_tenant_val,
            interactions_per_tenant=interactions_per_tenant_val,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario,
        )
    elif args.mode == "scaled":
        # Run both baseline and auto-index
        print(f"Running SCALED simulation with {args.scenario} scenario")
        # Type narrowing: ensure all parameters are proper types
        num_tenants_val = num_tenants if isinstance(num_tenants, int) else 10
        queries_per_tenant_val = queries_per_tenant if isinstance(queries_per_tenant, int) else 200
        contacts_per_tenant_val = (
            contacts_per_tenant if isinstance(contacts_per_tenant, int) else 100
        )
        orgs_per_tenant_val = orgs_per_tenant if isinstance(orgs_per_tenant, int) else 20
        interactions_per_tenant_val = (
            interactions_per_tenant if isinstance(interactions_per_tenant, int) else 200
        )
        tenant_ids = run_baseline_simulation(
            num_tenants=num_tenants_val,
            queries_per_tenant=queries_per_tenant_val,
            contacts_per_tenant=contacts_per_tenant_val,
            orgs_per_tenant=orgs_per_tenant_val,
            interactions_per_tenant=interactions_per_tenant_val,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario,
        )
        print("\n" + "=" * 80)
        print("Now running auto-index simulation with same tenants...")
        print("=" * 80)
        run_autoindex_simulation(
            tenant_ids=tenant_ids,
            queries_per_tenant=queries_per_tenant_val,
            contacts_per_tenant=contacts_per_tenant_val,
            orgs_per_tenant=orgs_per_tenant_val,
            interactions_per_tenant=interactions_per_tenant_val,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario,
        )
    elif args.mode == "comprehensive":
        # Run comprehensive simulation with feature verification
        # Comprehensive mode runs ALL scenarios (small, medium, large, stress-test)
        # to test all features across different database sizes
        print("=" * 80)
        print("COMPREHENSIVE SIMULATION MODE")
        print("=" * 80)
        print("This mode will run ALL scenarios (small, medium, large, stress-test)")
        print("Each scenario tests all product features")
        print("=" * 80)

        all_scenario_results = {}

        # Determine which scenarios to run
        # If --scenario is specified, run only that scenario
        # Otherwise, run all scenarios
        scenarios_to_run = (
            [args.scenario] if args.scenario else ["small", "medium", "large", "stress-test"]
        )

        # Run each scenario
        for scenario_name in scenarios_to_run:
            print("\n" + "=" * 80)
            print(f"RUNNING SCENARIO: {scenario_name.upper()}")
            print("=" * 80)

            scenario = SCENARIOS[scenario_name]
            print(f"Description: {scenario['description']}")
            print(f"Estimated time: ~{scenario['estimated_time_minutes']} minutes")
            print("=" * 80)

            # Get scenario parameters with type narrowing
            scenario_num_tenants_val = scenario.get("num_tenants")
            scenario_queries_per_tenant_val = scenario.get("queries_per_tenant")
            scenario_contacts_per_tenant_val = scenario.get("contacts_per_tenant")
            scenario_orgs_per_tenant_val = scenario.get("orgs_per_tenant")
            scenario_interactions_per_tenant_val = scenario.get("interactions_per_tenant")
            scenario_spike_probability_val = scenario.get("spike_probability")
            scenario_spike_multiplier_val = scenario.get("spike_multiplier")
            scenario_spike_duration_val = scenario.get("spike_duration_queries")

            # Type narrowing: ensure all parameters are proper types
            num_tenants_int = (
                scenario_num_tenants_val if isinstance(scenario_num_tenants_val, int) else 10
            )
            queries_per_tenant_int = (
                scenario_queries_per_tenant_val
                if isinstance(scenario_queries_per_tenant_val, int)
                else 200
            )
            contacts_per_tenant_int = (
                scenario_contacts_per_tenant_val
                if isinstance(scenario_contacts_per_tenant_val, int)
                else 100
            )
            orgs_per_tenant_int = (
                scenario_orgs_per_tenant_val
                if isinstance(scenario_orgs_per_tenant_val, int)
                else 20
            )
            interactions_per_tenant_int = (
                scenario_interactions_per_tenant_val
                if isinstance(scenario_interactions_per_tenant_val, int)
                else 200
            )
            spike_probability_float = (
                scenario_spike_probability_val
                if isinstance(scenario_spike_probability_val, float)
                else 0.1
            )
            spike_multiplier_float = (
                scenario_spike_multiplier_val
                if isinstance(scenario_spike_multiplier_val, float)
                else 1.0
            )
            spike_duration_int = (
                scenario_spike_duration_val if isinstance(scenario_spike_duration_val, int) else 20
            )

            # Run all features for this scenario
            try:
                scenario_result = run_comprehensive_features_for_scenario(
                    scenario_name=scenario_name,
                    num_tenants=num_tenants_int,
                    queries_per_tenant=queries_per_tenant_int,
                    contacts_per_tenant=contacts_per_tenant_int,
                    orgs_per_tenant=orgs_per_tenant_int,
                    interactions_per_tenant=interactions_per_tenant_int,
                    spike_probability=spike_probability_float,
                    spike_multiplier=spike_multiplier_float,
                    spike_duration=spike_duration_int,
                )
                all_scenario_results[scenario_name] = scenario_result
                print(f"\n[OK] Scenario '{scenario_name}' completed successfully")
            except Exception as e:
                print(f"\n[ERROR] Scenario '{scenario_name}' failed: {e}")
                import traceback

                traceback.print_exc()
                all_scenario_results[scenario_name] = {"error": str(e), "success": False}

        # Save comprehensive results for all scenarios
        from src.paths import get_report_path

        comprehensive_results = {
            "scenarios_run": scenarios_to_run,
            "scenario_results": all_scenario_results,
            "timestamp": datetime.now().isoformat(),
        }

        results_path = get_report_path("results_comprehensive.json")
        with open(results_path, "w") as f:
            json.dump(comprehensive_results, f, indent=2, default=str)

        print("\n" + "=" * 80)
        print("COMPREHENSIVE SIMULATION COMPLETE")
        print("=" * 80)
        print(f"Results saved to {results_path}")
        print(f"Scenarios run: {', '.join(scenarios_to_run)}")

        # Print summary
        successful_scenarios = []
        for name, result in all_scenario_results.items():
            # Type narrowing: ensure result is a dict
            if isinstance(result, dict):
                verification_results = result.get("verification_results")
                if isinstance(verification_results, dict):
                    summary = verification_results.get("summary")
                    if isinstance(summary, dict):
                        all_passed = summary.get("all_passed", False)
                        if isinstance(all_passed, bool) and all_passed:
                            successful_scenarios.append(name)
        if successful_scenarios:
            print(
                f"\n[SUCCESS] Scenarios with all verifications passed: {', '.join(successful_scenarios)}"
            )
        else:
            print("\n[WARNING] Some scenarios had verification issues. Check details above.")
    elif args.mode == "real-data":
        # Real-data mode: Use stock market data
        from src.simulation.stock_simulator import get_available_stocks, simulate_stock_workload
        from src.stock_data_loader import load_stock_data

        print("=" * 80)
        print("REAL-DATA SIMULATION MODE")
        print("=" * 80)
        print(f"Using stock market data from: {args.data_dir}")
        print(f"Timeframe: {args.timeframe}")

        # Parse stocks if provided
        stock_symbols = None
        if args.stocks:
            stock_symbols = [s.strip().upper() for s in args.stocks.split(",")]
            print(f"Stocks: {', '.join(stock_symbols)}")
        else:
            print("Stocks: All available stocks")

        # Load initial data (first 50%)
        print("\nLoading initial stock data (first 50%)...")
        try:
            load_result = load_stock_data(
                data_dir=args.data_dir,
                timeframe=args.timeframe,
                mode="initial",
                stocks=stock_symbols,
            )
            print(
                f"Loaded {load_result['total_rows_loaded']} rows from {load_result['stocks_processed']} stocks"
            )
        except Exception as e:
            print(f"ERROR: Failed to load stock data: {e}")
            sys.exit(1)

        # Get stock IDs for simulation
        stocks = get_available_stocks()
        if stock_symbols:
            stocks = [s for s in stocks if s["symbol"] in stock_symbols]
        # Type narrowing: ensure stock_ids contains only ints
        stock_ids: list[int] = []
        for s in stocks:
            stock_id = s.get("id")
            if isinstance(stock_id, int):
                stock_ids.append(stock_id)

        if not stock_ids:
            print("ERROR: No stocks available for simulation")
            sys.exit(1)

        # Determine number of queries
        num_queries = queries_per_tenant if queries_per_tenant else 500

        # Run baseline simulation (no auto-indexing)
        print("\n" + "=" * 80)
        print("Running BASELINE simulation (no auto-indexing)")
        print("=" * 80)
        baseline_durations = simulate_stock_workload(
            num_queries=num_queries,
            stock_ids=stock_ids,
            query_pattern="mixed",
        )

        baseline_avg = (
            sum(baseline_durations) / len(baseline_durations) if baseline_durations else 0
        )
        print("\nBaseline Results:")
        print(f"  Queries: {len(baseline_durations)}")
        print(f"  Avg Duration: {baseline_avg:.2f}ms")

        # Run autoindex simulation
        print("\n" + "=" * 80)
        print("Running AUTOINDEX simulation (with IndexPilot)")
        print("=" * 80)

        # Trigger index analysis
        print("Analyzing query patterns and creating indexes...")
        index_results = analyze_and_create_indexes()
        if index_results:
            print(
                f"Index analysis complete: {len(index_results.get('indexes_created', []))} indexes created"
            )

        # Run queries with indexes
        autoindex_durations = simulate_stock_workload(
            num_queries=num_queries,
            stock_ids=stock_ids,
            query_pattern="mixed",
        )

        autoindex_avg = (
            sum(autoindex_durations) / len(autoindex_durations) if autoindex_durations else 0
        )
        print("\nAutoindex Results:")
        print(f"  Queries: {len(autoindex_durations)}")
        print(f"  Avg Duration: {autoindex_avg:.2f}ms")

        # Calculate improvement
        improvement: float = 0.0
        if baseline_durations and baseline_avg > 0:
            improvement = (baseline_avg - autoindex_avg) / baseline_avg * 100

        if improvement > 0:
            print(f"\nPerformance Improvement: {improvement:.1f}%")
        else:
            print(f"\nPerformance Change: {improvement:.1f}%")

        # Save results
        results = {
            "mode": "real-data",
            "timeframe": args.timeframe,
            "stocks": [s["symbol"] for s in stocks],
            "baseline": {
                "queries": len(baseline_durations),
                "avg_duration_ms": baseline_avg,
            },
            "autoindex": {
                "queries": len(autoindex_durations),
                "avg_duration_ms": autoindex_avg,
            },
            "improvement_pct": improvement,
            "indexes_created": len(index_results.get("indexes_created", []))
            if index_results
            else 0,
        }

        from src.paths import get_report_path

        results_path = get_report_path("results_real_data.json")
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {results_path}")
