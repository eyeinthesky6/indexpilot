"""PostgreSQL workload parsing through a maintained SQL AST.

The public contract in this module is deliberately small.  SQLGlot nodes do
not escape into the rest of IndexPilot, which keeps a future move to
libpg_query possible without changing report or auto-indexer shapes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

PARSER_BACKEND = "sqlglot_postgres_ast"
TENANT_KEY = "tenant_id"


class SQLPatternError(ValueError):
    """Raised when SQL cannot safely be treated as one read-only query."""


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def parse_read_only_query(query: str) -> exp.Query:
    """Parse exactly one PostgreSQL query and reject mutating statements."""
    try:
        statements = sqlglot.parse(query, read="postgres")
    except ParseError as exc:
        raise SQLPatternError("invalid_postgresql_sql") from exc

    if len(statements) != 1:
        raise SQLPatternError("multiple_statements_not_supported")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLPatternError("non_select_statement")
    return statement


def canonical_query_fingerprint(statement: exp.Query) -> str:
    """Return a value-free fingerprint so equivalent query shapes group."""

    def remove_values(node: exp.Expression) -> exp.Expression:
        if isinstance(node, (exp.Literal, exp.Parameter, exp.Placeholder)):
            return exp.Placeholder()
        return node

    canonical = statement.copy().transform(remove_values).sql(dialect="postgres")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _conjuncts(expression: exp.Expression | None) -> Iterator[exp.Expression]:
    """Yield AND predicates left-to-right, preserving the SQL's useful order."""
    if expression is None:
        return
    if isinstance(expression, exp.And):
        yield from _conjuncts(expression.this)
        yield from _conjuncts(expression.expression)
        return
    yield expression


def _physical_tables(
    statement: exp.Query,
    table_columns: dict[tuple[str, str], set[str]],
    default_schema: str,
) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for table_node in statement.find_all(exp.Table):
        schema = (table_node.db or default_schema).lower()
        table = table_node.name.lower()
        key = (schema, table)
        if key not in table_columns:
            # CTE aliases and unrelated schemas are not physical targets.
            continue
        alias = table_node.alias_or_name.lower()
        identity = (schema, table, alias)
        if identity in seen:
            continue
        seen.add(identity)
        tables.append(
            {
                "schema": schema,
                "table": table,
                "alias": alias,
                "columns": {column.lower() for column in table_columns[key]},
            }
        )
    return tables


def _column_for_table(
    expression: exp.Expression,
    target: dict[str, Any],
    physical_tables: list[dict[str, Any]],
) -> str | None:
    columns = list(expression.find_all(exp.Column))
    if not columns:
        return None

    target_qualifiers = {target["alias"], target["table"]}
    for column in columns:
        name = column.name.lower()
        if name not in target["columns"]:
            continue
        qualifier = column.table.lower() if column.table else ""
        if qualifier:
            if qualifier in target_qualifiers:
                return name
            continue

        # An unqualified name is safe only when it maps to one physical table.
        matching_tables = [item for item in physical_tables if name in item["columns"]]
        if len(matching_tables) == 1 and matching_tables[0] is target:
            return name
    return None


def _predicate_expressions(statement: exp.Query) -> Iterable[exp.Expression]:
    for where in statement.find_all(exp.Where):
        yield from _conjuncts(where.this)
    for join in statement.find_all(exp.Join):
        yield from _conjuncts(join.args.get("on"))


def _pattern_for_table(
    statement: exp.Query,
    target: dict[str, Any],
    physical_tables: list[dict[str, Any]],
) -> dict[str, Any] | None:
    equality_columns: list[str] = []
    range_columns: list[str] = []

    equality_types = (exp.EQ, exp.In)
    range_types = (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.NEQ, exp.Like, exp.ILike, exp.Is)

    for predicate in _predicate_expressions(statement):
        column = _column_for_table(predicate, target, physical_tables)
        if column is None:
            continue
        if isinstance(predicate, equality_types):
            _append_unique(equality_columns, column)
        elif isinstance(predicate, range_types):
            _append_unique(range_columns, column)

    # A tenant key affects physical layout only when the query filters on it.
    tenant_key = TENANT_KEY if TENANT_KEY in equality_columns else None
    if tenant_key:
        equality_columns = [tenant_key, *[item for item in equality_columns if item != tenant_key]]

    order_columns: list[str] = []
    for order in statement.find_all(exp.Order):
        for ordered in order.expressions:
            column = _column_for_table(ordered, target, physical_tables)
            if column is not None:
                _append_unique(order_columns, column)

    candidate_columns: list[str] = []
    for column in equality_columns + range_columns + order_columns:
        _append_unique(candidate_columns, column)
    candidate_columns = candidate_columns[:3]

    if not equality_columns or not (range_columns or order_columns):
        return None
    if len(candidate_columns) < 2:
        return None

    return {
        "schema": target["schema"],
        "table": target["table"],
        "equality_columns": equality_columns,
        "range_columns": range_columns,
        "order_columns": order_columns,
        "candidate_columns": candidate_columns,
        "tenant_evidence": {
            "tenant_filtered": tenant_key is not None,
            "tenant_key": tenant_key,
            "source": "query_equality_predicate" if tenant_key else None,
        },
        "physical_scope": "shared_global_tenant_keyed" if tenant_key else "shared_global",
    }


def extract_postgres_query_pattern(
    query: str,
    table_columns: dict[tuple[str, str], set[str]],
    default_schema: str = "public",
) -> dict[str, Any] | None:
    """Extract the strongest safe index pattern from one PostgreSQL query."""
    try:
        statement = parse_read_only_query(query)
    except SQLPatternError:
        return None

    physical_tables = _physical_tables(statement, table_columns, default_schema)
    patterns = [
        pattern
        for target in physical_tables
        if (pattern := _pattern_for_table(statement, target, physical_tables)) is not None
    ]
    if not patterns:
        return None

    pattern = max(
        patterns,
        key=lambda item: (
            len(item["candidate_columns"]),
            len(item["equality_columns"]),
            len(item["range_columns"]),
        ),
    )
    pattern["query_fingerprint"] = canonical_query_fingerprint(statement)
    pattern["parser_backend"] = PARSER_BACKEND
    return pattern
