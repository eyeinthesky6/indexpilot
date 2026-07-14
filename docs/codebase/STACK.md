# Technology Stack

## 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python backend; TypeScript/React dashboard | `requirements.txt`, `ui/package.json` |
| Runtime + version | Python 3.10–3.13 package contract; Node 20.9+ for optional UI | `pyproject.toml`, `ui/package.json` |
| Package manager | Python `pyproject.toml`; compatibility requirements file; pnpm for UI | `pyproject.toml`, `requirements.txt`, `ui/pnpm-lock.yaml` |
| Module/build system | Installable `indexpilot` package over legacy `src`; Next.js App Router UI | `pyproject.toml`, `indexpilot/`, `ui/app/` |

## 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| PostgreSQL | 15-alpine in demo | Primary database and metadata store | `docker-compose.yml` |
| psycopg2-binary | >=2.9.9 | PostgreSQL connections and SQL composition | `requirements.txt`, `src/db.py` |
| FastAPI | 0.115.0 | Dashboard HTTP API | `requirements.txt`, `src/api_server.py` |
| Uvicorn | 0.32.0 | ASGI server | `requirements.txt`, `run_api.py` |
| PyYAML | 6.0.1 | Product and schema configuration | `requirements.txt`, `src/config_loader.py` |
| SQLGlot | 30.x | PostgreSQL AST parsing for workload DNA | `pyproject.toml`, `src/sql_parser.py` |
| typing-extensions | 4.12+ | Recursive JSON type alias on Python 3.10+ | `pyproject.toml`, `src/type_definitions.py` |
| NumPy/SciPy/scikit-learn/XGBoost | mixed pinned ranges | Statistical and ML-assisted scoring | `requirements.txt`, `src/algorithms/` |
| Next.js/React | Next 16, React 19 | Dashboard | `ui/package.json`, `ui/app/` |

## 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| pytest | Backend unit/integration tests | `pytest.ini`, `tests/` |
| Ruff | Python lint and format | `.ruff.toml`, `Makefile` |
| mypy, Pyright, Pylint | Python static checks | `mypy.ini`, `pyrightconfig.json`, `pylintrc` |
| ESLint, TypeScript | Dashboard lint and type checks | `ui/eslint.config.mjs`, `ui/tsconfig.json` |
| GitHub Actions | Backend tests and dashboard lint/build | `.github/workflows/ci.yml` |

## 4) Key Commands

```bash
python -m pip install -e ".[dev,api,ml]"
indexpilot review --help
docker compose up -d postgres
python -m pytest tests -q
python scripts/check_unsafe_db_access.py
cd ui && pnpm install --frozen-lockfile && pnpm lint && pnpm build
```

## 5) Environment and Config

- Config sources: `indexpilot_config.yaml`, `schema_config.yaml.example`, environment overrides.
- Production database credentials: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
  `DB_SSLMODE`; `SUPABASE_DB_URL` is also supported by `src/db.py`.
- The public `indexpilot review` path is always advisory. Apply-mode configuration belongs only to
  the historical auto-indexer compatibility surface.
- API auth: `INDEXPILOT_API_TOKEN`; required by default for all routes except `/` liveness.
- The bearer token is a single-operator control; hosted multi-user identity/RBAC is not implemented.
- Runtime, API, ML, and development dependencies are separated in `pyproject.toml`;
  `requirements.txt` remains for compatibility with the existing full source-checkout workflow.

## 6) Evidence

- `requirements.txt`
- `ui/package.json`
- `docker-compose.yml`
- `src/db.py`
- `src/config_loader.py`
- `.github/workflows/ci.yml`
