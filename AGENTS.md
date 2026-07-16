# IndexPilot contributor and agent guide

## Product boundary

IndexPilot is an advisory, read-only PostgreSQL index review CLI. The public path reviews a
proposed `CREATE INDEX` against observed `pg_stat_statements` workload, existing indexes, and
optional HypoPG plans. It produces JSON, Markdown, and optional SARIF evidence.

Do not describe the public product as an automatic index manager. It does not apply migrations,
create physical indexes, drop indexes, run `EXPLAIN ANALYZE`, or prove production latency.

## Start here

- `README.md`: product promise, quick start, and current public behavior
- `indexpilot/cli.py`: public command-line interface
- `src/workload_dna.py`: review reports, verdicts, and comparison contracts
- `src/auto_indexer.py`: workload candidate planning and HypoPG review
- `src/sql_parser.py`: PostgreSQL SQL parsing through SQLGlot
- `docs/USAGE.md`: complete CLI examples and report interpretation
- `docs/ROADMAP.md`: current scope and deliberately deferred work
- `examples/quickstart/`: sanitized, database-free first review with a known overlap result
- `skills/review-postgres-index/SKILL.md`: canonical install, first-use, and review workflow for agents

The historical `src/` tree contains earlier experiments. A module existing does not make it a
public feature. Follow the callers from `indexpilot/cli.py` and the current documentation before
changing or advertising behavior.

## Development

Requires Python 3.10 through 3.13. The optional dashboard requires Node.js 22 and pnpm 10.31.0.

```bash
python -m pip install ".[dev,api,ml]"
python -m pytest tests -q
python scripts/check_unsafe_db_access.py
python -m build
```

Dashboard checks:

```bash
cd ui
pnpm install --frozen-lockfile
pnpm lint
pnpm build
```

Database-backed tests expect the PostgreSQL service and environment used in
`.github/workflows/ci.yml`. A local connection failure is not a passing test; use the CI service or
start an equivalent disposable database.

## Change rules

- Keep the public review path advisory and read-only.
- Reuse existing report contracts and CLI owners instead of adding parallel paths.
- Parse proposed SQL through the existing SQLGlot AST path. Do not add a regex fallback.
- Never store raw workload SQL in reports; preserve query fingerprints.
- Never turn planner cost into a latency claim or overlap evidence into drop advice.
- Add tests for new verdicts, report fields, parser shapes, and CLI behavior.
- Update README, usage, roadmap, and examples when public behavior changes.
- Do not commit credentials, production SQL, raw query text, or database dumps.

## Pull requests

Keep changes small and state which public decision becomes easier or safer. Include the checks
run, PostgreSQL version when relevant, and a sanitized example report for output changes.

## Codex Coordinator

- This repository is Codex Coordinator-enabled.
- Project identity is in `.codex/coordination/project.yaml`; current coordination state is in `.codex/coordination/CURRENT.md`.
- Load the globally installed `codex-coordinator` skill before substantial, overlapping, parallel, or cross-thread work.
- Respect the project ID and assigned task boundary; reject missing or mismatched cross-thread project bindings.
- Treat Coordinator internals as protected; only an explicitly user-authorised `COORDINATOR_MAINTAINER` may modify them.
