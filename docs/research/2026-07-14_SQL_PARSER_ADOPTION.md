# SQL Parser Adoption Record

## Need

The first workload DNA preview used regular expressions to identify tables, filters, and ordering.
That was enough for a narrow demo, but not reliable for CTEs, aliases, joins, quoted identifiers, or
nested PostgreSQL syntax.

## Options evaluated

| Option | Result | Reason |
|---|---|---|
| `pg-query-python` 0.1.3 | Not adopted as a required dependency | BSD-3-Clause and based on `libpg_query`, but beta and the Windows install trial failed because no Windows wheel was available. |
| `pglast` / old `pg_query` | Not adopted | Mature PostgreSQL AST, but GPLv3+ is a poor fit for IndexPilot's MIT distribution. |
| Dexter's Ruby parser stack | Not embedded | Dexter uses PostgreSQL parser tooling well, but importing a Ruby runtime would make the Python package heavier. |
| SQLGlot 30.12 | Adopted behind an adapter | MIT, pure Python, no dependencies, maintained PostgreSQL dialect, Windows-compatible wheel, and passed the representative query trial. |

## Trial evidence

The isolated Windows trial parsed:

- `$1`-style PostgreSQL parameters;
- PostgREST-style CTEs;
- quoted schema/table/column identifiers;
- `= ANY($n)` predicates;
- joins and aliases;
- tenant equality plus timestamp ranges and ordering.

The same trial showed `pg-query-python==0.1.3` falling back to a source build and failing during its
native `libpg_query` build path on Windows.

## Integration and rollback

`src.sql_parser` is the product-owned contract. It returns plain dictionaries to workload DNA, so a
future `libpg_query` backend can replace SQLGlot without changing reports or auto-indexer code.
Rollback is a normal dependency/code revert; no database changes are involved.

## Primary sources

- SQLGlot repository and PostgreSQL dialect: https://github.com/tobymao/sqlglot
- SQLGlot API: https://sqlglot.com/
- `pg-query-python` package: https://pypi.org/project/pg-query-python/
- `libpg_query`: https://github.com/pganalyze/libpg_query
- Dexter: https://github.com/ankane/dexter
