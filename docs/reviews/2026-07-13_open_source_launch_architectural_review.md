# Open-Source Launch Architectural Review

## Scope

Assess IndexPilot's actual user value, trace the working runtime paths, identify launch blockers,
make minimal safe upgrades, and separate larger product work for a later release.

## Evidence Checked

- Product intent and claims: `README.md`, `docs/features/FEATURES.md`,
  `docs/features/SYSTEM_VALUE_PROPOSITION.md`
- Runtime owners: `src/stats.py`, `src/auto_indexer.py`, `src/query_executor.py`,
  `src/config_loader.py`, `src/api_server.py`, `src/index_lifecycle_manager.py`
- Contracts and persistence: `src/schema/initialization.py`, `src/genome.py`, `src/expression.py`
- Dashboard client and routes: `ui/lib/api.ts`, `ui/app/`, `ui/next.config.ts`
- Tests and tools: `tests/`, `pytest.ini`, `Makefile`, `scripts/check_unsafe_db_access.py`
- External baseline: PostgreSQL `pg_stat_statements`, HypoPG, Dexter, and PostgresAI index pilot

## Tool Baseline

- Repository scan: 858 files and 51,247 lines including data, docs, scripts, backend, tests, and UI.
- PostgreSQL 15 Docker service started and schema bootstrapped successfully.
- Baseline suite: 71 tests passed; two pytest warnings were found and fixed. The final suite after
  launch work passes 79 tests.
- API smoke: all seven GET routes and all three lifecycle dry-run POST routes returned HTTP 200.
- Unsafe database-access scan: passed.
- Mypy ran with 29 findings, mostly missing installed stubs plus several current-code findings; the
  old “zero errors” docs were not current. The new workload DNA files pass Ruff using an existing
  workspace tool environment.
- Dashboard dependencies were not installed locally, so local lint/build proof is still pending. CI
  now runs those checks on every push and pull request.

## Agent-Led Review

### Working runtime path

1. A host explicitly records workload data through `src.stats.log_query_stat()`.
2. Buffered rows are stored in `query_stats`.
3. `src.auto_indexer.analyze_and_create_indexes()` aggregates field usage, validates candidates,
   checks patterns, rate limits, maintenance windows, storage, and estimated benefit.
4. Index-type selection produces standard PostgreSQL DDL.
5. Advisory mode records the candidate in `mutation_log`; apply mode executes the DDL.
6. `src.api_server` reads health, performance, decision, and lifecycle data for the Next.js UI.

### Degraded and failure path

- Missing workload rows result in no recommendation rather than guessed DDL.
- Invalid table or field names are rejected through central validation.
- Database operations roll back on failures in the tested schema-mutation path.
- The shipped default previously selected apply mode despite README claims. This was a real unsafe
  failure path and is now fixed to advisory in code, config, example config, and tests.

### Ownership findings

- `src.auto_indexer.py` is the main decision and apply owner, but at about 2,900 lines it also owns
  cost loading, sampling, strategy selection, multiple research heuristics, safeguards, execution,
  and reporting. This is a future maintainability risk, not a launch refactor.
- `src.query_executor.execute_query()` intercepts and executes queries but does not call
  `log_query_stat()`. “Automatic” workload learning therefore depends on manual host instrumentation.
- `get_field_usage_stats()` aggregates across tenants. The main loop later looks for a `tenant_id`
  that is not in that aggregate, so per-tenant config does not drive the normal candidate path.
- ALEX, PGM, RadixStringSpline, Fractal Tree, iDistance, and Bx-tree modules are suitability or
  recommendation layers. They map ideas to supported PostgreSQL indexes; they do not implement those
  learned or specialized data structures inside PostgreSQL.

## True Product Value

### Strong today

IndexPilot is a useful experimental and advisory toolkit for teams that want one repository showing
schema discovery, query-stat persistence, explainable index decisions, mutation lineage, safeguards,
lifecycle helpers, an API, and a dashboard. The audit trail and operator-control emphasis are more
distinctive than the raw index-selection math.

### Not yet proven

It is not yet a drop-in autonomous index manager. Real applications need workload ingestion,
packaging, API authentication, and production trials. Tenant-specific recommendation behavior is
mostly an intended direction. Academic naming currently adds less value than the practical
PostgreSQL heuristics beneath it.

### Competitive position

- PostgreSQL already supplies `pg_stat_statements` to track planning and execution statistics for
  all server statements: https://www.postgresql.org/docs/current/pgstatstatements.html
- HypoPG can test hypothetical indexes without building them or consuming normal index resources:
  https://github.com/HypoPG/hypopg
- Dexter combines workload sources such as `pg_stat_statements` with HypoPG and does not create an
  index unless `--create` is supplied: https://github.com/ankane/dexter
- PostgresAI's BSD-licensed index pilot focuses on unused, redundant, and invalid index lifecycle:
  https://github.com/postgres-ai/postgres_ai/tree/main/components/index_pilot

