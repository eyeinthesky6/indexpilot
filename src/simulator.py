"""Simulation harness - load generation and benchmark"""

import atexit
import json
import logging
import random
import time
from datetime import datetime, timedelta

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

# Validate production configuration at startup
try:
    config = validate_production_config()
    log_level_val = config.get('LOG_LEVEL', 'INFO')
    log_level = log_level_val.upper() if isinstance(log_level_val, str) else 'INFO'
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
except ValueError as e:
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"Configuration validation failed: {e}")
    raise

logger = logging.getLogger(__name__)

# Set up graceful shutdown handlers
setup_graceful_shutdown()

# Scenario configurations based on real-world patterns
SCENARIOS = {
    'small': {
        'description': 'Small SaaS (startup, 10-50 customers)',
        'num_tenants': 10,
        'contacts_per_tenant': 500,
        'orgs_per_tenant': 50,
        'interactions_per_tenant': 1000,
        'queries_per_tenant': 200,
        'spike_probability': 0.1,  # 10% chance of spike
        'spike_multiplier': 3.0,  # 3x normal traffic during spike
        'spike_duration_queries': 20,  # Spike lasts 20 queries
        'estimated_time_minutes': 2
    },
    'medium': {
        'description': 'Medium SaaS (growing business, 100-500 customers)',
        'num_tenants': 50,
        'contacts_per_tenant': 2000,
        'orgs_per_tenant': 200,
        'interactions_per_tenant': 5000,
        'queries_per_tenant': 500,
        'spike_probability': 0.15,  # 15% chance of spike
        'spike_multiplier': 4.0,  # 4x normal traffic during spike
        'spike_duration_queries': 30,  # Spike lasts 30 queries
        'estimated_time_minutes': 10
    },
    'large': {
        'description': 'Large SaaS (established business, 1000+ customers)',
        'num_tenants': 100,
        'contacts_per_tenant': 10000,
        'orgs_per_tenant': 1000,
        'interactions_per_tenant': 20000,
        'queries_per_tenant': 1000,
        'spike_probability': 0.2,  # 20% chance of spike
        'spike_multiplier': 5.0,  # 5x normal traffic during spike
        'spike_duration_queries': 50,  # Spike lasts 50 queries
        'estimated_time_minutes': 45
    },
    'stress-test': {
        'description': 'Stress test (maximum load, 10,000+ customers)',
        'num_tenants': 200,
        'contacts_per_tenant': 50000,
        'orgs_per_tenant': 5000,
        'interactions_per_tenant': 100000,
        'queries_per_tenant': 2000,
        'spike_probability': 0.3,  # 30% chance of spike
        'spike_multiplier': 10.0,  # 10x normal traffic during spike
        'spike_duration_queries': 100,  # Spike lasts 100 queries
        'estimated_time_minutes': 180
    }
}

