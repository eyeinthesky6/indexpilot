# IndexPilot

[![CI](https://github.com/eyeinthesky6/indexpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/eyeinthesky6/indexpilot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Review PostgreSQL indexes against your real workload before building them.**

IndexPilot is an open-source, read-only CLI preview. It reads aggregate
`pg_stat_statements` data, understands PostgreSQL SQL through an AST parser, checks existing
indexes, and can use an already-installed [HypoPG](https://github.com/HypoPG/hypopg) extension to
compare planner cost. It writes both JSON and Markdown evidence.

It does **not** execute the proposed SQL, create an index, or claim that planner cost equals real
latency.

## The useful wedge

PostgreSQL already has mature candidate generators, hosted advisers, migration linters, and raw
HypoPG tooling. IndexPilot has a narrower job:

> “Someone proposed this index. Does our observed workload and the PostgreSQL planner give us
> enough evidence to spend time benchmarking it?”

That makes it useful in a pull request, performance review, or runbook where the next safe answer is
one of:

- `worth_benchmarking`
- `existing_overlap`
- `not_supported_by_current_planner_evidence`
- `inconclusive`

The positive verdict intentionally says **benchmark it**, not **ship it**.

## Five-minute path

### 1. Install

The first public package is not on PyPI yet. Install the current GitHub version in an isolated
environment:

```bash
pipx install "git+https://github.com/eyeinthesky6/indexpilot.git"
```

Or install from a clone:

```bash
git clone https://github.com/eyeinthesky6/indexpilot.git
cd indexpilot
python -m pip install .
```

### 2. Point it at PostgreSQL

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=my_app
export DB_USER=indexpilot_reader
export DB_PASSWORD='replace-me'
export DB_SSLMODE=require
```

PowerShell uses `$env:DB_HOST = "localhost"` and the same names for the remaining values.

The database must already expose `pg_stat_statements`. See [installation and database
permissions](docs/INSTALLATION.md) before using a production database.

### 3. Review one proposed index

```bash
indexpilot review \
  --candidate-sql 'CREATE INDEX ON public.orders (tenant_id, created_at)' \
  --hypopg
```

IndexPilot parses the input, keeps only normalized identifiers, rebuilds safe hypothetical SQL, and
reviews that exact column shape. The supplied string is never sent to PostgreSQL.

The command writes:

- `indexpilot-review.json` for automation and later comparison
- `indexpilot-review.md` for humans and pull requests

Its terminal summary is short:

```text
IndexPilot review complete (advisory only).
Verdict: worth_benchmarking
Reason: HypoPG lowered planner cost enough to pass the existing advisory threshold
Parser: sqlglot_postgres_ast
Workload rows read: 24
Candidate mutations: 1
HypoPG validation: completed
Planner-validated mutations: 1
JSON report: /work/indexpilot-review.json
Markdown report: /work/indexpilot-review.md
```

The numbers above illustrate the output shape; your report contains evidence from your database.

## Discover workload candidates

If you do not yet have a proposed index, omit the candidate:

```bash
indexpilot review --schema public --min-calls 100 --hypopg
```

This path finds repeated equality-plus-range/order patterns, skips small tables and comparable
existing B-tree prefixes, and compares smaller alternative shapes when HypoPG is available.

## What it reads and changes

| Area | Behavior |
|------|----------|
| Workload | Reads aggregate entries from `pg_stat_statements` |
| Catalog | Reads table, column, size, scan, and index metadata |
| SQL parsing | Uses SQLGlot’s PostgreSQL AST; there is no regex fallback |
| HypoPG | Creates session-local hypothetical indexes and uses `EXPLAIN`, never `ANALYZE` |
| Report privacy | Stores query fingerprints, not raw workload SQL |
| Physical indexes | Never creates, drops, or changes one in the public review command |

The connection is placed in a read-only transaction. HypoPG and `pg_stat_statements` must be
installed by the database owner; IndexPilot does not install extensions.

## Supported proposed indexes

The preview deliberately accepts a small shape:

```sql
CREATE INDEX [CONCURRENTLY] [IF NOT EXISTS] [name]
ON [schema.]table (column [, column ...]);
```

It supports one non-unique, ascending B-tree with plain column keys. It rejects partial,
expression, `INCLUDE`, `UNIQUE`, descending, GIN, GiST, BRIN, storage-option, tablespace, and
multi-statement input. Those shapes need different evidence and must not be silently approximated.

## How to read a verdict

| Verdict | Meaning | Next step |
|---------|---------|-----------|
| `worth_benchmarking` | The exact hypothetical index was selected and passed the existing planner-cost threshold | Benchmark latency, writes, size, and rollback on a production copy |
| `existing_overlap` | A valid, ready, ordinary B-tree with default operator classes, collations, and ascending order already has the same leading prefix | Inspect the existing index before adding another |
| `not_supported_by_current_planner_evidence` | HypoPG completed, but this exact shape was unused or below the threshold | Do not infer harm; inspect the query plan or test another shape |
| `inconclusive` | Workload evidence or planner validation was missing | Collect representative traffic or configure HypoPG |

Current HypoPG review plans one representative query per candidate. It is not a full workload
regression test.

## Why not just use an advanced tool?

- Use [Dexter](https://github.com/ankane/dexter) when you want a mature automatic index candidate
  generator.
- Use [Squawk](https://github.com/sbdchd/squawk) when you want static PostgreSQL migration linting.
- Use [HypoPG](https://github.com/HypoPG/hypopg) directly when you already know how to build the
  workload and evidence pipeline yourself.
- Use a hosted adviser when managed monitoring and support matter more than a local, inspectable
  report contract.

IndexPilot is for the smaller gap between those tools: review an exact proposal locally against
observed workload data and leave a portable evidence artifact. It is complementary, not a claim to
replace them.

## Documentation

- [Installation and PostgreSQL setup](docs/INSTALLATION.md)
- [CLI usage and report fields](docs/USAGE.md)
- [Current roadmap and deferred proof](docs/ROADMAP.md)
- [Architecture](docs/codebase/ARCHITECTURE.md)
- [Known concerns](docs/codebase/CONCERNS.md)
- [Article drafts](docs/articles/README.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

The repository also contains a historical automatic-indexer, demo API, CRM simulation, research
modules, and Next.js dashboard. They remain available for experiments but are not the public launch
promise. See [the documentation index](docs/DOCUMENTATION_INDEX.md) for that boundary.

## Development

```bash
git clone https://github.com/eyeinthesky6/indexpilot.git
cd indexpilot
python -m venv .venv
python -m pip install -e ".[dev,api,ml]"
python -m pytest tests -q
python scripts/check_unsafe_db_access.py
python -m build
```

Database-backed tests need the demo PostgreSQL service:

```bash
docker compose up -d postgres
python -c "from src.schema import init_schema; init_schema()"
python -m pytest tests -q
docker compose down
```

The dashboard is optional and is tested separately under `ui/`.

## Release status

`1.1.0a1` is an evaluation release, not a supported production service. The older
`v1.0.0-stable` repository tag predates this focused package contract and should be treated as
historical. The next release should be tagged only after CI passes on the merged default branch.

## License

[MIT](LICENSE)
