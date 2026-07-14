# Coding Conventions

## 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Python files | `snake_case.py` | `index_lifecycle_manager.py` | `src/` |
| Python functions | `snake_case` | `analyze_and_create_indexes` | `src/auto_indexer.py` |
| Python types | `PascalCase` | `ConfigLoader`, `DatabaseAdapter` | `src/config_loader.py` |
| Constants/env vars | uppercase with underscores | `YAML_AVAILABLE`, `DB_PASSWORD` | `src/config_loader.py`, `src/db.py` |
| React components | `PascalCase.tsx` | `Header.tsx` | `ui/components/` |

## 2) Formatting and Linting

- Python formatter/linter: Ruff using `.ruff.toml`; Makefile owns format and check commands.
- Python static tools: mypy, Pyright, and Pylint with repository config files.
- TypeScript: strict compiler flags in `ui/tsconfig.json`; ESLint flat config in
  `ui/eslint.config.mjs`.
- Run commands: `make lint-check`, `make typecheck`, `make quality`, `cd ui && pnpm lint`.

## 3) Import and Module Conventions

- Standard-library imports precede third-party and `src.*` imports in representative source files.
- Backend code uses absolute `src.*` imports rather than relative imports.
- Installed public entry points live in `indexpilot/` and delegate domain work to existing `src.*`
  owners rather than duplicating planner policy.
- `src/schema/__init__.py` provides a public export surface for schema operations.
- The UI uses the `@/*` alias defined in `ui/tsconfig.json`.

## 4) Error and Logging Conventions

- Database operations generally use context managers and explicit commit/rollback behavior.
- API routes catch errors, log them, and translate them to `HTTPException`.
- Best-effort telemetry catches failures so it does not stop the primary operation.
- `src/db.py` redacts password, credential, secret, token, and key patterns from connection errors.
- Several modules use broad exception catches for graceful degradation; these can hide broken
  optional integrations and should be narrowed when those paths are promoted.

## 5) Testing Conventions

- Tests live in `tests/` and use `test_*.py` / `test_*` discovery from `pytest.ini`.
- `unittest.mock.patch` is used for algorithm and helper isolation.
- Live PostgreSQL tests initialize or mutate the demo schema directly.
- Parser and report tests use pure snapshots/fake HypoPG cursors and assert that raw SQL is absent
  from serialized artifacts.
- Coverage threshold: `[TODO]` no coverage tool or enforced threshold is configured.

## 6) Evidence

- `.ruff.toml`
- `mypy.ini`
- `pytest.ini`
- `src/db.py`
- `src/api_server.py`
- `ui/eslint.config.mjs`
- `ui/tsconfig.json`
