# Launch-Readiness Upgrade Review

## Scope

This review covers the open-source launch surface: installation, CLI discovery, PostgreSQL query
parsing, migration review, workload evidence, HypoPG admission, tenant evidence, index-sprawl
reporting, post-deploy comparison, API/UI reporting, packaging, documentation, correctness, and
measured performance.

It does **not** authorize automatic index creation, automatic index deletion, or changes to another
product's database. ProfitPilot was not connected to or changed during this upgrade.

## Evidence Checked

- Public ownership and contracts in `indexpilot/cli.py`, `src/sql_parser.py`,
  `src/workload_dna.py`, and `src/auto_indexer.py`.
- Existing database, configuration, API authentication, lifecycle, and scheduling owners before
  adding behavior.
- PostgreSQL catalog and statistics queries used by doctor, audit, health, cleanup, and write
  inventory.
- Package metadata, console commands, CI, Docker Compose, dashboard types, and user documentation.
- Tests for parser ambiguity, unsafe expressions, multiple migration statements, reset-aware
  comparisons, index-name collisions, partitioned tables, tenant evidence, and legacy safety.
- The earlier guarded production-copy benchmark in
  `docs/case_studies/PROFITPILOT_PRODUCTION_COPY_BENCHMARK.md`. That benchmark used a throwaway
  database; this launch pass did not copy or mutate ProfitPilot data.

## Tool Baseline

- Python 3.13.12, pytest 9.0.2, Ruff 0.12.12, and the repository's unsafe database-access scanner.
- Node 24.14.0, pnpm 10.31.0, Next.js 16.2.10, ESLint, and TypeScript.
- The existing SQLGlot PostgreSQL AST adapter and HypoPG integration; no second parser or index
  mutation framework was added.
- `python -m build` for the source distribution and wheel, plus Docker Compose and YAML parsing for
  release metadata validation.

## Agent-Led Review

The review was split into four bounded passes: architecture and public contract tracing,
math/correctness edge cases, legacy index-module safety, and measured performance. A final
independent diff review found three launch blockers: migration-internal hazards bypassed the CI
gate, cleanup ownership used a fuzzy audit-log match, and one tenant lifecycle entry point still
defaulted to live VACUUM. All three were fixed and regression-tested. Documentation was then
checked against the implemented CLI and API behavior.

The central architecture remains intact:

```text
pg_stat_statements + PostgreSQL catalog
    -> SQLGlot PostgreSQL AST adapter
    -> migration/workload candidate
    -> optional HypoPG planner evidence
    -> existing src.auto_indexer admission rules
    -> advisory Markdown, JSON, or SARIF report
```

`src.auto_indexer` remains the decision/apply owner. The new review commands do not create a second
mutation path.

## Findings

1. **The credible wedge is migration review using the database's real workload.** IndexPilot can
   answer a narrow pull-request question: “Does this proposed PostgreSQL index match observed query
   shapes, duplicate an existing index, fit the table type, and show planner evidence?” This is more
   useful and believable than marketing another autonomous index tuner.
2. **The public path is advisory and fail-closed.** Ambiguous SQL, expressions that cannot be mapped
   safely to physical columns, partition parents, reset statistics, and incompatible comparison
   snapshots produce blockers or skipped evidence instead of invented certainty.
3. **Legacy modules previously overstated evidence.** Scan counts are not physical bloat, index
   count is not milliseconds of write cost, and prefix overlap alone does not prove an index is safe
   to drop. These modules now expose factual inventory/manual-review output, while physical cleanup
   and automatic reindex entry points refuse execution.
4. **Bloat and exact write overhead remain deliberately partial.** The UI and API now say
   `not_measured` and return null values. Measured bloat needs an extension such as `pgstattuple` or
   an equivalent trusted source; write overhead needs a controlled workload benchmark.
