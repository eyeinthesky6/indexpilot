"""Tests for bounded database connection configuration."""

import pytest

from src.db import get_db_config


def test_database_connections_have_a_bounded_default_timeout(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)

    assert get_db_config()["connect_timeout"] == 10


def test_database_connection_timeout_rejects_unbounded_values(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "0")

    with pytest.raises(ValueError, match="between 1 and 60"):
        get_db_config()
