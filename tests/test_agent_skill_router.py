import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROUTER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_skill_router.py"
SPEC = spec_from_file_location("indexpilot_agent_skill_router", ROUTER_PATH)
assert SPEC is not None and SPEC.loader is not None
ROUTER = module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)

planned_commands = ROUTER.planned_commands
route_skills = ROUTER.route_skills
run = ROUTER.run
PNPM = ROUTER.PNPM


def _skill_names(paths):
    return [name for name, _ in route_skills(paths)]


def test_routes_python_ui_and_public_project_paths():
    skills = _skill_names(
        ["indexpilot/cli.py", "ui/app/page.tsx", "README.md", ".github/workflows/ci.yml"]
    )

    assert skills == [
        "acquire-codebase-knowledge",
        "requirement-validation",
        "build-web-apps:frontend-testing-debugging",
        "frontend-design",
        "maintain-open-source-project",
        "secure-open-source-project",
    ]


def test_routes_release_governance_and_coordination_paths_once():
    skills = _skill_names(
        ["pyproject.toml", "CHANGELOG.md", "docs/governance-operations.md", ".codex/coordination/CURRENT.md"]
    )

    assert skills == [
        "acquire-codebase-knowledge",
        "requirement-validation",
        "maintain-open-source-project",
        "govern-open-source-project",
        "release-open-source-project",
        "codex-coordinator",
    ]


def test_plans_only_checks_relevant_to_changed_paths():
    commands = planned_commands(["scripts/agent_skill_router.py", "ui/app/page.tsx"])

    assert commands[0] == ("git", "diff", "--cached", "--check")
    assert (sys.executable, "-m", "pytest", "tests/test_agent_skill_router.py", "-q") in commands
    assert (PNPM, "--dir", "ui", "lint") in commands
    assert not any("test_workload_dna.py" in command for command in commands)


def test_core_review_changes_plan_focused_regression_suite():
    commands = planned_commands(["src/workload_dna.py"])

    assert any("tests/test_workload_dna.py" in command for command in commands)


def test_dry_run_prints_guidance_without_running_checks(capsys):
    assert run([".github/dependabot.yml"], dry_run=True) == 0

    output = capsys.readouterr().out
    assert "$secure-open-source-project" in output
    assert "parse staged YAML" in output
