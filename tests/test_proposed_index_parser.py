import pytest

from src.sql_parser import (
    ProposedIndexError,
    extract_postgres_query_pattern,
    extract_proposed_index_query_context,
    parse_proposed_index,
)

TABLE_COLUMNS = {
    ("public", "orders"): {"id", "tenant_id", "status", "created_at"},
    ("public", "tenants"): {"id", "name"},
}


def test_parses_one_plain_concurrent_btree_index():
    proposed = parse_proposed_index(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_tenant_created
        ON public.orders (tenant_id, created_at)
        """
    )

    assert proposed == {
        "schema": "public",
        "table": "orders",
        "columns": ["tenant_id", "created_at"],
        "index_name": "idx_orders_tenant_created",
        "method": "btree",
        "concurrently": True,
        "if_not_exists": True,
        "normalized_sql": (
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_tenant_created "
            "ON public.orders(tenant_id, created_at)"
        ),
    }


def test_uses_default_schema_and_postgresql_identifier_folding():
    proposed = parse_proposed_index(
        "CREATE INDEX IDX_ORDERS_CREATED ON ORDERS (CREATED_AT)",
        default_schema="Analytics",
    )

    assert proposed["schema"] == "analytics"
    assert proposed["table"] == "orders"
    assert proposed["columns"] == ["created_at"]
    assert proposed["index_name"] == "idx_orders_created"


def test_accepts_explicit_btree_and_an_unnamed_index():
    proposed = parse_proposed_index("CREATE INDEX ON public.orders USING btree (created_at)")

    assert proposed["index_name"] is None
    assert proposed["method"] == "btree"
    assert proposed["columns"] == ["created_at"]


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("", "create_index_required"),
        ("SELECT 1", "create_index_required"),
        ("DROP INDEX idx_orders", "create_index_required"),
        (
            "CREATE INDEX first_idx ON orders (tenant_id); "
            "CREATE INDEX second_idx ON orders (created_at)",
            "multiple_statements_not_supported",
        ),
        ("CREATE UNIQUE INDEX idx_orders ON orders (tenant_id)", "unique_index_not_supported"),
        (
            "CREATE INDEX idx_orders ON orders (tenant_id) INCLUDE (status)",
            "include_columns_not_supported",
        ),
        (
            "CREATE INDEX idx_orders ON orders (tenant_id) WHERE active",
            "partial_index_not_supported",
        ),
        (
            "CREATE INDEX idx_orders ON orders (LOWER(email))",
            "plain_column_keys_required",
        ),
        (
            "CREATE INDEX idx_orders ON orders (email text_pattern_ops)",
            "plain_column_keys_required",
        ),
        ("CREATE INDEX idx_orders ON orders USING gin (payload)", "btree_index_required"),
        (
            "CREATE INDEX idx_orders ON orders (created_at DESC)",
            "descending_index_keys_not_supported",
        ),
        (
            "CREATE INDEX idx_orders ON orders (created_at ASC NULLS FIRST)",
            "nulls_first_not_supported",
        ),
        (
            "CREATE INDEX idx_orders ON orders (tenant_id) WITH (fillfactor=80)",
            "index_storage_options_not_supported",
        ),
        (
            "CREATE INDEX idx_orders ON orders (tenant_id, tenant_id)",
            "duplicate_index_columns_not_supported",
        ),
        (
            'CREATE INDEX idx_orders ON public."Orders" (tenant_id)',
            "quoted_mixed_case_identifier_not_supported",
        ),
    ],
)
def test_rejects_index_shapes_the_review_cannot_reproduce(sql, reason):
    with pytest.raises(ProposedIndexError, match=f"^{reason}$"):
        parse_proposed_index(sql)


def test_rejects_an_unsupported_default_schema_before_database_access():
    with pytest.raises(ProposedIndexError, match="^unsupported_schema_identifier$"):
        parse_proposed_index("CREATE INDEX ON orders (tenant_id)", default_schema="sales-data")


def test_proposed_index_context_supports_an_equality_only_query():
    context = extract_proposed_index_query_context(
        "SELECT id FROM public.orders WHERE tenant_id = $1",
        TABLE_COLUMNS,
        target_schema="public",
        target_table="orders",
        candidate_columns=["tenant_id", "created_at"],
    )

    assert context is not None
    assert context["candidate_columns_used"] == ["tenant_id"]
    assert context["leading_column_usage"] == ["equality"]
    assert context["equality_columns"] == ["tenant_id"]
    assert context["range_columns"] == []
    assert context["order_columns"] == []
    assert context["tenant_evidence"]["source"] == "query_equality_predicate"
    assert len(context["query_fingerprint"]) == 12
    assert "query" not in context

    # Supplying an index is a separate review path; it must not relax the
    # automatic candidate generator's equality-plus-range/order heuristic.
    assert (
        extract_postgres_query_pattern(
            "SELECT id FROM public.orders WHERE tenant_id = $1", TABLE_COLUMNS
        )
        is None
    )


def test_proposed_index_context_reports_predicate_and_order_usage_with_an_alias():
    context = extract_proposed_index_query_context(
        """
        SELECT o.id
        FROM public.orders AS o
        JOIN public.tenants AS t ON t.id = o.tenant_id
        WHERE o.created_at >= $1
        ORDER BY o.created_at
        """,
        TABLE_COLUMNS,
        target_schema="public",
        target_table="orders",
        candidate_columns=["created_at", "tenant_id"],
    )

    assert context is not None
    assert context["leading_column_usage"] == ["range", "order"]
    assert context["candidate_columns_used"] == ["created_at", "tenant_id"]
    assert context["range_columns"] == ["created_at"]
    assert context["order_columns"] == ["created_at"]


@pytest.mark.parametrize(
    "query,candidate_columns",
    [
        ("SELECT status FROM public.orders", ["tenant_id"]),
        ("SELECT id FROM public.orders WHERE status = $1", ["tenant_id", "status"]),
        ("DELETE FROM public.orders WHERE tenant_id = $1", ["tenant_id"]),
        ("SELECT id FROM public.orders WHERE tenant_id = $1", ["missing_column"]),
    ],
)
def test_proposed_index_context_requires_a_known_leading_key_in_predicate_or_order(
    query, candidate_columns
):
    assert (
        extract_proposed_index_query_context(
            query,
            TABLE_COLUMNS,
            target_schema="public",
            target_table="orders",
            candidate_columns=candidate_columns,
        )
        is None
    )
