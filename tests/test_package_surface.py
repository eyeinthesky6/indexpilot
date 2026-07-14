import subprocess
import sys
from pathlib import Path

import indexpilot


def test_public_package_surface_is_importable():
    assert indexpilot.__version__ == "1.1.0a1"
    assert callable(indexpilot.build_index_review_report)
    assert callable(indexpilot.build_workload_dna_report)
    assert callable(indexpilot.render_review_markdown)


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
