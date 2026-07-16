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
4. Add a reusable fork-safe Action input after the versioned offline snapshot contract has shipped
   in a reviewed package release; the documented CLI workflow is available first.
5. Measure physical bloat with a clearly optional PostgreSQL-supported tool; keep catalog overlap
   separate from safe-to-drop decisions.
6. Promote a stable release only after its clean-environment install and stronger evidence are
   independently verified.

## Delivered evidence upgrades

- Versioned sanitized workload snapshot generation through the protected read-only collector.
- Exact candidate and migration review against that snapshot without PostgreSQL or secrets.
- Fork-safe CI guidance that reads the snapshot from the trusted base commit, not the contributor
  checkout. Offline evidence is deliberately weaker than live HypoPG planner review.

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
