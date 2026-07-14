# Focused roadmap

IndexPilot’s launch promise is intentionally small: review PostgreSQL index opportunities against
observed workload data without changing the database.

## In the preview

- installable Python package and CLI
- `indexpilot review` for workload discovery
- exact review of one simple proposed B-tree index
- batch review of supported index statements in a migration file
- readiness doctor for workload/catalog/HypoPG evidence
- conservative existing-index overlap audit with no drop advice
- offline post-deploy usage observation with statistics-window checks
- SARIF output and opt-in verdict gates for trusted CI
- SQLGlot PostgreSQL AST parsing
- `pg_stat_statements` workload input
- comparable existing-index checks
- optional HypoPG planner evidence
- JSON and Markdown artifacts
- cautious public verdicts
- compatibility access to the historical API, dashboard, simulator, and auto-indexer

## Next evidence upgrades

These add real value without turning the project into another automatic DBA:

1. Review every representative fingerprint for a candidate, not just one.
2. Add production-copy replay receipts for latency distribution and regressions.
3. Measure index size, build time, write amplification, and maintenance cost.
4. Accept a sanitized offline workload snapshot for safe untrusted-fork review.
5. Add an official reusable GitHub workflow only after the offline snapshot contract exists.
6. Measure physical bloat with a clearly optional PostgreSQL-supported tool; keep catalog overlap
   separate from safe-to-drop decisions.
7. Publish through PyPI Trusted Publishing after the default branch and release ownership are ready.

## Deliberately deferred

- automatic production DDL from the public CLI
- automatic cleanup or REINDEX from legacy lifecycle helpers
- inferred bloat percentages or fixed per-index write-cost percentages
- hosted multi-user accounts and RBAC
- claims of full tenant-specific physical optimization
- MySQL or SQL Server support
- ML scoring as the public value proposition
- automatic partial, expression, INCLUDE, GIN, GiST, or BRIN proposals

The historical repository contains experiments in several of these areas. They are not current
launch claims. A future feature should move into the public path only with a real caller, tests,
documented limits, and workload evidence.
