# Launch-Readiness Upgrade Review

## Decision

IndexPilot is now suitable for an open-source **advisory preview** under its current MIT license.
It is installable, its API fails closed by default, its workload parser uses a maintained SQL AST,
and HypoPG evidence reaches the existing auto-indexer decision owner. It is still not an autonomous
production index manager.

## Architecture after this upgrade

```text
pg_stat_statements
    -> SQLGlot PostgreSQL AST adapter
    -> workload DNA candidate + explicit tenant evidence
    -> optional HypoPG planner comparison
    -> src.auto_indexer admission review
    -> advisory report

operator-reviewed apply mode remains a separate, existing safeguarded path
```

The important ownership rule is unchanged: `src.auto_indexer` is the decision/apply owner. HypoPG
does not create a second mutation path. `src.sql_parser` owns parser translation, and SQLGlot nodes
do not escape that adapter.

## Completed items

### PostgreSQL parser

- Replaced query-shape regex parsing with SQLGlot's PostgreSQL AST.
- Covered quoted identifiers, placeholders, CTEs, aliases, joins, `ANY`, range filters, and order
  columns.
- Removed the regex fallback, so an unparsed or ambiguous statement is skipped rather than guessed.
- Canonical fingerprints remove literal and parameter values before hashing.

### HypoPG and auto-indexer

- Planner-backed recommendations are admitted through `review_planner_recommendations()` in
  `src.auto_indexer`.
- The auto-indexer rebuilds trusted DDL from validated identifiers and applies its configured
  minimum-improvement threshold.
- Admission remains advisory. Production-copy evidence and operator approval remain explicit apply
  blockers.

### Tenant-aware physical decisions

- An index is marked `shared_global_tenant_keyed` only when `tenant_id` appears as an equality
  predicate in the observed query and remains the leading selected index column.
- A table merely having a tenant column is not accepted as proof.
- PostgreSQL physical indexes are correctly described as shared/global; the report never claims to
  create one private physical index per tenant.

### Packaging

- Added `pyproject.toml` and the public `indexpilot` package.
- Added `indexpilot`, `indexpilot-dna`, and `indexpilot-api` console commands.
- Split optional API, ML, and development dependencies from the small advisory core.
- Kept `src.*` internally for compatibility instead of a risky repository-wide import rewrite.

### API authentication

- Added one centralized bearer-token middleware.
- All API, OpenAPI, and documentation routes require authentication; only `/` liveness is public.
- Missing token configuration fails closed with HTTP 503; missing or wrong credentials return 401.
- Non-loopback CLI hosting refuses to start unless required auth mode and a token are configured.
- The static bearer scheme is appropriate for a single operator/private deployment, not a hosted
  multi-user SaaS. OAuth/OIDC and role permissions remain later work.

### Bounded offline behavior

- Importing simulator helpers no longer starts the maintenance thread; the CLI starts it only after
  explicit simulator initialization.
- Database connection attempts now default to a bounded 10-second timeout, configurable through
  `DB_CONNECT_TIMEOUT` from 1 to 60 seconds.
- Identity-free cost checks return the deterministic heuristic result instead of invoking
  database-backed ML and telemetry with empty table/column names.

## Production-copy evidence

The 2026-07-14 run copied only `action_type`, `symbol`, and timestamps from ProfitPilot through a
read-only transaction into `indexpilot_benchmark_20260714`. The clone added synthetic padding to
approximate source row width. All real indexes, inserts, drops, and rollback measurements happened
only in that throwaway database.

ProfitPilot before and after:

| Check | Before | After |
|---|---:|---:|
| `action_audit` rows | 645,358 | 645,358 |
| `tick_data` rows | 21,037 | 21,037 |
| HypoPG installed | 0 | 0 |
| `_dna` indexes | 0 | 0 |

The detailed results are in
`docs/case_studies/PROFITPILOT_PRODUCTION_COPY_BENCHMARK.md`.

## Verification

- 88 database-free Python tests passed in 3.75 seconds.
- 8 existing live-database integration tests were not run because all database services were left
  stopped; they cover genome, schema mutation, and simulator integration rather than this upgrade.
- The dashboard passed `pnpm lint` and `pnpm build`.
- A clean Python 3.13 environment installed the `indexpilot-0.2.0` wheel with API extras, imported
  FastAPI 0.139 and SQLGlot 30.12, and ran both console entry points.
- An installed API smoke test returned 200 for public liveness, 401 for a protected route without a
  token, and 200 with the configured bearer token; the smoke server was then stopped.

## Remaining launch limits

1. The package has not been published to PyPI. A wheel/install smoke test proves it is publishable,
   but release credentials and the final version tag are operator-owned actions.
2. The API token is a single-operator control, not user accounts or RBAC.
3. The legacy field-stat auto-indexer still aggregates across tenants. The new DNA/HypoPG path has
   proven tenant semantics; the legacy path should not be marketed as tenant-specific.
4. Apply mode is not automatically enabled by a passing benchmark. This is intentional.
5. Multi-week shadow trials and false-positive rates are still needed before calling the system a
   supported production service.

## Files owning the new behavior

- `src/sql_parser.py` — SQL AST adapter and tenant predicate evidence
- `src/workload_dna.py` — report/candidate and HypoPG evidence
- `src/auto_indexer.py` — planner recommendation admission
- `src/api_auth.py` and `src/api_server.py` — API authentication boundary
- `pyproject.toml` and `indexpilot/` — installable public package
- `scripts/benchmarking/benchmark_production_copy.py` — guarded benchmark reproduction
