# External Integrations

## 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| PostgreSQL | Database | Host data, product metadata, query stats, mutations | URL or DB env credentials | High | `src/db.py` |
| FastAPI/Uvicorn | HTTP service | Dashboard and lifecycle API | None in repo | Medium | `src/api_server.py`, `run_api.py` |
| Host adapters | In-process interface | Monitoring, DB pool, audit, logging, error tracking | Host-owned | Medium | `src/adapters.py` |
| Next.js dashboard | HTTP client | Reads API metrics and decisions | None in repo | Medium | `ui/lib/api.ts` |
| Supabase Postgres | Optional database URL | Alternate PostgreSQL connection source | `SUPABASE_DB_URL` | Low | `src/db.py` |

## 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| Host PostgreSQL schema | Tables being analyzed/indexed | `src.db`, validated SQL helpers | Apply mode changes physical indexes | `src/auto_indexer.py` |
| IndexPilot metadata tables | Genome, expressions, stats, mutation/audit history | `src.schema`, `src.stats`, `src.audit` | Shares host DB lifecycle and permissions | `src/schema/initialization.py` |
| In-memory caches/buffers | Stats batching, validation, plans, production cache | module-level owners | State is process-local | `src/stats.py`, `src/production_cache.py` |

## 3) Secrets and Credentials Handling

- Credentials come from `SUPABASE_DB_URL` or individual `DB_*` environment variables.
- Production mode requires `DB_PASSWORD`; development has a documented default for the Docker demo.
- `.env.production.example` contains placeholders only and `.gitignore` excludes real `.env*` files.
- Rotation lifecycle: `[TODO]` owned by the host deployment; no secrets-manager integration exists.

## 4) Reliability and Failure Behavior

- Index retry uses exponential-backoff helpers in `src/index_retry.py`.
- Query and statement timeouts are configured through `src/query_timeout.py` and config defaults.
- Optional monitoring and research helpers commonly degrade through logged exceptions.
- The bypass system can disable features or the full system; advisory mode avoids DDL by default.

## 5) Observability for Integrations

- Structured logging setup is attempted at API startup.
- Host monitoring/error/audit adapters can receive events through `src/adapters.py`.
- Mutation and audit data are persisted in PostgreSQL.
- Gap: no distributed tracing and no durable external monitoring unless a host adapter is configured.

## 6) Evidence

- `src/db.py`
- `src/adapters.py`
- `src/audit.py`
- `src/index_retry.py`
- `.env.production.example`
- `SECURITY.md`