IndexPilot should not compete on “automatic index recommendation” alone. Its credible open-source
direction is an auditable application-aware control layer that can consume proven PostgreSQL/OSS
evidence and attach tenant, approval, lineage, and rollback context.

### ProfitPilot proof

A read-only scan of ProfitPilot's production-local PostgreSQL 17 workload read 187 aggregate
workload rows, ignored 68 patterns on small tables, and returned 11 review candidates. The leading
candidate matched 193 calls against the roughly 637,000-row `action_audit` table using
`(action_type, timestamp)`; those calls consumed about 68.85 seconds in aggregate. A representative
current plan used a parallel sequential scan and sort. The report recorded
`transaction_read_only=on`, stored query fingerprints rather than raw SQL, and applied no DDL.

This proves a narrow user value: IndexPilot can expose workload field sequences that ProfitPilot's
existing scan-count-based optimizer does not identify. A follow-up isolated HypoPG/Dexter trial
also proved the first equality-first composite is not reliable enough to be final: smaller timestamp
indexes won some planner comparisons. Optional HypoPG comparison now selects and deduplicates the
planner-backed mutation; real before/after latency and write-overhead evidence remains required.

## Findings

1. **High — unsafe default contradicted launch copy.** Config and fallback logic defaulted to apply.
2. **High — automatic collection is missing.** Host applications must manually record stats.
3. **High — remote API deployment is unsafe.** Lifecycle mutation routes have no authentication.
4. **High — distribution is not installable.** Users must copy `src/` and rewrite imports.
5. **Medium — tenant-aware value is incomplete.** Global aggregates bypass tenant-specific config.
6. **Medium — recommendation proof remains weaker than established OSS.** Optional HypoPG what-if
   evaluation now improves the standalone report, but the full auto-indexer is not yet routed
   through it and no production-copy benchmark exists.
7. **Medium — docs overclaim readiness and algorithm implementation.** Current evidence supports an
   open-source preview, not a production-ready service.
8. **Medium — central owner is oversized.** `src/auto_indexer.py` is difficult to review safely.

## Recommended Fixes

### Completed for preview launch

- Advisory is now the code and YAML default; apply needs explicit opt-in.
- Duplicate `features.auto_indexer` YAML ownership was removed without dropping thresholds.
- Safety-contract tests cover defaults, explicit override, and checked-in config.
- README now states actual capabilities, limits, Python/Node requirements, and preview status.
- CI, contribution guidance, and a security policy were added.
- Pytest configuration and the schema-mutation test no longer emit the two baseline warnings.
- A standalone workload DNA command now reads `pg_stat_statements` in an explicitly read-only
  transaction, suppresses covered and small-table noise, removes raw SQL from reports, and emits
  review-only composite-index candidates.
- A real ProfitPilot case study and three launch article drafts document the evidence and limits.
- Optional `--hypopg` comparison now evaluates composite, prefix, equality, range, and order-column
  alternatives one at a time, stores compact plan evidence, and emits deduplicated planner-backed
  recommendations without real DDL.
- An isolated ProfitPilot/Dexter trial corrected the competitor claims and showed where a smaller
  index beats the first DNA heuristic.

### Defer to the next product phase

1. Integrate the standalone DNA workload source into the full auto-indexer through a workload-source
   interface. Keep manual instrumentation as a supported adapter rather than the only path.
2. Route the now-proven optional HypoPG evidence contract into the full auto-indexer only after
   characterization tests lock its existing decision boundary. Keep it advisory until a
   production-copy benchmark passes.
3. Package the project with `pyproject.toml` under a real `indexpilot` namespace and separate runtime
   from development dependencies.
4. Add host-owned authentication/authorization for mutation routes, or split the read dashboard API
   from a private operator control API.
5. Make tenant context explicit in candidate aggregation and decide which tenant policies can affect
   global PostgreSQL indexes. Do not imply per-tenant physical indexes unless predicates prove it.
6. Split the auto-indexer only after characterization tests lock the decision contract. Suggested
   seams are workload input, candidate scoring, safeguards, DDL planning, apply, and evidence.
7. Extend the first anonymized ProfitPilot comparison into repeated shadow trials and publish
   false-positive rate, plan-cost delta, read latency, write overhead, index size, and rollback
   evidence.

## Verification

- `python -m pytest tests -q`
- `python -m pytest tests/test_workload_dna.py -q`
- `python scripts/check_unsafe_db_access.py`
- Live read-only report against ProfitPilot production-local: 187 workload rows, 11 candidates,
  `transaction_read_only=on`, and no raw-query fields
- FastAPI TestClient smoke against all ten routes with lifecycle requests forced to dry-run
- `docker compose config --quiet`
- CI syntax and repository paths reviewed; first remote CI run remains the dashboard build proof

## Follow-Up

- [ASK USER] Decide whether the first named release is an evaluation toolkit or a supported
  production service.
- [ASK USER] Decide whether the dashboard is local/private only or must support hosted multi-user
  access in the next release.
- [ASK USER] Choose whether packaging and `pg_stat_statements` ingestion are the next milestone; they
  provide more adoption value than adding more custom scoring algorithms.
