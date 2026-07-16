"""Route staged changes to relevant agent guidance and fast deterministic checks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

import yaml

SkillRoute = tuple[str, str]
Command = tuple[str, ...]
PNPM = "pnpm.cmd" if os.name == "nt" else "pnpm"


def _normalize(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def route_skills(paths: Iterable[str]) -> list[SkillRoute]:
    """Return stable, deduplicated skill guidance for repository-relative paths."""
    normalized = {_normalize(path) for path in paths}
    routes: list[SkillRoute] = []

    def add(skill: str, reason: str) -> None:
        if all(existing != skill for existing, _ in routes):
            routes.append((skill, reason))

    if any(path.endswith(".py") or path == "pyproject.toml" for path in normalized):
        add("acquire-codebase-knowledge", "trace Python owners and callers before changing behavior")
        add("requirement-validation", "prove the requested behavior and regression checks")

    if any(path.startswith("ui/") for path in normalized):
        add("build-web-apps:frontend-testing-debugging", "validate affected dashboard behavior")
        add("frontend-design", "preserve the established interface when visual files change")

    if any(
        path == "README.md"
        or path == "CONTRIBUTING.md"
        or path.startswith("docs/")
        or path.startswith(".github/ISSUE_TEMPLATE/")
        for path in normalized
    ):
        add("maintain-open-source-project", "keep public support and contributor paths accurate")

    if any(
        path in {"CODE_OF_CONDUCT.md", "GOVERNANCE.md"}
        or "governance" in path.lower()
        for path in normalized
    ):
        add("govern-open-source-project", "retain human approval and least-privilege role boundaries")

    if any(
        path == "SECURITY.md"
        or path.startswith(".github/workflows/")
        or path == ".github/dependabot.yml"
        for path in normalized
    ):
        add("secure-open-source-project", "review workflow permissions and supply-chain impact")

    if any(
        path in {"CHANGELOG.md", "action.yml", "pyproject.toml"}
        or path.startswith("docs/PUBLISHING")
        for path in normalized
    ):
        add("release-open-source-project", "keep package, action, notes, and publication order aligned")

    if any(path.startswith(".codex/coordination/") for path in normalized):
        add("codex-coordinator", "preserve project identity, ownership, and canonical state")

    return routes


def planned_commands(paths: Iterable[str]) -> list[Command]:
    """Build the non-modifying checks required for the supplied paths."""
    normalized = sorted({_normalize(path) for path in paths})
    commands: list[Command] = [("git", "diff", "--cached", "--check")]
    python_paths = [path for path in normalized if path.endswith(".py")]

    if python_paths:
        commands.append((sys.executable, "-m", "ruff", "check", "--force-exclude", *python_paths))

    core_prefixes = ("indexpilot/",)
    core_paths = {
        "src/auto_indexer.py",
        "src/sql_parser.py",
        "src/workload_dna.py",
        "tests/test_cli.py",
        "tests/test_package_surface.py",
        "tests/test_workload_dna.py",
    }
    if any(path.startswith(core_prefixes) or path in core_paths for path in normalized):
        commands.append(
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_workload_dna.py",
                "tests/test_cli.py",
                "tests/test_package_surface.py",
                "-q",
            )
        )

    if any(
        path in {"scripts/agent_skill_router.py", "tests/test_agent_skill_router.py"}
        for path in normalized
    ):
        commands.append((sys.executable, "-m", "pytest", "tests/test_agent_skill_router.py", "-q"))

    if any(path.startswith("ui/") for path in normalized):
        commands.append((PNPM, "--dir", "ui", "lint"))

    return commands


def staged_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def validate_staged_yaml(paths: Iterable[str]) -> None:
    """Parse YAML from the Git index rather than a possibly different worktree copy."""
    for path in sorted({_normalize(path) for path in paths}):
        if PurePosixPath(path).suffix not in {".yaml", ".yml"}:
            continue
        content = subprocess.run(
            ["git", "show", f":{path}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        yaml.safe_load(content)
        print(f"YAML OK: {path}")


def run(paths: Sequence[str], *, dry_run: bool = False) -> int:
    normalized = [_normalize(path) for path in paths]
    if not normalized:
        print("No staged files; no routed checks are needed.")
        return 0

    print("Agent skill guidance for these changes:")
    routes = route_skills(normalized)
    if routes:
        for skill, reason in routes:
            print(f"  - ${skill}: {reason}")
        print("Authoring agents must load these skills before changing or reviewing matching paths.")
    else:
        print("  - No specialist skill route; follow AGENTS.md and repository checks.")

    commands = planned_commands(normalized)
    if dry_run:
        for command in commands:
            print("CHECK:", subprocess.list2cmdline(command))
        if any(PurePosixPath(path).suffix in {".yaml", ".yml"} for path in normalized):
            print("CHECK: parse staged YAML")
        return 0

    validate_staged_yaml(normalized)
    for command in commands:
        print("Running:", subprocess.list2cmdline(command))
        subprocess.run(command, check=True, cwd=Path(__file__).resolve().parents[1])
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--staged", action="store_true", help="Route files staged in Git.")
    source.add_argument("--paths", nargs="+", help="Route explicit repository-relative paths.")
    parser.add_argument("--dry-run", action="store_true", help="Print checks without executing them.")
    args = parser.parse_args(argv)
    paths = staged_paths() if args.staged else args.paths
    return run(paths, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