# Get configuration values
prod_config = get_config()
min_conn = prod_config.get_int('MIN_CONNECTIONS', 2)
max_conn = prod_config.get_int('MAX_CONNECTIONS', 20)

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
        if is_feature_enabled('auto_indexing'):
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
        import time

        maintenance_interval = prod_config.get_int('MAINTENANCE_INTERVAL', 3600)
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
    logger.info(f"Maintenance background thread started (interval: {prod_config.get_int('MAINTENANCE_INTERVAL', 3600)}s)")

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
            cursor.execute("""
                INSERT INTO tenants (name)
                VALUES (%s)
                RETURNING id
            """, (name,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Failed to create tenant {name}: no ID returned")
            tenant_id = result['id']
            conn.commit()

            # Initialize expression profile
            initialize_tenant_expression(tenant_id)

            # Log to audit trail
            log_audit_event(
                'INITIALIZE_TENANT',
                tenant_id=tenant_id,
                details={'tenant_name': name, 'action': 'tenant_created'},
                severity='info'
            )

            return tenant_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def seed_tenant_data(tenant_id, num_contacts=100, num_orgs=20, num_interactions=200, batch_size=1000):
    """Seed data for a tenant (optimized with executemany for bulk inserts)"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
            interaction_types = ['call', 'email', 'meeting', 'note']
            now = datetime.now()

            # Create contacts (bulk insert with executemany)
            contacts = []
            print(f"  Seeding {num_contacts} contacts...")
            for batch_start in range(0, num_contacts, batch_size):
                batch_end = min(batch_start + batch_size, num_contacts)
                batch_data = []

                for i in range(batch_start, batch_end):
                    batch_data.append((
                        tenant_id,
                        f"Contact {i+1}",
                        f"contact{i+1}@example.com",
                        f"555-{1000+i:04d}",
                        f"Custom {i+1}" if i % 3 == 0 else None,
                        random.randint(1, 100) if i % 5 == 0 else None,
                        now - timedelta(days=random.randint(0, 365))
                    ))

                # Bulk insert
                cursor.executemany("""
                    INSERT INTO contacts
                    (tenant_id, name, email, phone, custom_text_1, custom_number_1, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, batch_data)

                # Get IDs for inserted contacts (for foreign keys)
                cursor.execute("""
                    SELECT id FROM contacts
                    WHERE tenant_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                """, (tenant_id, batch_end - batch_start))
                batch_contacts = [row['id'] for row in cursor.fetchall()]
                contacts.extend(batch_contacts)

                if batch_end % (batch_size * 5) == 0 or batch_end == num_contacts:
                    print(f"    Created {batch_end}/{num_contacts} contacts")

            # Create organizations (bulk insert)
            orgs = []
            print(f"  Seeding {num_orgs} organizations...")
            for batch_start in range(0, num_orgs, batch_size):
                batch_end = min(batch_start + batch_size, num_orgs)
                org_batch_data: list[tuple[int, str, str, str | None, datetime]] = []

                for i in range(batch_start, batch_end):
                    org_batch_data.append((
                        tenant_id,
                        f"Org {i+1}",
                        random.choice(industries),
                        f"Org Custom {i+1}" if i % 4 == 0 else None,
                        now - timedelta(days=random.randint(0, 365))
                    ))

                cursor.executemany("""
                    INSERT INTO organizations
                    (tenant_id, name, industry, custom_text_1, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, org_batch_data)

                # Get IDs for inserted orgs
                cursor.execute("""
                    SELECT id FROM organizations
                    WHERE tenant_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                """, (tenant_id, batch_end - batch_start))
                batch_orgs = [row['id'] for row in cursor.fetchall()]
                orgs.extend(batch_orgs)

            # Create interactions (bulk insert)
            print(f"  Seeding {num_interactions} interactions...")
            # Pre-generate random choices for better performance
            contact_choices = contacts if contacts else [None]
            org_choices = orgs if orgs else [None]

            for batch_start in range(0, num_interactions, batch_size):
                batch_end = min(batch_start + batch_size, num_interactions)
                interaction_batch_data: list[tuple[int, int | None, int | None, str, datetime, str]] = []

                for _i in range(batch_start, batch_end):
                    interaction_batch_data.append((
                        tenant_id,
                        random.choice(contact_choices),
                        random.choice(org_choices),
                        random.choice(interaction_types),
                        now - timedelta(days=random.randint(0, 90)),
                        json.dumps({'duration': random.randint(5, 60)})
                    ))

                cursor.executemany("""
                    INSERT INTO interactions
                    (tenant_id, contact_id, org_id, type, occurred_at, metadata_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, interaction_batch_data)

                if batch_end % (batch_size * 5) == 0 or batch_end == num_interactions:
                    print(f"    Created {batch_end}/{num_interactions} interactions")

            conn.commit()
            print(f"Seeded tenant {tenant_id}: {num_contacts} contacts, {num_orgs} orgs, {num_interactions} interactions")
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
                cursor.execute("SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,))
                result = cursor.fetchone()
                max_contact_id = result['max_id'] if result and result['max_id'] else 10000

            contact_num = random.randint(1, min(max_contact_id, 10000))
            email_pattern = f"%contact{contact_num}%"
            cursor.execute("""
                SELECT * FROM contacts
                WHERE tenant_id = %s AND email LIKE %s
                LIMIT 10
            """, (tenant_id, email_pattern))
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(tenant_id, 'contacts', 'email', 'READ', duration_ms, skip_validation=True)
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
                cursor.execute("SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,))
                result = cursor.fetchone()
                max_contact_id = result['max_id'] if result and result['max_id'] else 10000

            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
            phone_pattern = f"555-{phone_num:04d}"
            cursor.execute("""
                SELECT * FROM contacts
                WHERE tenant_id = %s AND phone = %s
                LIMIT 10
            """, (tenant_id, phone_pattern))
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(tenant_id, 'contacts', 'phone', 'READ', duration_ms, skip_validation=True)
            return duration_ms
        finally:
            cursor.close()


def run_query_by_industry(tenant_id):
    """Run a query filtering by industry"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
            industry = random.choice(industries)
            cursor.execute("""
                SELECT * FROM organizations
                WHERE tenant_id = %s AND industry = %s
                LIMIT 10
            """, (tenant_id, industry))
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(tenant_id, 'organizations', 'industry', 'READ', duration_ms, skip_validation=True)
            return duration_ms
        finally:
            cursor.close()


def run_query_by_custom_field(tenant_id):
    """Run a query filtering by custom field"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM contacts
                WHERE tenant_id = %s AND custom_text_1 IS NOT NULL
                LIMIT 10
            """, (tenant_id,))
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(tenant_id, 'contacts', 'custom_text_1', 'READ', duration_ms, skip_validation=True)
            return duration_ms
        finally:
            cursor.close()


def run_query_by_interaction_type(tenant_id):
    """Run a query filtering by interaction type"""
    start = time.time()
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            types = ['call', 'email', 'meeting', 'note']
            interaction_type = random.choice(types)
            cursor.execute("""
                SELECT * FROM interactions
                WHERE tenant_id = %s AND type = %s
                LIMIT 10
            """, (tenant_id, interaction_type))
            _ = cursor.fetchall()  # Execute query to measure real performance
            duration_ms = (time.time() - start) * 1000

            log_query_stat(tenant_id, 'interactions', 'type', 'READ', duration_ms, skip_validation=True)
            return duration_ms
        finally:
            cursor.close()


def simulate_tenant_workload(tenant_id, num_queries=1000, query_pattern='mixed', _use_cache=False,
                            spike_probability=0.15, spike_multiplier=4.0, spike_duration=30):
    """
    Simulate workload for a tenant with a specific query pattern and optional traffic spikes.
    Optimized to reuse database connections within batches.

    Args:
        tenant_id: Tenant ID
        num_queries: Total number of queries to run
        query_pattern: 'email', 'phone', 'industry', or 'mixed'
        _use_cache: Whether to use cached max_contact_id (reserved for future use)
        spike_probability: Probability of entering a spike (0.0-1.0)
        spike_multiplier: Multiplier for queries during spike (e.g., 4.0 = 4x normal)
        spike_duration: Number of queries a spike lasts
    """
    durations = []

    # Cache max_contact_id once at the start
    max_contact_id = None
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT MAX(id) as max_id FROM contacts WHERE tenant_id = %s", (tenant_id,))
            result = cursor.fetchone()
            max_contact_id = result['max_id'] if result and result['max_id'] else 10000
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
        # Check if we should enter a spike
        if not in_spike and random.random() < spike_probability:
            in_spike = True
            spike_queries_remaining = spike_duration
            # Note: spike_started_at removed as it was unused
            print(f"  Tenant {tenant_id}: [SPIKE] DETECTED at query {i+1} (will last {spike_duration} queries)")

        # Determine how many queries to run in this iteration
        if in_spike:
            # During spike, run multiple queries per iteration
            queries_this_iteration = min(
                int(spike_multiplier),
                spike_queries_remaining,
                num_queries - i,
                batch_size  # Limit batch size
            )
            spike_queries_remaining -= queries_this_iteration
            if spike_queries_remaining <= 0:
                in_spike = False
                print(f"  Tenant {tenant_id}: [SPIKE ENDED] at query {i+1}")
        else:
            queries_this_iteration = min(1, num_queries - i)

        # Reuse connection for this batch
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Run queries for this iteration
                for _ in range(queries_this_iteration):
                    start = time.time()
                    table = 'contacts'
                    field = 'email'

                    if query_pattern == 'email':
                        # 80% email, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute("""
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """, (tenant_id, email_pattern))
                            _ = cursor.fetchall()
                            table, field = 'contacts', 'email'
                        else:
                            if random.random() < 0.5:
                                phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                                phone_pattern = f"555-{phone_num:04d}"
                                cursor.execute("""
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND phone = %s
                                    LIMIT 10
                                """, (tenant_id, phone_pattern))
                                _ = cursor.fetchall()
                                table, field = 'contacts', 'phone'
                            else:
                                industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
                                industry = random.choice(industries)
                                cursor.execute("""
                                    SELECT * FROM organizations
                                    WHERE tenant_id = %s AND industry = %s
                                    LIMIT 10
                                """, (tenant_id, industry))
                                _ = cursor.fetchall()
                                table, field = 'organizations', 'industry'
                    elif query_pattern == 'phone':
                        # 80% phone, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                            phone_pattern = f"555-{phone_num:04d}"
                            cursor.execute("""
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND phone = %s
                                LIMIT 10
                            """, (tenant_id, phone_pattern))
                            _ = cursor.fetchall()
                            table, field = 'contacts', 'phone'
                        else:
                            if random.random() < 0.5:
                                contact_num = random.randint(1, min(max_contact_id, 10000))
                                email_pattern = f"%contact{contact_num}%"
                                cursor.execute("""
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND email LIKE %s
                                    LIMIT 10
                                """, (tenant_id, email_pattern))
                                _ = cursor.fetchall()
                                table, field = 'contacts', 'email'
                            else:
                                industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
                                industry = random.choice(industries)
                                cursor.execute("""
                                    SELECT * FROM organizations
                                    WHERE tenant_id = %s AND industry = %s
                                    LIMIT 10
                                """, (tenant_id, industry))
                                _ = cursor.fetchall()
                                table, field = 'organizations', 'industry'
                    elif query_pattern == 'industry':
                        # 80% industry, 20% other
                        rand_val = random.random()
                        if rand_val < 0.8:
                            industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
                            industry = random.choice(industries)
                            cursor.execute("""
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """, (tenant_id, industry))
                            _ = cursor.fetchall()
                            table, field = 'organizations', 'industry'
                        else:
                            if random.random() < 0.5:
                                contact_num = random.randint(1, min(max_contact_id, 10000))
                                email_pattern = f"%contact{contact_num}%"
                                cursor.execute("""
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND email LIKE %s
                                    LIMIT 10
                                """, (tenant_id, email_pattern))
                                _ = cursor.fetchall()
                                table, field = 'contacts', 'email'
                            else:
                                phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                                phone_pattern = f"555-{phone_num:04d}"
                                cursor.execute("""
                                    SELECT * FROM contacts
                                    WHERE tenant_id = %s AND phone = %s
                                    LIMIT 10
                                """, (tenant_id, phone_pattern))
                                _ = cursor.fetchall()
                                table, field = 'contacts', 'phone'
                    else:  # mixed
                        # Balanced distribution
                        rand = random.random()
                        if rand < 0.3:
                            contact_num = random.randint(1, min(max_contact_id, 10000))
                            email_pattern = f"%contact{contact_num}%"
                            cursor.execute("""
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND email LIKE %s
                                LIMIT 10
                            """, (tenant_id, email_pattern))
                            _ = cursor.fetchall()
                            table, field = 'contacts', 'email'
                        elif rand < 0.6:
                            phone_num = random.randint(1000, min(1000 + max_contact_id, 9999))
                            phone_pattern = f"555-{phone_num:04d}"
                            cursor.execute("""
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND phone = %s
                                LIMIT 10
                            """, (tenant_id, phone_pattern))
                            _ = cursor.fetchall()
                            table, field = 'contacts', 'phone'
                        elif rand < 0.8:
                            industries = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']
                            industry = random.choice(industries)
                            cursor.execute("""
                                SELECT * FROM organizations
                                WHERE tenant_id = %s AND industry = %s
                                LIMIT 10
                            """, (tenant_id, industry))
                            _ = cursor.fetchall()
                            table, field = 'organizations', 'industry'
                        elif rand < 0.9:
                            interaction_types = ['call', 'email', 'meeting', 'note']
                            interaction_type = random.choice(interaction_types)
                            cursor.execute("""
                                SELECT * FROM interactions
                                WHERE tenant_id = %s AND type = %s
                                LIMIT 10
                            """, (tenant_id, interaction_type))
                            _ = cursor.fetchall()
                            table, field = 'interactions', 'type'
                        else:
                            cursor.execute("""
                                SELECT * FROM contacts
                                WHERE tenant_id = %s AND custom_text_1 IS NOT NULL
                                LIMIT 10
                            """, (tenant_id,))
                            _ = cursor.fetchall()
                            table, field = 'contacts', 'custom_text_1'

                    duration_ms = (time.time() - start) * 1000
                    log_query_stat(tenant_id, table, field, 'READ', duration_ms, skip_validation=True)
                    durations.append(duration_ms)
                    i += 1
            finally:
                cursor.close()

        # Progress reporting (reduced frequency)
        if num_queries > 50 and (i - last_print) >= 50:
            status = "[SPIKE]" if in_spike else "normal"
            print(f"  Tenant {tenant_id}: Completed {i}/{num_queries} queries ({status})")
            last_print = i
            flush_query_stats()  # Flush stats periodically

    # Flush remaining stats
    flush_query_stats()
    return durations


def run_baseline_simulation(num_tenants=10, queries_per_tenant=200,
                            contacts_per_tenant=100, orgs_per_tenant=20,
                            interactions_per_tenant=200,
                            spike_probability=0.15, spike_multiplier=4.0, spike_duration=30,
                            scenario_name=None):
    """Run baseline simulation without auto-indexing"""
    print("=" * 60)
    print("BASELINE SIMULATION (No Auto-Indexing)")
    if scenario_name:
        print(f"Scenario: {scenario_name}")
    print("=" * 60)
    print(f"Configuration: {num_tenants} tenants, {queries_per_tenant} queries/tenant")
    print(f"Data scale: {contacts_per_tenant} contacts, {orgs_per_tenant} orgs, {interactions_per_tenant} interactions per tenant")
    if spike_probability > 0:
        print(f"Traffic spikes: {spike_probability*100:.0f}% probability, {spike_multiplier}x multiplier, {spike_duration} queries duration")
    print("=" * 60)

    # Create tenants
    tenant_ids = []
    query_patterns = ['email', 'phone', 'industry', 'mixed']
    all_durations = []

    for i in range(num_tenants):
        tenant_id = create_tenant(f"Tenant {i+1}")
        tenant_ids.append(tenant_id)

        # Seed data
        print(f"\n[{i+1}/{num_tenants}] Creating tenant {tenant_id}...")
        seed_tenant_data(tenant_id,
                        num_contacts=contacts_per_tenant,
                        num_orgs=orgs_per_tenant,
                        num_interactions=interactions_per_tenant)

        # Assign query pattern
        pattern = query_patterns[i % len(query_patterns)]

        print(f"Running {queries_per_tenant} queries ({pattern} pattern)...")
        durations = simulate_tenant_workload(tenant_id, queries_per_tenant, pattern,
                                            spike_probability=spike_probability,
                                            spike_multiplier=spike_multiplier,
                                            spike_duration=spike_duration)
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

    print("\n" + "=" * 60)
    print("OVERALL BASELINE STATISTICS")
    print("=" * 60)
    print(f"Total queries: {len(all_durations):,}")
    print(f"Average: {overall_avg:.2f}ms")
    print(f"P95: {overall_p95:.2f}ms")
    print(f"P99: {overall_p99:.2f}ms")

    # Save results
    results = {
        'phase': 'baseline',
        'num_tenants': num_tenants,
        'queries_per_tenant': queries_per_tenant,
        'total_queries': len(all_durations),
        'contacts_per_tenant': contacts_per_tenant,
        'orgs_per_tenant': orgs_per_tenant,
        'interactions_per_tenant': interactions_per_tenant,
        'overall_avg_ms': overall_avg,
        'overall_p95_ms': overall_p95,
        'overall_p99_ms': overall_p99,
        'timestamp': datetime.now().isoformat()
    }

    from src.paths import get_report_path
    results_path = get_report_path('results_baseline.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Final flush of any remaining stats
    flush_query_stats()
    print(f"\nBaseline simulation complete. Results saved to {results_path}")
    return tenant_ids


def _seed_historical_query_stats(tenant_ids, contacts_per_tenant, orgs_per_tenant, interactions_per_tenant):
    """Seed historical query stats spanning 2-3 days for pattern detection"""
    from datetime import datetime, timedelta

    query_patterns = ['email', 'phone', 'industry', 'mixed']
    # Generate stats for the last 3 days
    days_back = 3
    queries_per_day = 50  # Minimum queries per day for pattern detection

    print(f"  Seeding {days_back} days of historical query stats...")

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            stats_to_insert = []

            for day_offset in range(days_back):
                # Calculate date for this day
                target_date = datetime.now() - timedelta(days=day_offset)
                # Distribute queries throughout the day (morning, afternoon, evening)
                hours_in_day = [9, 12, 15, 18, 21]  # Spread across day

                for tenant_idx, tenant_id in enumerate(tenant_ids):
                    pattern = query_patterns[tenant_idx % len(query_patterns)]

                    # Generate queries for this tenant/day
                    queries_this_day = queries_per_day + random.randint(-10, 20)  # Some variation

                    for hour in hours_in_day:
                        queries_this_hour = queries_this_day // len(hours_in_day)
                        for _ in range(queries_this_hour):
                            # Create timestamp for this query
                            minute = random.randint(0, 59)
                            query_time = target_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))

                            # Determine table/field based on pattern
                            if pattern == 'email':
                                table_name, field_name = 'contacts', 'email'
                                duration_ms = random.uniform(0.8, 2.5)
                            elif pattern == 'phone':
                                table_name, field_name = 'contacts', 'phone'
                                duration_ms = random.uniform(0.9, 2.8)
                            elif pattern == 'industry':
                                table_name, field_name = 'organizations', 'industry'
                                duration_ms = random.uniform(0.7, 2.2)
                            else:  # mixed
                                # Randomly pick a field
                                fields = [
                                    ('contacts', 'email'),
                                    ('contacts', 'phone'),
                                    ('organizations', 'industry'),
                                    ('contacts', 'custom_text_1'),
                                    ('interactions', 'type')
                                ]
                                table_name, field_name = random.choice(fields)
                                duration_ms = random.uniform(0.8, 3.0)

                            # Insert with explicit timestamp
                            stats_to_insert.append((
                                str(tenant_id),
                                table_name,
                                field_name,
                                'READ',
                                duration_ms,
                                query_time  # Explicit timestamp
                            ))

            # Bulk insert with explicit timestamps
            if stats_to_insert:
                cursor.executemany("""
                    INSERT INTO query_stats
                    (tenant_id, table_name, field_name, query_type, duration_ms, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, stats_to_insert)
                conn.commit()
                print(f"  Seeded {len(stats_to_insert)} historical query stats across {days_back} days")
        finally:
            cursor.close()


def run_autoindex_simulation(tenant_ids=None, queries_per_tenant=200,
                             contacts_per_tenant=100, orgs_per_tenant=20,
                             interactions_per_tenant=200, warmup_ratio=0.1,
                             spike_probability=0.15, spike_multiplier=4.0, spike_duration=30,
                             scenario_name=None):
    """Run simulation with auto-indexing enabled"""
    print("=" * 60)
    print("AUTO-INDEX SIMULATION")
    if scenario_name:
        print(f"Scenario: {scenario_name}")
    print("=" * 60)
    print(f"Configuration: {len(tenant_ids) if tenant_ids else 'NEW'} tenants, {queries_per_tenant} queries/tenant")
    print(f"Data scale: {contacts_per_tenant} contacts, {orgs_per_tenant} orgs, {interactions_per_tenant} interactions per tenant")
    if spike_probability > 0:
        print(f"Traffic spikes: {spike_probability*100:.0f}% probability, {spike_multiplier}x multiplier, {spike_duration} queries duration")
    print("=" * 60)

    if tenant_ids is None:
        # Create new tenants if none provided
        tenant_ids = []
        query_patterns = ['email', 'phone', 'industry', 'mixed']
        num_tenants = 10

        for i in range(num_tenants):
            tenant_id = create_tenant(f"Tenant Auto {i+1}")
            tenant_ids.append(tenant_id)
            print(f"[{i+1}/{num_tenants}] Creating tenant {tenant_id}...")
            seed_tenant_data(tenant_id,
                            num_contacts=contacts_per_tenant,
                            num_orgs=orgs_per_tenant,
                            num_interactions=interactions_per_tenant)

    # Seed historical query stats (2-3 days) for pattern detection
    print("\n" + "=" * 60)
    print("SEEDING HISTORICAL QUERY STATS (2-3 days)...")
    print("=" * 60)
    _seed_historical_query_stats(tenant_ids, contacts_per_tenant, orgs_per_tenant, interactions_per_tenant)

    # Warmup phase - run some queries to collect stats
    print("\n" + "=" * 60)
    print("WARMUP PHASE - Collecting query statistics...")
    print("=" * 60)
    query_patterns = ['email', 'phone', 'industry', 'mixed']
    warmup_queries = max(int(queries_per_tenant * warmup_ratio), 100)  # At least 100 queries for warmup

    for i, tenant_id in enumerate(tenant_ids):
        pattern = query_patterns[i % len(query_patterns)]
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Warming up tenant {tenant_id} ({pattern} pattern, {warmup_queries} queries)...")
        simulate_tenant_workload(tenant_id, warmup_queries, pattern,
                                spike_probability=spike_probability,
                                spike_multiplier=spike_multiplier,
                                spike_duration=spike_duration)

    # Run auto-indexer
    print("\n" + "=" * 60)
    print("ANALYZING QUERY PATTERNS AND CREATING INDEXES...")
    print("=" * 60)
    # Scale threshold based on number of tenants and queries
    # Lower threshold for smaller datasets - use 5% of warmup queries per tenant
    min_threshold = max(10, int(warmup_queries * 0.05))  # 5% of warmup queries per tenant
    print(f"  Using minimum query threshold: {min_threshold}")
    index_results = analyze_and_create_indexes(time_window_hours=1, min_query_threshold=min_threshold)
    print("\nIndex Creation Summary:")
    print(f"  Created: {len(index_results['created'])} indexes")
    print(f"  Skipped: {len(index_results['skipped'])} candidates")

    if index_results['created']:
        print("\n  Created indexes:")
        for idx in index_results['created']:
            print(f"    - {idx['table']}.{idx['field']} (queries: {idx['queries']}, cost: {idx['build_cost']:.2f})")

    # Run queries again with indexes in place
    print("\n" + "=" * 60)
    print("RUNNING QUERIES WITH INDEXES...")
    print("=" * 60)
    all_durations = []

    for i, tenant_id in enumerate(tenant_ids):
        pattern = query_patterns[i % len(query_patterns)]
        if (i + 1) % 10 == 0 or i == 0:
            print(f"\nTenant {tenant_id} ({pattern} pattern):")
        durations = simulate_tenant_workload(tenant_id, queries_per_tenant, pattern, _use_cache=False,
                                            spike_probability=spike_probability,
                                            spike_multiplier=spike_multiplier,
                                            spike_duration=spike_duration)
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

    print("\n" + "=" * 60)
    print("OVERALL AUTO-INDEX STATISTICS")
    print("=" * 60)
    print(f"Total queries: {len(all_durations):,}")
    print(f"Average: {overall_avg:.2f}ms")
    print(f"P95: {overall_p95:.2f}ms")
    print(f"P99: {overall_p99:.2f}ms")

    # Save results
    results = {
        'phase': 'auto_index',
        'num_tenants': len(tenant_ids),
        'queries_per_tenant': queries_per_tenant,
        'total_queries': len(all_durations),
        'contacts_per_tenant': contacts_per_tenant,
        'orgs_per_tenant': orgs_per_tenant,
        'interactions_per_tenant': interactions_per_tenant,
        'warmup_queries': warmup_queries,
        'indexes_created': len(index_results['created']),
        'indexes_skipped': len(index_results['skipped']),
        'overall_avg_ms': overall_avg,
        'overall_p95_ms': overall_p95,
        'overall_p99_ms': overall_p99,
        'index_details': index_results['created'],
        'timestamp': datetime.now().isoformat()
    }

    from src.paths import get_report_path
    results_path = get_report_path('results_with_auto_index.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Final flush of any remaining stats
    flush_query_stats()
    print(f"\nAuto-index simulation complete. Results saved to {results_path}")
    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='IndexPilot Simulation Harness',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  small       - Small SaaS (startup, 10-50 customers) - ~2 minutes
  medium      - Medium SaaS (growing business, 100-500 customers) - ~10 minutes [DEFAULT]
  large       - Large SaaS (established business, 1000+ customers) - ~45 minutes
  stress-test - Stress test (maximum load, 10,000+ customers) - ~3 hours

Examples:
  # Run medium scenario (default)
  python -m src.simulator baseline
  python -m src.simulator autoindex

  # Run specific scenario
  python -m src.simulator baseline --scenario small
  python -m src.simulator baseline --scenario large

  # Run stress test
  python -m src.simulator baseline --scenario stress-test

  # Comprehensive mode (tests all features)
  python -m src.simulator comprehensive --scenario small
  python -m src.simulator comprehensive --scenario medium
  python -m src.simulator comprehensive --scenario large

  # Custom parameters (overrides scenario)
  python -m src.simulator baseline --tenants 20 --queries 500 --contacts 2000
        """
    )

    parser.add_argument('mode', choices=['baseline', 'autoindex', 'scaled', 'comprehensive'],
                       help='Simulation mode')
    parser.add_argument('--scenario', choices=['small', 'medium', 'large', 'stress-test'],
                       default='medium',
                       help='Scenario to run (default: medium)')
    parser.add_argument('--tenants', type=int,
                       help='Number of tenants (overrides scenario)')
    parser.add_argument('--queries', type=int,
                       help='Queries per tenant (overrides scenario)')
    parser.add_argument('--contacts', type=int,
                       help='Contacts per tenant (overrides scenario)')
    parser.add_argument('--orgs', type=int,
                       help='Organizations per tenant (overrides scenario)')
    parser.add_argument('--interactions', type=int,
                       help='Interactions per tenant (overrides scenario)')

    args = parser.parse_args()

    # Get scenario configuration
    scenario = SCENARIOS[args.scenario]
    print(f"\n{'='*60}")
    print(f"SCENARIO: {args.scenario.upper()}")
    print(f"Description: {scenario['description']}")
    print(f"Estimated time: ~{scenario['estimated_time_minutes']} minutes")
    print(f"{'='*60}\n")

    # Use scenario defaults, but allow overrides
    num_tenants = args.tenants if args.tenants else scenario['num_tenants']
    queries_per_tenant = args.queries if args.queries else scenario['queries_per_tenant']
    contacts_per_tenant = args.contacts if args.contacts else scenario['contacts_per_tenant']
    orgs_per_tenant = args.orgs if args.orgs else scenario['orgs_per_tenant']
    interactions_per_tenant = args.interactions if args.interactions else scenario['interactions_per_tenant']
    spike_probability = scenario['spike_probability']
    spike_multiplier = scenario['spike_multiplier']
    spike_duration = scenario['spike_duration_queries']

    # Run simulation based on mode
    if args.mode == 'baseline':
        run_baseline_simulation(
            num_tenants=num_tenants,
            queries_per_tenant=queries_per_tenant,
            contacts_per_tenant=contacts_per_tenant,
            orgs_per_tenant=orgs_per_tenant,
            interactions_per_tenant=interactions_per_tenant,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario
        )
    elif args.mode == 'autoindex':
        run_autoindex_simulation(
            tenant_ids=None,
            queries_per_tenant=queries_per_tenant,
            contacts_per_tenant=contacts_per_tenant,
            orgs_per_tenant=orgs_per_tenant,
            interactions_per_tenant=interactions_per_tenant,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario
        )
    elif args.mode == 'scaled':
        # Run both baseline and auto-index
        print(f"Running SCALED simulation with {args.scenario} scenario")
        tenant_ids = run_baseline_simulation(
            num_tenants=num_tenants,
            queries_per_tenant=queries_per_tenant,
            contacts_per_tenant=contacts_per_tenant,
            orgs_per_tenant=orgs_per_tenant,
            interactions_per_tenant=interactions_per_tenant,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario
        )
        print("\n" + "=" * 80)
        print("Now running auto-index simulation with same tenants...")
        print("=" * 80)
        run_autoindex_simulation(
            tenant_ids=tenant_ids,
            queries_per_tenant=queries_per_tenant,
            contacts_per_tenant=contacts_per_tenant,
            orgs_per_tenant=orgs_per_tenant,
            interactions_per_tenant=interactions_per_tenant,
            spike_probability=spike_probability,
            spike_multiplier=spike_multiplier,
            spike_duration=spike_duration,
            scenario_name=args.scenario
        )
    elif args.mode == 'comprehensive':
        # Run comprehensive simulation with feature verification
        print(f"Running COMPREHENSIVE simulation with {args.scenario} scenario")
        print("This mode tests all product features across different database sizes")

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
            scenario_name=args.scenario
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
            scenario_name=args.scenario
        )

        # Run comprehensive feature verification
        print("\n" + "=" * 80)
        print("RUNNING COMPREHENSIVE FEATURE VERIFICATION")
        print("=" * 80)

        from src.simulation_verification import verify_all_features

        min_indexes = len(autoindex_results.get('index_details', [])) if isinstance(autoindex_results, dict) else 0
        verification_results = verify_all_features(tenant_ids=tenant_ids, min_indexes=min_indexes)

        # Save comprehensive results
        from src.paths import get_report_path
        comprehensive_results = {
            'scenario': args.scenario,
            'num_tenants': num_tenants,
            'queries_per_tenant': queries_per_tenant,
            'contacts_per_tenant': contacts_per_tenant,
            'orgs_per_tenant': orgs_per_tenant,
            'interactions_per_tenant': interactions_per_tenant,
            'autoindex_results': autoindex_results if isinstance(autoindex_results, dict) else {},
            'verification_results': verification_results,
            'timestamp': datetime.now().isoformat()
        }

        results_path = get_report_path('results_comprehensive.json')
        with open(results_path, 'w') as f:
            json.dump(comprehensive_results, f, indent=2, default=str)

        print(f"\n[OK] Comprehensive simulation complete. Results saved to {results_path}")

        # Print final summary
        if verification_results.get('summary', {}).get('all_passed', False):
            print("\n[SUCCESS] All feature verifications PASSED!")
        else:
            print("\n[WARNING] Some feature verifications had issues. Check details above.")

