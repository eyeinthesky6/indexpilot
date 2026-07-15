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
    assert "1.1.0a2" in capsys.readouterr().out

    assert cli.main(["unknown"]) == 2
    assert "Unknown command" in capsys.readouterr().err


def test_main_routes_review_and_keeps_dna_alias(monkeypatch):
    monkeypatch.setattr(cli, "review_main", lambda args: 11)
    monkeypatch.setattr(cli, "doctor_main", lambda args: 13)
    monkeypatch.setattr(cli, "audit_main", lambda args: 14)
    monkeypatch.setattr(cli, "compare_main", lambda args: 15)
    monkeypatch.setattr(cli, "dna_main", lambda args: 12)

    assert cli.main(["review"]) == 11
    assert cli.main(["doctor"]) == 13
    assert cli.main(["audit"]) == 14
    assert cli.main(["compare"]) == 15
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


def test_review_routes_a_migration_file_to_the_batch_builder(monkeypatch, tmp_path):
    migration_path = tmp_path / "migration.sql"
    migration_path.write_text(
        "CREATE INDEX idx_orders_status ON orders (status);", encoding="utf-8"
    )
    report = {
        "report_type": "indexpilot_migration_review",
        "advisory_only": True,
        "parser": {"backend": "sqlglot_postgres_ast"},
        "migration": {
            "statement_count": 1,
            "ignored_non_index_statements": 0,
            "reviewed_index_statements": 1,
        },
        "summary": {
            "reviewed_indexes": 1,
            "snapshot_count": 1,
            "verdict_counts": {"inconclusive": 1},
            "migration_overlap_findings": 0,
        },
        "reviews": [],
        "migration_overlap_findings": [],
        "limits": ["No index was executed."],
    }
    captured = {}

    def fake_build(sql, **kwargs):
        captured["sql"] = sql
        captured["kwargs"] = kwargs
        return report

    monkeypatch.setattr(workload_dna, "build_migration_review_report", fake_build)
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)

    result = cli.review_main(
        [
            "--migration-file",
            str(migration_path),
            "--output",
            str(tmp_path / "review.json"),
            "--markdown-output",
            str(tmp_path / "review.md"),
        ]
    )

    assert result == 0
    assert "CREATE INDEX" in captured["sql"]
    assert captured["kwargs"]["default_schema"] == "public"
    assert (
        json.loads((tmp_path / "review.json").read_text(encoding="utf-8"))["report_type"]
        == "indexpilot_migration_review"
    )


def test_migration_overlap_matches_existing_overlap_gate():
    report = {
        "report_type": "indexpilot_migration_review",
        "reviews": [],
        "migration_overlap_findings": [{"type": "exact_duplicate_shape"}],
    }

    assert cli._report_verdict_statuses(report) == {"existing_overlap"}


def test_doctor_writes_readiness_reports(monkeypatch, tmp_path):
    report = {
        "report_type": "indexpilot_readiness",
        "summary": {"status": "ready", "reason": "test evidence"},
        "source": {"database_name": "test", "server_version": "17"},
        "checks": [],
        "next_command": "indexpilot review",
    }
    monkeypatch.setattr(workload_dna, "build_workload_readiness_report", lambda **kwargs: report)
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)
    json_path = tmp_path / "doctor.json"
    markdown_path = tmp_path / "doctor.md"

    result = cli.doctor_main(
        [
            "--output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert result == 0
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["status"] == "ready"
    assert "IndexPilot workload readiness" in markdown_path.read_text(encoding="utf-8")


def test_audit_writes_non_destructive_overlap_report(monkeypatch, tmp_path):
    report = {
        "report_type": "indexpilot_index_sprawl",
        "summary": {
            "status": "review_candidates_found",
            "indexes_inspected": 2,
            "comparable_indexes": 2,
            "skipped_non_comparable_indexes": 0,
            "overlap_findings": 1,
        },
        "source": {"database_stats_reset_at": "2026-07-01"},
        "findings": [],
        "limits": ["No DROP INDEX statement is generated."],
    }
    monkeypatch.setattr(workload_dna, "build_index_sprawl_report", lambda **kwargs: report)
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)
    json_path = tmp_path / "audit.json"
    markdown_path = tmp_path / "audit.md"

    result = cli.audit_main(
        [
            "--output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert result == 0
    assert all("drop_sql" not in finding for finding in report["findings"])
    assert "never declares an index safe to drop" in markdown_path.read_text(encoding="utf-8")


def test_compare_reads_two_reports_and_writes_observation(monkeypatch, tmp_path):
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps({"report": "before"}), encoding="utf-8")
    after_path.write_text(json.dumps({"report": "after"}), encoding="utf-8")
    observation = {
        "report_type": "indexpilot_index_observation",
        "proposal": {"schema": "public", "table": "orders", "columns": ["status"]},
        "source": {},
        "verdict": {"status": "usage_observed", "reason": "test evidence"},
        "observed_index": {"name": "idx_orders_status", "index_scans": 3},
        "workload_delta": None,
        "table_activity_delta": None,
        "limits": [],
    }
    captured = {}

    def fake_compare(before, after):
        captured["before"] = before
        captured["after"] = after
        return observation

    monkeypatch.setattr(workload_dna, "compare_index_review_reports", fake_compare)
    output = tmp_path / "observation.json"
    markdown = tmp_path / "observation.md"

    result = cli.compare_main(
        [
            str(before_path),
            str(after_path),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ]
    )

    assert result == 0
    assert captured == {"before": {"report": "before"}, "after": {"report": "after"}}
    assert json.loads(output.read_text(encoding="utf-8"))["verdict"]["status"] == "usage_observed"


def test_review_can_write_sarif_and_opt_in_to_a_verdict_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(workload_dna, "build_workload_dna_report", lambda **kwargs: _report())
    monkeypatch.setattr("src.db.close_connection_pool", lambda: None)
    sarif_path = tmp_path / "review.sarif"

    result = cli.review_main(
        [
            "--output",
            str(tmp_path / "review.json"),
            "--markdown-output",
            str(tmp_path / "review.md"),
            "--sarif-output",
            str(sarif_path),
            "--fail-on",
            "inconclusive",
        ]
    )

    assert result == 3
    assert json.loads(sarif_path.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_api_command_explains_how_to_install_optional_support(monkeypatch):
    original_import = builtins.__import__

    def import_without_api_support(name, *args, **kwargs):
        if name == "uvicorn" or name.startswith("src.api_auth"):
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_api_support)

    with pytest.raises(SystemExit, match=r"pip install 'indexpilot\[api\]'"):
        cli.api_main([])
