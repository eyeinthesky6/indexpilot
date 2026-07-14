# Changelog

All notable changes to the focused public package are documented here.

## 1.1.0a1 - Unreleased

### Added

- `indexpilot review` as the public read-only command.
- Exact review for one simple proposed PostgreSQL B-tree index.
- Stable review verdicts and Markdown report output.
- Existing-index comparability checks for validity, readiness, predicates, expressions, access
  method, operator classes, collations, and sort order.
- Pooled-session HypoPG isolation so stale hypothetical indexes cannot contaminate baselines.
- Clean package build and command smoke tests across Python 3.10–3.13 in CI.
- Focused installation, usage, roadmap, issue, contribution, and release documentation.

### Changed

- Public positioning now focuses on local PostgreSQL index review instead of automatic indexing.
- SQL parsing uses SQLGlot’s PostgreSQL AST boundary.
- Development dependencies no longer rely on known-vulnerable historical pins.
- Python type aliases remain compatible with Python 3.10 while supporting FastAPI/Pydantic runtime
  schema generation.
- Optional academic/ML algorithm exports now load lazily, keeping the core review install light.

### Security

- The API remains fail-closed with a required bearer token by default.
- The public review command never executes supplied candidate SQL or physical DDL.
- Dashboard dependencies were refreshed within their supported major lines; `pnpm audit` reports no
  known vulnerabilities for the committed lockfile.

## Historical repository tag

The older `v1.0.0-stable` tag predates the installable focused package and this changelog. It is kept
for history but is not a supported production release line.
