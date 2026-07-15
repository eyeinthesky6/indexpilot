# Contributing to IndexPilot

Thanks for helping improve IndexPilot. The project is an open-source preview, so a small change with
clear evidence is more useful than a broad rewrite. You do not need to know every historical module
or be a PostgreSQL expert to make a worthwhile contribution.

## Good First Contributions

Good starting points include:

- correcting a supported CLI example or documenting a reproducible setup problem;
- adding a focused unit test for an existing verdict, parser boundary, or report field;
- reproducing behavior on another supported PostgreSQL or Python version;
- improving database-independent test coverage without inventing a coverage target;
- reducing a small piece of duplicate contributor or CI work.

Browse issues labelled
[good first issue](https://github.com/eyeinthesky6/indexpilot/labels/good%20first%20issue) or
[help wanted](https://github.com/eyeinthesky6/indexpilot/labels/help%20wanted). Comment on an issue
before starting so two people do not solve the same problem. If no issue matches, open a bug report,
question, or focused feature request first.

## Before You Start

- Open an issue for large behavior or architecture changes.
- Keep advisory mode as the default. Changes that create or remove database objects need explicit
  operator opt-in and rollback evidence.
- Reuse the existing database, configuration, validation, audit, and adapter modules.
- Prefer a maintained library when it solves the problem cleanly. Explain why a new dependency is
  needed and check its license and maintenance status.
- Do not add secrets or real production data to tests, examples, or reports.

## Core CLI setup

Requirements: Python 3.10+. Docker is needed only for database-backed integration tests.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,api,ml]"
python -m pytest tests/test_cli.py tests/test_proposed_index_parser.py tests/test_workload_dna.py -q
python -m build
indexpilot --help
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead of the
`source` command.

For the full database-backed suite:

```bash
docker compose up -d postgres
python -c "from src.schema import init_schema; from src.genome import bootstrap_genome_catalog; init_schema(); bootstrap_genome_catalog()"
python -m pytest tests -q
python scripts/check_unsafe_db_access.py
docker compose down
```

## Dashboard Setup

Requirements: Node.js 20.9+ and pnpm 10+. CI currently uses Node.js 22.

```bash
cd ui
pnpm install --frozen-lockfile
pnpm lint
pnpm build
```

## Make a Small First Pull Request

1. Fork the repository and create a focused branch.
2. Change one behavior, test, or documentation problem.
3. Run the narrowest relevant check, then the broader package checks when practical.
4. Open a pull request and fill in the evidence and safety sections.

The pull request template asks for user-visible behavior, tests, and database reads or writes. If a
check needs PostgreSQL and you cannot run it locally, say so plainly. CI supplies PostgreSQL for the
full backend suite.

## Pull Requests

Explain the user-visible behavior, tests run, database impact, and rollback path. Update the README
or focused docs when a capability or limitation changes. Do not describe a module as working merely
because a file exists; show its caller, test, or runtime evidence.

For proposed-index review, keep the accepted SQL subset explicit. Supplied SQL must be parsed and
rebuilt from validated identifiers; it must never be executed directly or silently approximated.

Changes that expand the public claim need a real caller, tests, documented limits, and evidence.
The project will not merge automatic production DDL by default, fabricated benchmark results, or a
new public feature justified only by the presence of an older experimental file.

There is no guaranteed maintainer response time. You should still expect direct feedback about the
supported behavior, evidence quality, and safety boundary. Respectful disagreement is welcome.
