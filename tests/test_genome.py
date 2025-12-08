"""Tests for genome catalog operations"""

import pytest

from src.genome import bootstrap_genome_catalog, get_genome_fields
from src.schema import init_schema


@pytest.fixture(scope="module")
def setup_db():
    """Initialize database schema for tests"""
    init_schema()
    bootstrap_genome_catalog()


def test_genome_catalog_bootstrap(setup_db):
    """Test that genome catalog is bootstrapped correctly"""
    fields = get_genome_fields()
    assert len(fields) > 0

    # Check that core fields exist
    table_names = {f["table_name"] for f in fields}
    assert "contacts" in table_names
    assert "organizations" in table_names
    assert "tenants" in table_names


def test_genome_fields_for_table(setup_db):
    """Test getting fields for a specific table"""
    contact_fields = get_genome_fields("contacts")
    assert len(contact_fields) > 0

    field_names = {f["field_name"] for f in contact_fields}
    assert "id" in field_names
    assert "name" in field_names
    assert "email" in field_names
    assert "tenant_id" in field_names


def test_genome_field_properties(setup_db):
    """Test that genome fields have required properties"""
    fields = get_genome_fields("contacts")

    for field in fields:
        assert "table_name" in field
        assert "field_name" in field
        assert "field_type" in field
        assert "is_indexable" in field
        assert "default_expression" in field
