"""PostgreSQL workload parsing through a maintained SQL AST.

The public contract in this module is deliberately small.  SQLGlot nodes do
not escape into the rest of IndexPilot, which keeps a future move to
libpg_query possible without changing report or auto-indexer shapes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

PARSER_BACKEND = "sqlglot_postgres_ast"
TENANT_KEY = "tenant_id"
_SUPPORTED_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class SQLPatternError(ValueError):
    """Raised when SQL cannot safely be treated as one read-only query."""


class ProposedIndexError(ValueError):
    """Raised when proposed index SQL is outside the supported review shape."""


def _proposed_index_identifier(node: exp.Expression | None, *, label: str) -> str:
    """Return an identifier using PostgreSQL's folding rules and launch limits."""
    if not isinstance(node, exp.Identifier):
        raise ProposedIndexError(f"{label}_identifier_required")

    name = node.name
    if node.args.get("quoted"):
        # The workload analyzer currently normalizes catalog metadata to lower
        # case. Reject case-sensitive names rather than reviewing a different
        # physical object from the one the operator supplied.
        if name != name.lower():
            raise ProposedIndexError("quoted_mixed_case_identifier_not_supported")
    else:
        name = name.lower()

    if not _SUPPORTED_IDENTIFIER_RE.fullmatch(name):
        raise ProposedIndexError(f"unsupported_{label}_identifier")
    return name


def _default_schema_identifier(default_schema: str) -> str:
    schema = default_schema.strip().lower()
    if not _SUPPORTED_IDENTIFIER_RE.fullmatch(schema):
        raise ProposedIndexError("unsupported_schema_identifier")
    return schema


