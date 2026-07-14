import builtins
import json

import pytest

import indexpilot.cli as cli
import src.workload_dna as workload_dna


def _report():
    return {
        "report_type": "indexpilot_workload_dna",
        "advisory_only": True,
        "parser": {"backend": "sqlglot_postgres_ast"},
        "summary": {
            "workload_rows_read": 1,
            "workload_stats_empty": False,
            "candidate_mutations": 0,
            "planner_validated_mutations": 0,
            "indexable_patterns_observed": 0,
        },
        "verdict": {"status": "inconclusive", "reason": "test evidence"},
        "planner_validation": {"requested": False, "status": "not_requested"},
        "candidates": [],
        "limits": ["No index was created or dropped."],
    }


def test_root_help_version_and_unknown_command(capsys):
    assert cli.main([]) == 0
    assert "review" in capsys.readouterr().out

    assert cli.main(["--version"]) == 0
    assert "1.1.0a1" in capsys.readouterr().out

    assert cli.main(["unknown"]) == 2
    assert "Unknown command" in capsys.readouterr().err


def test_main_routes_review_and_keeps_dna_alias(monkeypatch):
    monkeypatch.setattr(cli, "review_main", lambda args: 11)
    monkeypatch.setattr(cli, "dna_main", lambda args: 12)

    assert cli.main(["review"]) == 11
    assert cli.main(["dna"]) == 12


def test_review_writes_json_and_markdown_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(workload_dna, "build_workload_dna_report", lambda **kwargs: _report())
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)
    json_path = tmp_path / "review.json"
    markdown_path = tmp_path / "review.md"

    result = cli.review_main(
        [
            "--output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert result == 0
    assert json.loads(json_path.read_text(encoding="utf-8"))["advisory_only"] is True
    assert "Advisory only" in markdown_path.read_text(encoding="utf-8")


def test_unsupported_candidate_is_an_input_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)

    result = cli.review_main(
        [
            "--candidate-sql",
            "DROP INDEX dangerous",
            "--output",
            str(tmp_path / "review.json"),
            "--markdown-output",
            str(tmp_path / "review.md"),
        ]
    )

    assert result == 2
    assert "Unsupported candidate index" in capsys.readouterr().err


def test_empty_candidate_is_not_silently_changed_to_workload_discovery(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)

    result = cli.review_main(
        [
            "--candidate-sql",
            "",
            "--output",
            str(tmp_path / "review.json"),
            "--markdown-output",
            str(tmp_path / "review.md"),
        ]
    )

    assert result == 2
    assert "create_index_required" in capsys.readouterr().err


def test_json_and_markdown_outputs_cannot_overwrite_each_other(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)
    output = tmp_path / "review.out"

    result = cli.review_main(["--output", str(output), "--markdown-output", str(output)])

    assert result == 2
    assert "must be different" in capsys.readouterr().err
    assert not output.exists()


def test_api_command_explains_how_to_install_optional_support(monkeypatch):
    original_import = builtins.__import__

    def import_without_api_support(name, *args, **kwargs):
        if name == "uvicorn" or name.startswith("src.api_auth"):
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_api_support)

    with pytest.raises(SystemExit, match=r"pip install 'indexpilot\[api\]'"):
        cli.api_main([])
