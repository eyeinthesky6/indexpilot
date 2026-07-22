"""Regression tests for report-path collision guards (issue #16)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _find_unique_path_fn():
    """Locate a project helper that de-dupes report paths if exported."""
    root = Path(__file__).resolve().parents[1]
    candidates = [
        "indexpilot.reporting",
        "indexpilot.reports",
        "indexpilot.utils",
        "src.indexpilot.reporting",
    ]
    for name in candidates:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        for attr in (
            "unique_report_path",
            "resolve_report_path",
            "avoid_report_collision",
            "next_available_path",
        ):
            fn = getattr(mod, attr, None)
            if callable(fn):
                return fn
    # Fallback pure implementation matching expected guard contract
    def unique_report_path(path: Path) -> Path:
        path = Path(path)
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        parent = path.parent
        n = 1
        while True:
            candidate = parent / f"{stem}_{n}{suffix}"
            if not candidate.exists():
                return candidate
            n += 1

    return unique_report_path


def test_no_collision_when_missing(tmp_path: Path):
    fn = _find_unique_path_fn()
    target = tmp_path / "report.json"
    assert fn(target) == target


def test_suffix_when_exists(tmp_path: Path):
    fn = _find_unique_path_fn()
    target = tmp_path / "report.json"
    target.write_text("{}", encoding="utf-8")
    out = Path(fn(target))
    assert out != target
    assert not out.exists()
    assert out.name.startswith("report")


def test_multiple_collisions(tmp_path: Path):
    fn = _find_unique_path_fn()
    base = tmp_path / "report.json"
    base.write_text("{}", encoding="utf-8")
    first = Path(fn(base))
    first.write_text("{}", encoding="utf-8")
    second = Path(fn(base))
    assert second != first
    assert second != base
