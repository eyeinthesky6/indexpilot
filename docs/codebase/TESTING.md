# Testing Patterns

## 1) Test Stack and Commands

- Primary framework: pytest 8.4–9.x through package/development ranges.
- Assertions: native Python `assert`; mocking: `unittest.mock`.

```bash
python -m pytest tests -q
python -m pytest tests/test_cli.py tests/test_proposed_index_parser.py tests/test_workload_dna.py -q
python -m pytest tests/test_auto_indexer.py -q
python scripts/check_unsafe_db_access.py
cd ui && pnpm lint && pnpm build
```

## 2) Test Layout

- Backend tests are in `tests/` and follow `test_*.py` / `test_*` discovery.
- There is no shared `tests/conftest.py`; database setup is local to test modules or test functions.
- Algorithm tests use mocks for database/config boundaries.
- Simulator, genome, and schema-mutation tests use a live PostgreSQL demo database.

## 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | scoring math, retry, storage, workload helpers | many DB calls mocked |
| Integration | Partial | schema, genome, simulator, auto-index smoke | PostgreSQL required |
| API smoke | Yes | auth middleware and OpenAPI boundary | `tests/test_api_auth.py` |
| Package/CLI | Yes | imports, help, routing, JSON/Markdown output | `tests/test_package_surface.py`, `tests/test_cli.py` |
| SQL parser | Yes | read-only queries and constrained proposed indexes | `tests/test_proposed_index_parser.py` |
| UI build | CI only | lint and Next.js build | no browser/e2e suite |
| Real workload | No | adopter query stream and apply/rollback lifecycle | deferred launch milestone |

## 4) Mocking and Isolation Strategy

- `unittest.mock.patch` replaces config and database functions in focused tests.
- Live schema tests clean known temporary columns but share the same database.
- Common failure mode: tests hang or fail when PostgreSQL is not running; this was observed before
  starting the Compose service.

## 5) Coverage and Quality Signals

- Coverage tool and threshold: `[TODO]` not configured.
- Current reported coverage: `[TODO]` not measured.
- Current launch evidence: 135 tests pass against an isolated PostgreSQL 15 container; 127 pass
  without a database and the remaining eight are explicitly database-backed.
- CI builds and installs wheels on Python 3.10–3.13; full backend tests run with PostgreSQL 15.
- Known gaps: browser/E2E dashboard behavior, live HypoPG on PostgreSQL 16+, workload-wide replay,
  and production apply/rollback trials.

## 6) Evidence

- `pytest.ini`
- `tests/test_auto_indexer.py`
- `tests/test_simulator.py`
- `tests/test_schema_mutations.py`
- `tests/test_config_loader.py`
- `.github/workflows/ci.yml`
