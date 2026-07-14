"""Installed command-line entry points for IndexPilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from psycopg2 import Error as PsycopgError

from indexpilot import __version__

ROOT_HELP = """usage: indexpilot [--version] <command> [options]

Read-only PostgreSQL index review against observed workload evidence.

commands:
  review    Review workload candidates or one proposed CREATE INDEX
  dna       Compatibility alias for the original JSON workload report
  api       Run the authenticated, single-operator dashboard API

Run 'indexpilot <command> --help' for command-specific options.
"""


def _add_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--schema", default="public", help="Schema to inspect (default: public)")
    parser.add_argument("--min-calls", type=int, default=100)
    parser.add_argument("--min-table-rows", type=int, default=10_000)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--hypopg",
        action="store_true",
        help="Use an already-installed HypoPG extension for read-only planner comparison.",
    )
    parser.add_argument("--stdout", action="store_true", help="Also print the report to stdout.")


def _dna_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indexpilot dna",
        description=(
            "Write the compatibility workload-DNA JSON report. The command is read-only and "
            "never applies DDL."
        ),
    )
    _add_report_arguments(parser)
    parser.add_argument("--output", type=Path)
    return parser


def _review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indexpilot review",
        description=(
            "Review PostgreSQL index opportunities against pg_stat_statements. Optionally supply "
            "one simple CREATE INDEX to review its exact B-tree shape. No DDL is executed."
        ),
    )
    _add_report_arguments(parser)
    candidate = parser.add_mutually_exclusive_group()
    candidate.add_argument(
        "--candidate-sql",
        help="One simple, non-unique B-tree CREATE INDEX statement to review.",
    )
    candidate.add_argument(
        "--candidate-file",
        type=Path,
        help="File containing exactly one supported CREATE INDEX statement.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("indexpilot-review.json"),
        help="JSON report path (default: ./indexpilot-review.json).",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("indexpilot-review.md"),
        help="Markdown report path (default: ./indexpilot-review.md).",
    )
    return parser


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _print_report_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    verdict = report.get("verdict", {})
    print("IndexPilot review complete (advisory only).")
    if verdict:
        print(f"Verdict: {verdict['status']}")
        print(f"Reason: {verdict['reason']}")
    print(f"Parser: {report['parser']['backend']}")
    print(f"Workload rows read: {summary['workload_rows_read']}")
    if summary["workload_stats_empty"]:
        print("Warning: the selected pg_stat_statements window is empty.")
    print(f"Candidate mutations: {summary['candidate_mutations']}")
    if report.get("planner_validation", {}).get("requested"):
        print(f"HypoPG validation: {report['planner_validation']['status']}")
        print(f"Planner-validated mutations: {summary['planner_validated_mutations']}")


def _report_runtime_error(exc: Exception) -> int:
    print(f"IndexPilot could not complete the review: {exc}", file=sys.stderr)
    return 1


def dna_main(argv: list[str] | None = None) -> int:
    """Run the original workload report as a compatibility command."""
    from src.db import close_connection_pool
    from src.paths import get_report_path
    from src.workload_dna import build_workload_dna_report

    args = _dna_parser().parse_args(argv)
    output_path = args.output or get_report_path("workload_dna.json")

    try:
        report = build_workload_dna_report(
            schema=args.schema,
            min_calls=args.min_calls,
            min_table_rows=args.min_table_rows,
            limit=args.limit,
            validate_hypopg=args.hypopg,
        )
        serialized = json.dumps(report, indent=2)
        _write_text(output_path, serialized)
        _print_report_summary(report)
        print(f"JSON report: {output_path.resolve()}")
        if args.stdout:
            print(serialized)
        return 0
    except (OSError, PsycopgError, RuntimeError, ValueError) as exc:
        return _report_runtime_error(exc)
    finally:
        close_connection_pool()


def review_main(argv: list[str] | None = None) -> int:
    """Run the public workload or proposed-index review command."""
    from src.db import close_connection_pool
    from src.sql_parser import ProposedIndexError
    from src.workload_dna import (
        build_index_review_report,
        build_workload_dna_report,
        render_review_markdown,
    )

    args = _review_parser().parse_args(argv)
    try:
        if args.output.resolve() == args.markdown_output.resolve():
            print("JSON and Markdown output paths must be different.", file=sys.stderr)
            return 2

        candidate_requested = args.candidate_sql is not None or args.candidate_file is not None
        candidate_sql = args.candidate_sql
        if args.candidate_file is not None:
            candidate_sql = args.candidate_file.read_text(encoding="utf-8")

        if candidate_requested:
            report = build_index_review_report(
                candidate_sql or "",
                default_schema=args.schema,
                min_calls=args.min_calls,
                limit=args.limit,
                validate_hypopg=args.hypopg,
            )
        else:
            report = build_workload_dna_report(
                schema=args.schema,
                min_calls=args.min_calls,
                min_table_rows=args.min_table_rows,
                limit=args.limit,
                validate_hypopg=args.hypopg,
            )

        serialized = json.dumps(report, indent=2)
        markdown = render_review_markdown(report)
        _write_text(args.output, serialized)
        _write_text(args.markdown_output, markdown)
        _print_report_summary(report)
        print(f"JSON report: {args.output.resolve()}")
        print(f"Markdown report: {args.markdown_output.resolve()}")
        if args.stdout:
            print(markdown)
        return 0
    except ProposedIndexError as exc:
        print(f"Unsupported candidate index: {exc}", file=sys.stderr)
        return 2
    except (OSError, PsycopgError, RuntimeError, ValueError) as exc:
        return _report_runtime_error(exc)
    finally:
        close_connection_pool()


def _is_loopback_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "::1", "localhost"}


def api_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the authenticated IndexPilot API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    try:
        import uvicorn

        from src.api_auth import AUTH_TOKEN_ENV, api_auth_is_configured, get_api_auth_mode
    except ImportError as exc:
        raise SystemExit("Install API support with: pip install 'indexpilot[api]'") from exc

    if not _is_loopback_host(args.host) and (
        get_api_auth_mode() != "required" or not api_auth_is_configured()
    ):
        parser.error(f"non-loopback hosting requires {AUTH_TOKEN_ENV} and required auth mode")

    uvicorn.run(
        "src.api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help"}:
        print(ROOT_HELP)
        return 0
    if arguments[0] == "--version":
        print(f"indexpilot {__version__}")
        return 0

    command, *rest = arguments
    commands = {"review": review_main, "dna": dna_main, "api": api_main}
    handler = commands.get(command)
    if handler is None:
        print(f"Unknown command: {command}\n", file=sys.stderr)
        print(ROOT_HELP, file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