def parse_proposed_index(sql: str, default_schema: str = "public") -> dict[str, Any]:
    """Parse one simple PostgreSQL B-tree ``CREATE INDEX`` for read-only review.

    The returned shape contains identifiers and metadata only. Callers must
    rebuild any HypoPG DDL from these identifiers; the supplied SQL is never an
    execution contract.

    IndexPilot's launch review supports plain ascending column keys. Features
    whose physical meaning would be lost by the existing hypothetical-index
    builder are rejected instead of being approximated.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ProposedIndexError("create_index_required")

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except ParseError as exc:
        raise ProposedIndexError("invalid_postgresql_sql") from exc

    if len(statements) != 1:
        raise ProposedIndexError("multiple_statements_not_supported")

    statement = statements[0]
    if (
        not isinstance(statement, exp.Create)
        or str(statement.args.get("kind", "")).upper() != "INDEX"
        or not isinstance(statement.this, exp.Index)
    ):
        raise ProposedIndexError("create_index_required")
    if statement.args.get("unique"):
        raise ProposedIndexError("unique_index_not_supported")

    unsupported_create_options = (
        "replace",
        "refresh",
        "expression",
        "properties",
        "indexes",
        "no_schema_binding",
        "begin",
        "clone",
        "clustered",
    )
    if any(statement.args.get(option) for option in unsupported_create_options):
        raise ProposedIndexError("create_index_options_not_supported")

    index = statement.this
    if any(index.args.get(option) for option in ("unique", "primary", "amp")):
        raise ProposedIndexError("index_options_not_supported")

    table = index.args.get("table")
    if not isinstance(table, exp.Table):
        raise ProposedIndexError("index_target_required")
    if table.catalog:
        raise ProposedIndexError("cross_database_target_not_supported")

    table_name = _proposed_index_identifier(table.args.get("this"), label="table")
    schema_node = table.args.get("db")
    schema_name = (
        _proposed_index_identifier(schema_node, label="schema")
        if schema_node is not None
        else _default_schema_identifier(default_schema)
    )

    index_name_node = index.args.get("this")
    index_name = (
        _proposed_index_identifier(index_name_node, label="index")
        if index_name_node is not None
        else None
    )

    parameters = index.args.get("params")
    if not isinstance(parameters, exp.IndexParameters):
        raise ProposedIndexError("index_columns_required")

    using = parameters.args.get("using")
    if using is not None and using.name.lower() != "btree":
        raise ProposedIndexError("btree_index_required")
    if parameters.args.get("include"):
        raise ProposedIndexError("include_columns_not_supported")
    if parameters.args.get("partition_by"):
        raise ProposedIndexError("partitioned_index_not_supported")
    if parameters.args.get("where") is not None:
        raise ProposedIndexError("partial_index_not_supported")
    if parameters.args.get("with_storage"):
        raise ProposedIndexError("index_storage_options_not_supported")
    if parameters.args.get("tablespace") is not None:
        raise ProposedIndexError("index_tablespace_not_supported")
    if parameters.args.get("on") is not None:
        raise ProposedIndexError("index_on_clause_not_supported")

    columns: list[str] = []
    key_expressions = parameters.args.get("columns") or []
    if not key_expressions:
        raise ProposedIndexError("index_columns_required")
    for ordered in key_expressions:
        if not isinstance(ordered, exp.Ordered) or not isinstance(ordered.this, exp.Column):
            raise ProposedIndexError("plain_column_keys_required")
        if ordered.args.get("desc"):
            raise ProposedIndexError("descending_index_keys_not_supported")
        if ordered.args.get("nulls_first"):
            raise ProposedIndexError("nulls_first_not_supported")

        column = ordered.this
        if column.table or column.db or column.catalog:
            raise ProposedIndexError("qualified_index_columns_not_supported")
        column_name = _proposed_index_identifier(column.args.get("this"), label="column")
        if column_name in columns:
            raise ProposedIndexError("duplicate_index_columns_not_supported")
        columns.append(column_name)

    return {
        "schema": schema_name,
        "table": table_name,
        "columns": columns,
        "index_name": index_name,
        "method": "btree",
        "concurrently": bool(statement.args.get("concurrently")),
        "if_not_exists": bool(statement.args.get("exists")),
        "normalized_sql": statement.sql(dialect="postgres"),
    }


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


def _predicate_context_for_table(
    statement: exp.Query,
    target: dict[str, Any],
    physical_tables: list[dict[str, Any]],
) -> dict[str, Any]:
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

    return {
        "equality_columns": equality_columns,
        "range_columns": range_columns,
        "order_columns": order_columns,
        "tenant_evidence": {
            "tenant_filtered": tenant_key is not None,
            "tenant_key": tenant_key,
            "source": "query_equality_predicate" if tenant_key else None,
        },
        "physical_scope": "shared_global_tenant_keyed" if tenant_key else "shared_global",
    }


def extract_proposed_index_query_context(
    query: str,
    table_columns: dict[tuple[str, str], set[str]],
    *,
    target_schema: str,
    target_table: str,
    candidate_columns: list[str],
    default_schema: str = "public",
) -> dict[str, Any] | None:
    """Return read-only workload context when a proposed leading key is used.

    Unlike automatic candidate extraction, this helper accepts equality-only
    queries. The index shape already came from the operator, so this boundary
    only establishes whether its leading key participates in a predicate or
    ordering expression on the requested physical table.
    """
    normalized_schema = target_schema.lower()
    normalized_table = target_table.lower()
    normalized_candidates = [column.lower() for column in candidate_columns]
    if not normalized_candidates:
        return None
    known_columns = table_columns.get((normalized_schema, normalized_table))
    normalized_known_columns = {item.lower() for item in known_columns or set()}
    if known_columns is None or any(
        column not in normalized_known_columns for column in normalized_candidates
    ):
        return None

    try:
        statement = parse_read_only_query(query)
    except SQLPatternError:
        return None

    physical_tables = _physical_tables(statement, table_columns, default_schema)
    targets = [
        target
        for target in physical_tables
        if target["schema"] == normalized_schema and target["table"] == normalized_table
    ]
    leading_column = normalized_candidates[0]
    for target in targets:
        context = _predicate_context_for_table(statement, target, physical_tables)
        leading_column_usage = [
            usage
            for usage, columns in (
                ("equality", context["equality_columns"]),
                ("range", context["range_columns"]),
                ("order", context["order_columns"]),
            )
            if leading_column in columns
        ]
        if not leading_column_usage:
            continue

        used_columns = {
            *context["equality_columns"],
            *context["range_columns"],
            *context["order_columns"],
        }
        return {
            "schema": normalized_schema,
            "table": normalized_table,
            "candidate_columns": normalized_candidates,
            "candidate_columns_used": [
                column for column in normalized_candidates if column in used_columns
            ],
            "leading_column": leading_column,
            "leading_column_usage": leading_column_usage,
            "query_fingerprint": canonical_query_fingerprint(statement),
            "parser_backend": PARSER_BACKEND,
            **context,
        }
    return None


def _pattern_for_table(
    statement: exp.Query,
    target: dict[str, Any],
    physical_tables: list[dict[str, Any]],
) -> dict[str, Any] | None:
    context = _predicate_context_for_table(statement, target, physical_tables)
    equality_columns = context["equality_columns"]
    range_columns = context["range_columns"]
    order_columns = context["order_columns"]

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
        "tenant_evidence": context["tenant_evidence"],
        "physical_scope": context["physical_scope"],
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
