# Architecture

## 1) Architectural Style

- Primary style: modular Python application/toolkit with a shared PostgreSQL store and a separate
  dashboard client.
- The classification comes from direct module calls under `src/`, central `src.db` connection
  helpers, FastAPI routes, and a Next.js API client. There is no message bus or service boundary.
- Primary constraints: PostgreSQL-specific optimizer behavior, advisory/apply safety, and host-owned
  workload instrumentation.

## 2) System Flow

```text
host instrumentation -> query_stats -> candidate scoring/safeguards -> advisory log or DDL
                    -> mutation_log/health data -> FastAPI -> Next.js dashboard

proposed CREATE INDEX or migration -> SQL AST -> normalized exact shapes --+
pg_stat_statements + catalogs -> workload fingerprints -------+-> existing-prefix check
                                                            -> optional HypoPG EXPLAIN
                                                            -> auto-indexer admission threshold
                                                            -> verdict + JSON/Markdown/SARIF

catalog snapshot -> conservative overlap audit (never DROP advice)
before/after exact reports -> offline usage observation (never latency proof)
```

1. `indexpilot review` collects aggregate workload and catalog metadata in a read-only transaction.
2. `src.sql_parser` parses queries and one or more constrained `CREATE INDEX` statements.
3. Existing-index comparison accepts only valid, ready, ordinary non-partial B-trees as coverage.
4. Optional HypoPG tests session-local hypothetical shapes with `EXPLAIN`, never `ANALYZE`.
5. `src.auto_indexer.review_planner_recommendations()` remains the one admission-threshold owner.
6. The CLI writes fingerprints and evidence to JSON, Markdown, and optional SARIF without physical
   DDL. `doctor`, `audit`, and `compare` reuse the same factual evidence boundary.
7. The older host-instrumented `query_stats`/apply flow and dashboard remain compatibility surfaces.
   Scheduled lifecycle work is dry-run; legacy cleanup and REINDEX mutation are disabled.

## 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| Configuration | Defaults, YAML loading, environment overrides | Database DDL | `src/config_loader.py` |
| Persistence | Connections, transactions, typed cursor helpers | Product scoring | `src/db.py` |
| Workload | Query-stat collection and aggregates | HTTP API | `src/stats.py` |
| SQL parsing | PostgreSQL AST to product-owned pattern contract | DDL or planner decisions | `src/sql_parser.py` |
| Review/report | Snapshot analysis, hypothetical evidence, stable verdicts | Physical index execution | `src/workload_dna.py` |
| CLI | Inputs, exit codes, JSON/Markdown files | Candidate scoring | `indexpilot/cli.py` |
| Decision/apply | Candidate scoring, gates, advisory/apply path | UI rendering | `src/auto_indexer.py` |
| Lifecycle | Advisory inventory, refresh, and dry-run scheduling | Automatic cleanup or REINDEX | `src/index_lifecycle_manager.py` |
| API auth | Central bearer-token boundary | Database or lifecycle decisions | `src/api_auth.py` |
| API | JSON route contract and error translation | Workload collection | `src/api_server.py` |
| UI | Dashboard presentation and API calls | PostgreSQL access | `ui/lib/api.ts` |

## 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Adapter | `src/adapters.py`, `src/database/adapters/` | Reuse host monitoring/database tools and isolate DB syntax |
| Config loader | `src/config_loader.py` | Central YAML defaults and environment overrides |
| Context manager | `src/db.py`, `src/resilience.py` | Transaction and resource cleanup |
| Strategy/scoring helpers | `src/index_type_selection.py`, `src/algorithms/` | Compare index approaches without changing API shapes |
| Audit/mutation log | `src/audit.py`, schema initialization | Preserve operator evidence and lineage |

## 5) Known Architectural Risks

- `src/auto_indexer.py` is about 2,900 lines and owns several distinct responsibilities, making safe
  changes expensive.
- `pg_stat_statements` is representative only when the selected window contains real traffic.
- HypoPG currently plans one representative fingerprint per candidate, not a full regression set.
- Tenant aggregates and `expression_profile` are not joined in the main recommendation flow.
- API auth is a single shared operator token; hosted multi-user identity and roles are not present.
- The database adapter abstraction does not make the broader PostgreSQL-specific code portable.
- Candidate SQL supports only simple ascending, non-unique B-trees in the preview.
- Live-secret CI is trusted-branch only until a sanitized offline workload snapshot exists.

## 6) Evidence

- `src/query_executor.py`
- `src/stats.py`
- `src/auto_indexer.py`
- `src/index_type_selection.py`
- `src/api_server.py`
- `ui/lib/api.ts`
