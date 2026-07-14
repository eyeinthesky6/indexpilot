import asyncio
import inspect
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

import src.api_server as api_server
import src.index_cleanup as index_cleanup
import src.index_health as index_health
import src.index_lifecycle_manager as lifecycle
import src.maintenance as maintenance
import src.write_performance as write_performance


class _SequenceCursor:
    def __init__(self, *, rows=None, fetchones=None):
        self.rows = rows or []
        self.fetchones = list(fetchones or [])
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((query, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.fetchones.pop(0) if self.fetchones else None


def test_unused_index_detector_requires_known_old_age_and_honors_minimum_size(monkeypatch):
    now = datetime.now()
    cursor = _SequenceCursor(
        rows=[
            {
                "indexname": "idx_young",
                "tablename": "orders",
                "index_scans": 0,
                "index_size_bytes": 2 * 1024 * 1024,
            },
            {
                "indexname": "idx_old",
                "tablename": "orders",
                "index_scans": 0,
                "index_size_bytes": 2 * 1024 * 1024,
            },
        ],
        fetchones=[
            {"created_at": now - timedelta(hours=1)},
            {"created_at": now - timedelta(days=30)},
        ],
    )

    @contextmanager
    def fake_cursor():
        yield cursor

    monkeypatch.setattr(index_cleanup, "is_system_enabled", lambda: True)
    monkeypatch.setattr(index_cleanup, "get_cursor", fake_cursor)

    candidates = index_cleanup.find_unused_indexes(min_scans=10, days_unused=7, _min_size_mb=1.5)

    assert [candidate["indexname"] for candidate in candidates] == ["idx_old"]
    assert candidates[0]["safe_to_drop"] is False
    assert cursor.executions[0][1][-1] == int(1.5 * 1024 * 1024)
    ownership_query, ownership_params = cursor.executions[1]
    assert "details_json->>'index_name' = %s" in ownership_query
    assert "details_json->>'mode' = 'apply'" in ownership_query
    assert ownership_params == ("orders", "idx_young")


def test_legacy_cleanup_and_reindex_reject_physical_changes(monkeypatch):
    monkeypatch.setattr(index_cleanup, "is_system_enabled", lambda: True)

    with pytest.raises(RuntimeError, match="automatic_index_drop_disabled"):
        index_cleanup.cleanup_unused_indexes(dry_run=False)
    with pytest.raises(RuntimeError, match="automatic_reindex_disabled"):
        index_health.reindex_bloated_indexes(dry_run=False)
    assert maintenance.schedule_automatic_reindex(dry_run=False) == {
        "skipped": True,
        "reason": "automatic_reindex_disabled",
        "reindexed": 0,
        "indexes": [],
    }


def test_index_health_is_one_query_factual_inventory_without_inferred_bloat(monkeypatch):
    cursor = _SequenceCursor(
        rows=[
            {
                "indexname": "orders_status_idx",
                "tablename": "orders",
                "index_scans": 12,
                "tuples_read": 40,
                "tuples_fetched": 30,
                "index_size_bytes": 2 * 1024 * 1024,
                "table_size_bytes": 20 * 1024 * 1024,
                "is_valid": True,
                "is_ready": True,
                "is_unique": False,
                "is_primary": False,
                "is_constraint_owned": False,
            }
        ]
    )

    @contextmanager
    def fake_cursor():
        yield cursor

    monkeypatch.setattr(index_health, "is_system_enabled", lambda: True)
    monkeypatch.setattr(index_health, "get_cursor", fake_cursor)

    report = index_health.monitor_index_health(min_size_mb=1)

    assert len(cursor.executions) == 1
    assert report["summary"]["bloat_status"] == "not_measured"
    assert report["indexes"][0]["bloat_percent"] is None
    assert report["indexes"][0]["last_used_at"] is None


def test_health_api_keeps_unmeasured_values_missing_instead_of_inventing_them(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "monitor_index_health",
        lambda **kwargs: {
            "indexes": [
                {
                    "indexname": "orders_status_idx",
                    "tablename": "orders",
                    "size_mb": 2.0,
                    "index_scans": 12,
                    "health_status": "healthy",
                    "bloat_status": "not_measured",
                }
            ]
        },
    )

    response = asyncio.run(api_server.get_health_data())

    assert response["indexes"][0]["bloatPercent"] is None
    assert response["indexes"][0]["lastUsed"] is None
    assert response["summary"]["avgBloatPercent"] is None
    assert response["summary"]["bloatStatus"] == "not_measured"


def test_write_stats_keep_decimal_latency_but_do_not_claim_overhead(monkeypatch):
    cursor = _SequenceCursor(
        fetchones=[
            {
                "total_writes": 4,
                "avg_write_duration_ms": Decimal("12.5"),
                "p95_write_duration_ms": Decimal("20.25"),
                "p99_write_duration_ms": Decimal("25.75"),
            },
            {"index_count": 3, "total_index_bytes": 8192},
            {
                "inserts": 10,
                "updates": 5,
                "deletes": 2,
                "hot_updates": 3,
                "database_stats_reset_at": "2026-07-01T00:00:00Z",
            },
        ]
    )

    @contextmanager
    def fake_cursor():
        yield cursor

    monkeypatch.setattr(write_performance, "get_cursor", fake_cursor)

    report = write_performance.get_table_write_stats("orders", hours=24)

    assert report["avg_write_duration_ms"] == 12.5
    assert report["writes_observed"] == 17
    assert report["total_index_bytes"] == 8192
    assert report["estimated_write_overhead"] is None
    assert report["write_overhead_status"] == "not_measured"


def test_scheduled_lifecycle_is_explicitly_dry_run(monkeypatch):
    assert (
        inspect.signature(lifecycle.perform_vacuum_analyze_for_indexes)
        .parameters["dry_run"]
        .default
        is True
    )
    assert (
        inspect.signature(lifecycle.perform_per_tenant_lifecycle).parameters["dry_run"].default
        is True
    )
    assert (
        inspect.signature(lifecycle.perform_weekly_lifecycle).parameters["dry_run"].default is True
    )
    assert (
        inspect.signature(lifecycle.perform_monthly_lifecycle).parameters["dry_run"].default is True
    )
    weekly_calls = []
    monthly_calls = []
    monkeypatch.setattr(lifecycle, "is_lifecycle_management_enabled", lambda: True)
    monkeypatch.setattr(
        lifecycle,
        "get_lifecycle_config",
        lambda: {"weekly_schedule": True, "monthly_schedule": True},
    )
    monkeypatch.setattr(lifecycle, "_get_weekly_interval", lambda: 0)
    monkeypatch.setattr(lifecycle, "_get_monthly_interval", lambda: 0)
    monkeypatch.setattr(lifecycle.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        lifecycle,
        "perform_weekly_lifecycle",
        lambda *, dry_run: weekly_calls.append(dry_run) or {},
    )
    monkeypatch.setattr(
        lifecycle,
        "perform_monthly_lifecycle",
        lambda *, dry_run: monthly_calls.append(dry_run) or {},
    )
    lifecycle._last_weekly_lifecycle = 0
    lifecycle._last_monthly_lifecycle = 0

    lifecycle.run_lifecycle_scheduler()

    assert weekly_calls == [True]
    assert monthly_calls == [True]
