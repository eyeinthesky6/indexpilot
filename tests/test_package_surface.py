import subprocess
import sys
from pathlib import Path

import indexpilot
from indexpilot.dashboard_assets import dashboard_assets_available, resolve_dashboard_asset

ROOT = Path(__file__).resolve().parents[1]
ACTION_TEXT = (ROOT / "action.yml").read_text(encoding="utf-8")


def test_public_package_surface_is_importable():
    assert indexpilot.__version__ == "1.1.0a5"
    assert callable(indexpilot.build_index_review_report)
    assert callable(indexpilot.build_migration_review_report)
    assert callable(indexpilot.build_workload_readiness_report)
    assert callable(indexpilot.build_index_sprawl_report)
    assert callable(indexpilot.compare_index_review_reports)
    assert callable(indexpilot.build_workload_dna_report)
    assert callable(indexpilot.render_review_markdown)
    assert callable(indexpilot.render_review_sarif)


def test_core_review_imports_do_not_require_ml_dependencies():
    """The default wheel must run its review path without installing `[ml]`."""
    root = Path(__file__).resolve().parents[1]
    script = """
import builtins

blocked = {"numpy", "scipy", "sklearn", "xgboost"}
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name.split(".", 1)[0] in blocked:
        raise AssertionError(f"core review imported optional dependency: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from src.auto_indexer import review_planner_recommendations
from src.workload_dna import build_index_review_report
assert callable(review_planner_recommendations)
assert callable(build_index_review_report)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_action_exposes_optional_trusted_snapshot_input():
    assert "  snapshot-file:\n" in ACTION_TEXT
    assert 'description: "Optional path to a trusted sanitized workload snapshot' in ACTION_TEXT
    assert "INDEXPILOT_SNAPSHOT_FILE: ${{ inputs['snapshot-file'] }}" in ACTION_TEXT


def test_action_installs_published_package_version():
    assert 'python -m pip install "indexpilot==1.1.0a5"' in ACTION_TEXT


def test_bundled_dashboard_assets_are_present_and_path_safe():
    assert dashboard_assets_available()
    assert resolve_dashboard_asset("/dashboard/") is not None
    assert resolve_dashboard_asset("/../pyproject.toml") is None


def test_action_keeps_snapshot_and_live_command_modes_exclusive():
    snapshot_if = ACTION_TEXT.index('if [[ -n "$INDEXPILOT_SNAPSHOT_FILE" ]]')
    snapshot_arg = ACTION_TEXT.index(
        'args+=(--snapshot-file "$INDEXPILOT_SNAPSHOT_FILE")', snapshot_if
    )
    live_else = ACTION_TEXT.index("        else", snapshot_arg)
    schema_arg = ACTION_TEXT.index(
        'args+=(--schema "$INDEXPILOT_SCHEMA")', live_else
    )
    hypopg_arg = ACTION_TEXT.index("args+=(--hypopg)", schema_arg)
    mode_end = ACTION_TEXT.index("\n        fi\n        IFS=", hypopg_arg)

    assert snapshot_if < snapshot_arg < live_else < schema_arg < hypopg_arg < mode_end
    assert "--hypopg" not in ACTION_TEXT[snapshot_if:live_else]
    assert "--schema" not in ACTION_TEXT[snapshot_if:live_else]


def test_action_preserves_live_outputs_hypopg_and_verdict_gates():
    assert 'args=(review --migration-file "$INDEXPILOT_MIGRATION_FILE"' in ACTION_TEXT
    assert "--output indexpilot-review.json" in ACTION_TEXT
    assert "--markdown-output indexpilot-review.md" in ACTION_TEXT
    assert "--sarif-output indexpilot-review.sarif" in ACTION_TEXT
    assert 'if [[ "$INDEXPILOT_HYPOPG" == "true" ]]; then args+=(--hypopg); fi' in ACTION_TEXT
    assert 'IFS=\',\' read -ra verdicts <<< "$INDEXPILOT_FAIL_ON"' in ACTION_TEXT
    assert 'args+=(--fail-on "$verdict")' in ACTION_TEXT