5. **Performance is adequate for an advisory alpha.** Median local measurements were 121.70 ms for
   one automatic review over 200 workload rows, 128.85 ms for one exact review, 2.45 seconds for 20
   exact candidates, 19.23 ms to parse a 100-statement migration, and 124.28 ms to filter 1,000
   commented workload rows. The health endpoint's previous per-index query pattern was reduced to
   one catalog query. No speculative cache or broad refactor was justified.
6. **The complete suite still needs the repository's own PostgreSQL test service.** All 165
   database-independent tests pass. Eight integration cases cannot run while `localhost:5432` is
   unavailable; all eight fail at connection setup rather than at an IndexPilot assertion.

## Recommended Fixes

Completed for launch:

- Added `doctor`, migration-file review, `audit`, reset-aware `compare`, SARIF output, and CI-friendly
  `--fail-on` behavior.
- Reused the existing parser, workload, auto-indexer, authentication, and configuration owners.
- Added exact identifier/name collision checks, finite numeric thresholds, raw-value decisions,
  comment-aware read-only workload filtering, partition blockers, and conservative overlap rules.
- Routed migration-internal overlap and schema-wide duplicate names into SARIF and the opt-in
  `existing_overlap` gate.
- Changed cleanup, reindex, bloat, redundancy, and write-cost surfaces to factual/manual behavior;
  cleanup attribution now requires an exact same-table `mode=apply` receipt, destructive
  compatibility entry points refuse execution, and tenant/VACUUM lifecycle defaults to dry-run
  with safely composed identifiers.
- Added launch installation, usage, and GitHub Actions documentation and made every new feature
  discoverable from the README and CLI help.
- Repaired the pre-commit hook so it runs the UI lint gate from `ui/` and does not require a live
  authenticated API merely to create a commit.
- Removed the health endpoint's per-index database query and kept the measured implementation after
  benchmarking showed no need for a larger optimization.

Defer until evidence exists:

- Offline/sanitized workload snapshots for untrusted fork pull requests.
- A versioned official GitHub Action and multi-week false-positive trial data.
- Measured physical bloat and controlled write-amplification benchmarks.
- OAuth/OIDC and role permissions for a hosted multi-user service.
- Automatic apply/delete behavior. It should not be enabled merely to make the project appear more
  advanced.

## Verification

- `python -m pytest tests -q`: 173 collected; 165 passed. The remaining 1 failure and 7 setup errors
  all report PostgreSQL connection refusal at `localhost:5432` in the three existing live-database
  test files.
- Database-independent suite: 165/165 passed.
- Focused migration, CLI, and legacy-safety regression set: 62/62 passed.
- `python scripts/check_unsafe_db_access.py`: passed after removing test-variable false positives.
- Ruff formatting and lint on all changed Python files: passed.
- `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build`: passed; all dashboard routes generated.
- The repaired Husky pre-commit script passed from the repository root.
- `python -m build`: produced `indexpilot-1.1.0a1.tar.gz` and
  `indexpilot-1.1.0a1-py3-none-any.whl`.
- The shared machine's `python -m pip check` reports an existing `numba 0.61.2` / `numpy 2.4.3`
  conflict. Neither package is in IndexPilot's core dependency set; the environment was not
  changed. CI retains its isolated installed-wheel `pip check`.
- Root, `doctor`, `review`, `audit`, and `compare` CLI help smoke tests: passed.
- Docker Compose configuration and GitHub Actions YAML parsing: passed.
- Catalog SQL was also checked inside a read-only transaction against PostgreSQL 17.6 on a
  non-ProfitPilot local service. ProfitPilot was not accessed or changed.

## Follow-Up

Before calling IndexPilot an autonomous production index manager, run the live integration suite,
collect multi-week shadow results, prove rollback and write-amplification behavior on representative
copies, and choose a trusted bloat measurement source. None of those are blockers for an honest
open-source **advisory preview** positioned as workload-aware PostgreSQL migration review.
