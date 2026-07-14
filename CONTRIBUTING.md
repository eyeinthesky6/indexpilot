# Contributing to IndexPilot

Thanks for helping improve IndexPilot. The project is currently an open-source preview, so small,
well-tested changes are preferred over broad rewrites.

## Before You Start

- Open an issue for large behavior or architecture changes.
- Keep advisory mode as the default. Changes that create or remove database objects need explicit
  operator opt-in and rollback evidence.
- Reuse the existing database, configuration, validation, audit, and adapter modules.
- Do not add secrets or real production data to tests, examples, or reports.

## Core CLI setup

Requirements: Python 3.10+. Docker is needed only for database-backed integration tests.

```bash
python -m venv venv
python -m pip install -e ".[dev,api,ml]"
python -m pytest tests/test_cli.py tests/test_proposed_index_parser.py tests/test_workload_dna.py -q
python -m build
indexpilot --help
```

For the full database-backed suite:

```bash
docker compose up -d postgres
python -c "from src.schema import init_schema; from src.genome import bootstrap_genome_catalog; init_schema(); bootstrap_genome_catalog()"
python -m pytest tests -q
python scripts/check_unsafe_db_access.py
docker compose down
```

## Dashboard Setup

Requirements: Node.js 20.9+ and pnpm 10+.

```bash
cd ui
pnpm install --frozen-lockfile
pnpm lint
pnpm build
```

## Pull Requests

Explain the user-visible behavior, tests run, database impact, and rollback path. Update the README
or focused docs when a capability or limitation changes. Do not describe a module as working merely
because a file exists; show its caller, test, or runtime evidence.

For proposed-index review, keep the accepted SQL subset explicit. Supplied SQL must be parsed and
rebuilt from validated identifiers; it must never be executed directly or silently approximated.
