"""Configuration safety-contract tests."""

from pathlib import Path

from src.config_loader import ConfigLoader


def test_default_mode_is_advisory(tmp_path: Path, monkeypatch) -> None:
    """A missing config file must never opt into index-creating DDL."""
    monkeypatch.delenv("INDEXPILOT_AUTO_INDEXER_MODE", raising=False)

    loader = ConfigLoader(str(tmp_path / "missing-indexpilot-config.yaml"))

    assert loader.get("features.auto_indexer.mode") == "advisory"


def test_apply_mode_requires_explicit_environment_opt_in(tmp_path: Path, monkeypatch) -> None:
    """Operators can still opt into apply mode through the existing override."""
    monkeypatch.setenv("INDEXPILOT_AUTO_INDEXER_MODE", "apply")

    loader = ConfigLoader(str(tmp_path / "missing-indexpilot-config.yaml"))

    assert loader.get("features.auto_indexer.mode") == "apply"


def test_checked_in_config_keeps_thresholds_and_safe_mode(monkeypatch) -> None:
    """The shipped YAML has one complete auto-indexer configuration block."""
    monkeypatch.delenv("INDEXPILOT_AUTO_INDEXER_MODE", raising=False)

    loader = ConfigLoader("indexpilot_config.yaml")

    assert loader.get("features.auto_indexer.mode") == "advisory"
    assert loader.get_float("features.auto_indexer.threshold_multiplier") == 1.0
    assert loader.get_int("features.auto_indexer.min_queries_per_hour") == 100
    assert loader.get_int("features.auto_indexer.max_indexes_per_table") == 10
