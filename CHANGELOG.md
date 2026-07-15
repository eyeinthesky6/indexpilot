# Changelog

All notable changes to the focused public package are documented here.

## Unreleased

### Added

- Problem-led public guides for index justification, planner selection, overlap, hypothetical
  testing, and trusted CI review.
- A standards-compatible agent skill with concrete trigger phrases and safe verdict handling.
- A composite GitHub Action for protected branches, reviewed commits, and sanitized databases.

### Changed

- The homepage, sitemap, README, and `llms.txt` now connect user-described PostgreSQL index pains
  directly to the supported IndexPilot workflow.

## 1.1.0a3 - 2026-07-15

### Changed

- Replaced research-style public copy with a direct outcome: stop bad PostgreSQL indexes before
  they reach production.
- Aligned the package summary, README, website metadata, and agent discovery copy around the same
  user-facing promise.

## 1.1.0a2 - 2026-07-15

### Added

- Public launch documentation, agent guidance, GitHub Pages discovery files, and a reusable
  open-source launch playbook.
- PyPI Trusted Publishing support for alpha releases so the public package can be verified before a
  stable release.

### Changed

- Repository positioning, installation guidance, contributor routes, and search metadata now point
  to the same benchmark-before-merge product boundary.

## 1.1.0a1 - 2026-07-14

### Added

- `indexpilot review` as the public read-only command.
- Exact review for one simple proposed PostgreSQL B-tree index.
- Batch review for supported `CREATE INDEX` statements in a migration file.
- Read-only `doctor` and conservative existing-index `audit` commands.
- Offline before/after usage observation and SARIF output for CI workflows.
- Stable review verdicts and Markdown report output.
- Existing-index comparability checks for validity, readiness, predicates, expressions, access
  method, operator classes, collations, and sort order.
- Pooled-session HypoPG isolation so stale hypothetical indexes cannot contaminate baselines.
- Clean package build and command smoke tests across Python 3.10–3.13 in CI.
- Focused installation, usage, roadmap, issue, contribution, and release documentation.

### Changed

- Public positioning now focuses on local PostgreSQL index review instead of automatic indexing.
- Legacy cleanup, inferred bloat, automatic reindex, and estimated write-cost paths remain outside the
  public recommendation contract; public overlap findings never emit drop advice.
- Migration-internal overlap and duplicate index names now participate in SARIF and the opt-in
  `existing_overlap` CI gate.
- Legacy cleanup ownership requires an exact same-table `mode=apply` audit receipt; lifecycle and
  VACUUM helpers default to dry-run and quote catalog identifiers safely.
- The Husky pre-commit hook now resolves the UI package directory and runs its lint gate without
  requiring a live authenticated API for type generation.
- SQL parsing uses SQLGlot’s PostgreSQL AST boundary.
- Development dependencies no longer rely on known-vulnerable historical pins.
- Python type aliases remain compatible with Python 3.10 while supporting FastAPI/Pydantic runtime
  schema generation.
- Optional academic/ML algorithm exports now load lazily, keeping the core review install light.

### Security

- The API remains fail-closed with a required bearer token by default.
- The public review command never executes supplied candidate SQL or physical DDL.
- Minimum `python-dotenv` and pytest versions include the first patched releases for the two
  default-branch dependency alerts current at launch review time.
- Dashboard dependencies were refreshed within their supported major lines; `pnpm audit` reports no
  known vulnerabilities for the committed lockfile.

## Historical repository tag

The older `v1.0.0-stable` tag predates the installable focused package and this changelog. It is kept
for history but is not a supported production release line.
