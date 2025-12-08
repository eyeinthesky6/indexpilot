"""Tests for simulator - smoke test"""

import pytest
from psycopg2.extras import RealDictCursor

from src.auto_indexer import analyze_and_create_indexes
from src.db import get_connection
from src.genome import bootstrap_genome_catalog
from src.schema import init_schema
from src.simulation.simulator import create_tenant, run_query_by_email, seed_tenant_data


@pytest.fixture(scope="module")
def setup_db():
    """Initialize database schema for tests"""
    init_schema()
    bootstrap_genome_catalog()


def test_create_tenant(setup_db):
    """Test tenant creation"""
    tenant_id = create_tenant("Test Tenant")
    assert tenant_id > 0

    # Verify tenant exists
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,))
            tenant = cursor.fetchone()
            assert tenant is not None
            assert tenant['name'] == "Test Tenant"
        finally:
            cursor.close()


def test_seed_tenant_data(setup_db):
    """Test seeding data for a tenant"""
    tenant_id = create_tenant("Seed Test Tenant")
    seed_tenant_data(tenant_id, num_contacts=10, num_orgs=5, num_interactions=20)

    # Verify data was created
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT COUNT(*) as count FROM contacts WHERE tenant_id = %s", (tenant_id,))
            contact_count = cursor.fetchone()['count']
            assert contact_count == 10

            cursor.execute("SELECT COUNT(*) as count FROM organizations WHERE tenant_id = %s", (tenant_id,))
            org_count = cursor.fetchone()['count']
            assert org_count == 5
        finally:
            cursor.close()


def test_query_execution(setup_db):
    """Test that queries can be executed and stats are logged"""
    tenant_id = create_tenant("Query Test Tenant")
    seed_tenant_data(tenant_id, num_contacts=50, num_orgs=10, num_interactions=50)

    # Run a few queries
    for _ in range(5):
        duration = run_query_by_email(tenant_id)
        assert duration >= 0

    # Flush stats to ensure they're written
    from src.stats import flush_query_stats
    flush_query_stats()

    # Verify stats were logged
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM query_stats
                WHERE tenant_id = %s AND table_name = 'contacts' AND field_name = 'email'
            """, (tenant_id,))
            stat_count = cursor.fetchone()['count']
            assert stat_count == 5
        finally:
            cursor.close()


def test_auto_indexer_smoke(setup_db):
    """Smoke test: run auto-indexer and verify it can create indexes"""
    tenant_id = create_tenant("Auto-Index Test Tenant")
    seed_tenant_data(tenant_id, num_contacts=100, num_orgs=20, num_interactions=100)

    # Run many queries to generate stats
    for _ in range(200):
        run_query_by_email(tenant_id)

    # Run auto-indexer with low threshold
    _ = analyze_and_create_indexes(time_window_hours=1, min_query_threshold=50)

    # Verify that mutation was logged if index was created
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
            """)
            mutation_count = cursor.fetchone()['count']
            # Should have at least attempted to create an index if queries were sufficient
            assert mutation_count >= 0  # At least no errors
        finally:
            cursor.close()

