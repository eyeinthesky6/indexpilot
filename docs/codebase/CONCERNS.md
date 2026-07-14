# Codebase Concerns

## 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Workload collection is manual | `src/query_executor.py`, `src/stats.py` | “Automatic” recommendations can have no input | Add a workload-source contract and `pg_stat_statements` adapter |
| Medium | API has only single-operator authentication | `src/api_auth.py`, `SECURITY.md` | No separate users or roles for hosted SaaS | Keep private or add OIDC/RBAC before multi-user hosting |
| Medium | Package is not published | `pyproject.toml`, `README.md` | Install works from source but not from PyPI | Publish only after release/tag ownership is decided |
| Medium | Tenant-specific path is incomplete | `src/stats.py`, `src/auto_indexer.py` | Product niche is not fully realized | Carry tenant context through aggregation and policy |
| Medium | Production proof is one bounded workload | `src/workload_dna.py`, case study | False-positive rate across systems is unknown | Run multi-week shadow trials before production claims |
| Medium | Oversized decision owner | `src/auto_indexer.py` | Review and change risk | Characterize, then split by stable contracts |

## 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Research names exceed implementations | Modules adapt concepts to normal Postgres indexes | `src/algorithms/`, old feature docs | Trust and maintenance cost | Keep honest naming and measure each helper's lift |
| Duplicate canary setup in query executor | Phase additions were appended twice | `src/query_executor.py` | Confusing state and extra work per query | Remove after targeted behavior tests |
| Compatibility requirements remain broad | Historical full-stack workflow | `requirements.txt`, `pyproject.toml` | Source checkout install is larger than core package | Keep `pyproject.toml` as the public dependency contract |
| PostgreSQL abstraction is partial | Adapter covers a small SQL surface | `src/database/adapters/`, broader `src/` | Multi-database claims drift | State PostgreSQL-only or complete a proven adapter boundary |
| Historical docs conflict | Many completion reports predate current review | `docs/archive/`, `docs/features/` | Users cannot identify current truth | Make README and dated review canonical; archive stale claims |

## 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| Shared bearer token | A01 Broken Access Control | `src/api_auth.py` | fail-closed default, constant-time compare, non-loopback startup guard | no user identity, roles, token expiry, or revocation service |
| Raw exception detail in API errors | A05 Security Misconfiguration | `src/api_server.py` | logging and DB credential redaction | internal errors can be returned to clients |
| Apply mode changes DB objects | N/A | `src/auto_indexer.py` | advisory default, validation, gates, audit | no mandatory hypothetical/shadow evidence |
| Demo credentials | N/A | `docker-compose.yml` | production requires env password | users must not reuse demo config remotely |

## 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Large synchronous decision loop | `src/auto_indexer.py` | many DB and helper calls per field | long runs and lock exposure | profile real workloads before decomposition |
| Process-local caches/buffers | `src/stats.py`, `src/production_cache.py` | state differs by worker | loss/duplication in multi-instance runs | use DB/source-of-truth aggregation |
| Query interception can EXPLAIN requests | `src/query_interceptor.py` | extra planning work | request latency under load | sample/cache and publish overhead budgets |

## 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `src/auto_indexer.py` | 2,900 lines and many responsibilities | scan largest source file; no recent 90-day history | add characterization tests before seams change |
| `src/query_interceptor.py` | parsing, rate limits, plans, caches | over 1,000 lines | keep contract tests around allow/block cases |
| `src/index_lifecycle_manager.py` | cleanup and DDL scheduling | about 960 lines | default to dry-run and verify receipts |
| Historical docs | claims are duplicated across many files | 90+ commits, large docs tree | update one canonical current review |

## 6) `[ASK USER]` Questions

1. [ASK USER] Is the first named release an evaluation toolkit or a supported production service?
2. [ASK USER] Should the dashboard stay local/private, or must hosted multi-user access be supported?
3. [ASK USER] Should packaging plus `pg_stat_statements` ingestion be the next milestone?

## 7) Evidence

- Repository scan output recorded in `docs/reviews/2026-07-13_open_source_launch_architectural_review.md`
- `src/query_executor.py`
- `src/auto_indexer.py`
- `src/api_server.py`
- `docs/reviews/2026-07-13_open_source_launch_architectural_review.md`
