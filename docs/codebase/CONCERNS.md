# Codebase concerns

## 1) Top risks

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Planner review checks one representative query | `src/workload_dna.py` | A positive verdict can miss regressions elsewhere | Add workload-wide production-copy replay before stronger claims |
| Resolved | Public package availability | `pyproject.toml`, `README.md` | Users can install the published alpha with pipx | Keep PyPI Trusted Publishing and release verification green |
| Medium | Old public tag conflicts with preview maturity | Git tag `v1.0.0-stable`, `pyproject.toml` | Users may mistake historical code for the supported line | Point users to `v1.1.0a3`; keep the old tag explicitly historical |
| Medium | Historical docs contain production-ready claims | `docs/features/`, `docs/tech/` | Search visitors can see stale claims | Keep canonical navigation and historical banners; migrate only proven material |
| Medium | API has only single-operator authentication | `src/api_auth.py`, `SECURITY.md` | No hosted users, roles, expiry, or revocation | Keep private; add OIDC/RBAC only for a real hosted product |
| Medium | Tenant-specific legacy path is incomplete | `src/stats.py`, `src/auto_indexer.py` | Broader DNA claims exceed evidence | Keep tenant metadata out of launch positioning until workload decisions prove it |
| Medium | Fork-safe review input is absent | `docs/GITHUB_ACTIONS.md`, `src/workload_dna.py` | Live database secrets cannot be exposed to untrusted PR code | Add a versioned sanitized offline workload snapshot before an official Action |

## 2) Technical debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Large legacy package surface | Wheel includes all of `src` for compatibility | `pyproject.toml` | More maintenance and imports than the CLI needs | Split only after stable public contracts and deprecation plan |
| Oversized decision owner | Sprint features accumulated in one module | `src/auto_indexer.py` | Safe changes are expensive | Characterize behavior before extracting stable seams |
| Research names exceed implementations | Modules adapt ideas to normal PostgreSQL indexes | `src/algorithms/` | Users can infer learned-index implementations | Keep them experimental and use precise descriptions |
| Compatibility requirements are broad | Historical full-stack source workflow | `requirements.txt` | Dev installs are larger than the core package | Treat `pyproject.toml` as the public dependency contract |
| Report directories are repo-shaped in DNA alias | Legacy helper writes under `docs/audit` | `src/paths.py`, `indexpilot/cli.py` | Installed alias can create surprising folders | Public `review` uses neutral output; deprecate alias path later |

## 3) Security concerns

| Risk | Evidence | Current mitigation | Gap |
|------|----------|--------------------|-----|
| Shared API bearer token | `src/api_auth.py` | Fail-closed default and non-loopback guard | No user identity, expiry, or revocation |
| Sensitive report metadata | `src/workload_dna.py` | Raw SQL replaced with fingerprints | Names, counts, and sizes still require sharing review |
| Proposed SQL input | `src/sql_parser.py` | One AST statement, narrow shape, identifiers rebuilt | Additional physical index shapes remain unsupported |
| Historical secret-scan match | old `docs/SSL_QUICK_SUMMARY.md` commit | Not present in current tree | Confirm whether the old 63-character password-like value was ever real and rotate if so |
| Apply mode changes DB objects | `src/auto_indexer.py` | Separate legacy path, advisory default, gates, audit | No mandatory full-workload replay receipt |

## 4) Performance and proof gaps

- Planner cost is not measured latency.
- Index size, build duration, write amplification, cache effects, and rollback time are not measured
  by the public review command.
- Physical bloat and index-attributable write overhead are deliberately `not_measured`; the
  compatibility dashboard no longer invents values from scan counts or fixed percentages.
- `pg_stat_statements` can be empty or unrepresentative after reset/restart or before real traffic.
- The preview supports simple B-trees only; partial, expression, INCLUDE, and specialized indexes
  need separate evidence models.

## 5) Decisions resolved for launch

1. The first focused release is an evaluation CLI, not a supported production service.
2. The dashboard stays an optional, private, single-operator compatibility surface.
3. `pg_stat_statements` ingestion, packaging, exact proposal review, and JSON/Markdown artifacts are
   the launch path.
4. DNA remains an internal report model and compatibility alias, not the headline positioning.
5. The product name is unchanged until a real naming notice or conflict requires review.

## 6) `[ASK USER]` questions

None. The current launch direction resolves the earlier product-boundary questions. The alpha is
published through PyPI Trusted Publishing; no unresolved code-design choice remains for it.

## 7) Evidence

- `README.md`
- `pyproject.toml`
- `indexpilot/cli.py`
- `src/sql_parser.py`
- `src/workload_dna.py`
- `src/auto_indexer.py`
- `.github/workflows/ci.yml`
- `SECURITY.md`
