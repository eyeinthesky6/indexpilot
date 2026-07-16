import json
from pathlib import Path

import indexpilot.cli as cli
import src.workload_dna as workload_dna

REPO_ROOT = Path(__file__).resolve().parents[1]
QUICKSTART = REPO_ROOT / "examples" / "quickstart"


def test_bundled_first_review_runs_without_database_access(monkeypatch, tmp_path):
    def fail_if_connected(**kwargs):
        raise AssertionError(f"quickstart attempted database access: {kwargs}")

    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", fail_if_connected)
    json_output = tmp_path / "indexpilot-review.json"
    markdown_output = tmp_path / "indexpilot-review.md"

    result = cli.review_main(
        [
            "--migration-file",
            str(QUICKSTART / "migration.sql"),
            "--snapshot-file",
            str(QUICKSTART / "workload-snapshot.json"),
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    assert result == 0
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["source_mode"] == "sanitized_offline_snapshot"
    assert report["summary"]["reviewed_indexes"] == 1
    assert report["summary"]["verdict_counts"] == {"existing_overlap": 1}
    assert report["reviews"][0]["summary"]["matching_workload_fingerprints"] == 1
    assert "`existing_overlap`" in markdown_output.read_text(encoding="utf-8")


def test_agent_discovery_files_point_to_one_canonical_skill():
    canonical = REPO_ROOT / "skills" / "review-postgres-index" / "SKILL.md"
    assert canonical.is_file()
    assert (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"

    for agent_root in (".agents", ".claude"):
        wrapper = REPO_ROOT / agent_root / "skills" / "review-postgres-index" / "SKILL.md"
        text = wrapper.read_text(encoding="utf-8")
        assert "../../../skills/review-postgres-index/SKILL.md" in text

    canonical_metadata = (
        REPO_ROOT / "skills" / "review-postgres-index" / "agents" / "openai.yaml"
    )
    discovered_metadata = (
        REPO_ROOT / ".agents" / "skills" / "review-postgres-index" / "agents" / "openai.yaml"
    )
    assert canonical_metadata.read_text(encoding="utf-8") == discovered_metadata.read_text(
        encoding="utf-8"
    )
