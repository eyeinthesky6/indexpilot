# Testing Patterns

## 1) Test Stack and Commands

- Primary framework: pytest, pinned as 7.4.3 in `requirements.txt`.
- Assertions: native Python `assert`; mocking: `unittest.mock`.

```bash
python -m pytest tests -q
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
| API smoke | CI gap | FastAPI routes | manually verified in launch review; no committed route tests |
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
- Current launch evidence after safety tests: 74 tests pass against PostgreSQL 15.
- Known gaps: API auth/failure cases, dashboard behavior, packaging install, workload ingestion,
  HypoPG validation, and production apply/rollback trials.

## 6) Evidence

- `pytest.ini`
- `tests/test_auto_indexer.py`
- `tests/test_simulator.py`
- `tests/test_schema_mutations.py`
- `tests/test_config_loader.py`
- `.github/workflows/ci.yml`
