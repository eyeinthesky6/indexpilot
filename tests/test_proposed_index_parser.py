import pytest

from src.sql_parser import (
    ProposedIndexError,
    extract_postgres_query_pattern,
    extract_proposed_index_query_context,
    parse_migration_indexes,
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


def test_extracts_supported_indexes_from_a_mixed_migration():
    migration = parse_migration_indexes(
        """
        ALTER TABLE orders ADD COLUMN archived_at timestamptz;
        CREATE INDEX CONCURRENTLY idx_orders_tenant
          ON public.orders (tenant_id);
        CREATE INDEX idx_orders_created ON public.orders (created_at);
        """
    )

    assert migration["statement_count"] == 3
    assert migration["ignored_statement_count"] == 1
    assert [item["statement_number"] for item in migration["proposals"]] == [2, 3]
    assert [item["columns"] for item in migration["proposals"]] == [
        ["tenant_id"],
        ["created_at"],
    ]


def test_migration_reports_the_position_of_an_unsupported_index():
    with pytest.raises(
        ProposedIndexError,
        match="^migration_statement_2_partial_index_not_supported$",
    ):
        parse_migration_indexes(
            """
            ALTER TABLE orders ADD COLUMN active boolean;
            CREATE INDEX idx_orders_active ON orders (tenant_id) WHERE active;
            """
        )


def test_migration_requires_at_least_one_supported_create_index():
    with pytest.raises(ProposedIndexError, match="^no_supported_create_index_statements$"):
        parse_migration_indexes("ALTER TABLE orders ADD COLUMN active boolean;")


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


def test_expression_predicates_do_not_masquerade_as_plain_index_keys():
    context = extract_proposed_index_query_context(
        "SELECT id FROM public.orders WHERE lower(status) = $1",
        TABLE_COLUMNS,
        target_schema="public",
        target_table="orders",
        candidate_columns=["status"],
    )
    pattern = extract_postgres_query_pattern(
        """
        SELECT id FROM public.orders
        WHERE lower(status) = $1 AND created_at >= $2
        ORDER BY lower(status)
        """,
        TABLE_COLUMNS,
    )

    assert context is None
    assert pattern is None


def test_bare_column_on_either_side_of_a_predicate_is_still_supported():
    context = extract_proposed_index_query_context(
        "SELECT id FROM public.orders WHERE $1 = tenant_id",
        TABLE_COLUMNS,
        target_schema="public",
        target_table="orders",
        candidate_columns=["tenant_id"],
    )

    assert context is not None
    assert context["equality_columns"] == ["tenant_id"]


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


SHAPE_COMPATIBILITY_MATRIX = [
    (
        "CREATE INDEX idx_orders_tenant ON orders (tenant_id)",
        None,
    ),
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
        "CREATE INDEX idx_orders ON orders USING gin (payload)",
        "btree_index_required",
    ),
    (
        "CREATE INDEX idx_orders ON orders USING gist (geom)",
        "btree_index_required",
    ),
    (
        "CREATE INDEX idx_orders ON orders USING brin (created_at)",
        "btree_index_required",
    ),
]

@pytest.mark.parametrize("sql,expected_error", SHAPE_COMPATIBILITY_MATRIX)
def test_create_index_shape_compatibility_matrix(sql, expected_error):
    if expected_error is None:
        proposed = parse_proposed_index(sql)
        assert proposed["columns"] == ["tenant_id"]
    else:
        with pytest.raises(ProposedIndexError, match=f"^{expected_error}$"):
            parse_proposed_index(sql)

@pytest.mark.parametrize("position", [1, 3])
@pytest.mark.parametrize("sql,expected_error", SHAPE_COMPATIBILITY_MATRIX)
def test_migration_shape_compatibility_reports_positional_errors(sql, expected_error, position):
    if position == 1:
        migration_sql = f"""
            {sql};
            CREATE INDEX idx_valid ON orders (created_at);
            ALTER TABLE orders ADD COLUMN dummy text;
        """
        error_pos = 1
    else:
        migration_sql = f"""
            ALTER TABLE orders ADD COLUMN dummy text;
            CREATE INDEX idx_valid ON orders (created_at);
            {sql};
        """
        error_pos = 3

    if expected_error is None:
        result = parse_migration_indexes(migration_sql)
        assert result["ignored_statement_count"] == 1
        assert len(result["proposals"]) == 2

        import json
        serialized = json.dumps(result)
        assert "ALTER TABLE" not in serialized
        assert sql not in serialized
        assert "CREATE INDEX idx_valid ON orders (created_at)" not in serialized
        return

    with pytest.raises(ProposedIndexError, match=f"^migration_statement_{error_pos}_{expected_error}$"):
        parse_migration_indexes(migration_sql)
