"""Installed command-line entry points for IndexPilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _dna_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read PostgreSQL workload statistics and write explainable index candidates. "
            "The command is read-only and never applies DDL."
        )
    )
    parser.add_argument("--schema", default="public", help="Schema to inspect (default: public)")
    parser.add_argument("--min-calls", type=int, default=100)
    parser.add_argument("--min-table-rows", type=int, default=10_000)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--hypopg",
        action="store_true",
        help="Use an already-installed HypoPG extension for read-only planner comparison.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stdout", action="store_true")
    return parser


def dna_main(argv: list[str] | None = None) -> int:
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        summary = report["summary"]
        print("IndexPilot workload DNA report complete (advisory only).")
        print(f"Parser: {report['parser']['backend']}")
        print(f"Workload rows read: {summary['workload_rows_read']}")
        if summary["workload_stats_empty"]:
            print("Warning: the selected pg_stat_statements window is empty.")
        print(f"Candidate mutations: {summary['candidate_mutations']}")
        if args.hypopg:
            print(f"HypoPG validation: {report['planner_validation']['status']}")
            print(f"Planner-validated mutations: {summary['planner_validated_mutations']}")
            print(f"Auto-indexer review: {report['auto_indexer_review']['status']}")
        print(f"Report: {output_path.resolve()}")
        if args.stdout:
            print(json.dumps(report, indent=2))
        return 0
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

    from src.api_auth import AUTH_TOKEN_ENV, api_auth_is_configured, get_api_auth_mode

    if not _is_loopback_host(args.host) and (
        get_api_auth_mode() != "required" or not api_auth_is_configured()
    ):
        parser.error(f"non-loopback hosting requires {AUTH_TOKEN_ENV} and required auth mode")

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install API support with: pip install 'indexpilot[api]'") from exc

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
    if not arguments or arguments[0] not in {"dna", "api"}:
        print("Usage: indexpilot [dna|api] [options]", file=sys.stderr)
        return 2
    command, *rest = arguments
    return dna_main(rest) if command == "dna" else api_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
