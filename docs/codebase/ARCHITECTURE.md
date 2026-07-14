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

pg_stat_statements -> SQL AST -> DNA candidate -> optional HypoPG -> auto-indexer advisory review
```

1. The host calls `log_query_stat()`; the generic query executor does not do this automatically.
2. `src.stats` batches and stores workload rows in `query_stats`.
3. `src.auto_indexer` aggregates fields and evaluates thresholds, patterns, plans, and safeguards.
4. `src.index_type_selection` and algorithm helpers score PostgreSQL-supported index strategies.
5. Advisory mode records evidence; apply mode executes DDL and records the result.
6. The API reads health, performance, decisions, and lifecycle state for the dashboard.

## 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| Configuration | Defaults, YAML loading, environment overrides | Database DDL | `src/config_loader.py` |
| Persistence | Connections, transactions, typed cursor helpers | Product scoring | `src/db.py` |
| Workload | Query-stat collection and aggregates | HTTP API | `src/stats.py` |
| SQL parsing | PostgreSQL AST to product-owned pattern contract | DDL or planner decisions | `src/sql_parser.py` |
| Decision/apply | Candidate scoring, gates, advisory/apply path | UI rendering | `src/auto_indexer.py` |
| Lifecycle | Cleanup, refresh, reindex scheduling and dry-runs | Authentication | `src/index_lifecycle_manager.py` |
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
- Workload collection is outside the normal query-execution path, so the product is not automatic
  without host integration.
- Tenant aggregates and `expression_profile` are not joined in the main recommendation flow.
- API auth is a single shared operator token; hosted multi-user identity and roles are not present.
- The database adapter abstraction does not make the broader PostgreSQL-specific code portable.

## 6) Evidence

- `src/query_executor.py`
- `src/stats.py`
- `src/auto_indexer.py`
- `src/index_type_selection.py`
- `src/api_server.py`
- `ui/lib/api.ts`
