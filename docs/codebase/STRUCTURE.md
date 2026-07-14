# Codebase Structure

## 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `src/` | Backend domain logic, database access, API, safeguards, algorithms | `src/api_server.py`, `src/auto_indexer.py` |
| `src/algorithms/` | Research-inspired scoring and recommendation helpers | `src/algorithms/__init__.py` |
| `src/database/` | Database type detection and adapter interfaces | `src/database/adapters/base.py` |
| `src/schema/` | Schema discovery, validation, initialization, change detection | `src/schema/__init__.py` |
| `src/simulation/` | Demo workload and scenario runners | `src/simulation/simulator.py` |
| `tests/` | Pytest suite, including live PostgreSQL paths | `pytest.ini`, `tests/test_simulator.py` |
| `ui/` | Next.js dashboard | `ui/package.json`, `ui/app/` |
| `scripts/` | Setup, validation, benchmark, and operational commands | `scripts/assess_setup.py` |
| `docs/` | Product, installation, research, review, and test documentation | `docs/DOCUMENTATION_INDEX.md` |

## 2) Entry Points

- API entry: `run_api.py` loads `src.api_server:app` with Uvicorn.
- Simulation entry: `python -m src.simulation.simulator` through Makefile targets.
- Database setup: `src.schema.init_schema()` and genome bootstrap commands in `Makefile`.
- Auto-index analysis: direct call to `src.auto_indexer.analyze_and_create_indexes()`; no packaged CLI
  exists.
- Dashboard entry: Next.js scripts in `ui/package.json`.

## 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `src/db.py` | Connection configuration, pool, cursor helpers | Index-selection policy |
| `src/stats.py` | Query-stat persistence and aggregation | DDL application |
| `src/auto_indexer.py` | Candidate decision, safeguards, advisory/apply result | HTTP presentation |
| `src/schema/` | Metadata schema and discovery | Dashboard behavior |
| `src/api_server.py` | HTTP translation for dashboard data and lifecycle calls | A second index decision engine |
| `ui/` | Rendering and API consumption | Direct database access |

## 4) Naming and Organization Rules

- Python files and functions use `snake_case`; classes use `PascalCase`.
- React component files use `PascalCase`; route files follow Next.js `page.tsx` naming.
- Backend imports use absolute `src.*` paths. Copy-over docs describe rewriting them to
  `indexpilot.*`, which is not automated.
- Organization is mostly capability-based modules in a flat `src/`, with subdirectories for
  algorithms, database adapters, schema, and simulation.

## 5) Evidence

- `run_api.py`
- `Makefile`
- `src/api_server.py`
- `src/auto_indexer.py`
- `ui/package.json`
