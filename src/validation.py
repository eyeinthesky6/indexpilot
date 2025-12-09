"""Input validation for security and error prevention"""

import logging
import re

logger = logging.getLogger(__name__)

# IndexPilot metadata tables (always allowed)
METADATA_TABLES = {"genome_catalog", "expression_profile", "mutation_log", "query_stats"}

# Cache for allowed tables/fields from genome_catalog
_allowed_tables_cache: set[str] | None = None
_allowed_fields_cache: set[str] | None = None


def is_valid_identifier(name: str) -> bool:
    """
    Validate identifier name (table, column) to prevent SQL injection.

    Args:
        name: Identifier name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False

    # Must match identifier pattern: alphanumeric + underscore, start with letter/underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        return False

    # Must not be a SQL keyword (basic check)
    sql_keywords = {
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "table",
        "index",
        "where",
        "from",
        "and",
        "or",
        "not",
        "null",
        "true",
        "false",
        "order",
        "by",
        "group",
        "having",
        "limit",
        "offset",
    }
    return name.lower() not in sql_keywords


def _get_allowed_tables() -> set[str]:
    """
    Get allowed table names from genome_catalog (dynamic, not hardcoded).

    Returns:
        Set of allowed table names
    """
    global _allowed_tables_cache

    if _allowed_tables_cache is not None:
        return _allowed_tables_cache

    # Try to load from genome_catalog
    try:
        from src.db import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT table_name
                FROM genome_catalog
            """
            )
            tables = {row["table_name"] for row in cursor.fetchall()}
            # Add metadata tables
            tables.update(METADATA_TABLES)
            _allowed_tables_cache = tables
            return tables
    except Exception as e:
        logger.warning(
            f"Could not load tables from genome_catalog: {e}. Using metadata tables only."
        )
        # Fallback: only allow metadata tables
        _allowed_tables_cache = METADATA_TABLES.copy()
        return _allowed_tables_cache


def _get_allowed_fields() -> set[str]:
    """
    Get allowed field names from genome_catalog (dynamic, not hardcoded).

    Returns:
        Set of allowed field names
    """
    global _allowed_fields_cache

    if _allowed_fields_cache is not None:
        return _allowed_fields_cache

    # Try to load from genome_catalog
    try:
        from src.db import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT field_name
                FROM genome_catalog
            """
            )
            fields = {row["field_name"] for row in cursor.fetchall()}
            # Always allow common fields
            fields.update(["id", "created_at", "updated_at"])
            _allowed_fields_cache = fields
            return fields
    except Exception as e:
        logger.warning(
            f"Could not load fields from genome_catalog: {e}. Using basic validation only."
        )
        # Fallback: allow any valid identifier
        _allowed_fields_cache = set()
        return _allowed_fields_cache


def clear_validation_cache():
    """Clear cached validation data (useful after schema changes)"""
    global _allowed_tables_cache, _allowed_fields_cache
    _allowed_tables_cache = None
    _allowed_fields_cache = None


def validate_table_name(table_name: str, use_cache: bool = True) -> str:
    """
    Validate and return table name.

    Uses genome_catalog for dynamic validation (not hardcoded whitelist).

    Args:
        table_name: Table name to validate
        use_cache: Whether to use cached allowed tables (default: True)

    Returns:
        Validated table name

    Raises:
        ValueError: If table name is invalid
    """
    if not is_valid_identifier(table_name):
        raise ValueError(f"Invalid table name format: {table_name}")

    # Always allow metadata tables
    if table_name.lower() in METADATA_TABLES:
        return table_name

    # Check against genome_catalog (dynamic)
    if use_cache:
        allowed_tables = _get_allowed_tables()
    else:
        # Force reload
        clear_validation_cache()
        allowed_tables = _get_allowed_tables()

    if table_name.lower() not in allowed_tables:
        # If genome_catalog is empty or not initialized, be permissive
        # (allow any valid identifier to support initial setup)
        if len(allowed_tables) == len(METADATA_TABLES):
            logger.debug(f"Genome catalog empty, allowing table: {table_name}")
            return table_name
        raise ValueError(f"Table name not found in genome_catalog: {table_name}")

    return table_name


def validate_field_name(
    field_name: str, table_name: str | None = None, use_cache: bool = True
) -> str:
    """
    Validate and return field name.

    Uses genome_catalog for dynamic validation (not hardcoded whitelist).

    Args:
        field_name: Field name to validate
        table_name: Optional table name for context-specific validation
        use_cache: Whether to use cached allowed fields (default: True)

    Returns:
        Validated field name

    Raises:
        ValueError: If field name is invalid
    """
    if not is_valid_identifier(field_name):
        raise ValueError(f"Invalid field name format: {field_name}")

    # Always allow common fields
    if field_name.lower() in ("id", "created_at", "updated_at"):
        return field_name

    # Allow custom fields (common pattern)
    if field_name.startswith("custom_"):
        return field_name

    # Check against genome_catalog (dynamic)
    if table_name:
        # Table-specific validation
        try:
            from src.db import get_cursor

            with get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT field_name
                    FROM genome_catalog
                    WHERE table_name = %s AND field_name = %s
                """,
                    (table_name, field_name),
                )
                if cursor.fetchone():
                    return field_name
        except Exception as e:
            logger.warning(f"Could not validate field against genome_catalog: {e}")
            # Fall through to general validation

    # General validation (any field in genome_catalog)
    if use_cache:
        allowed_fields = _get_allowed_fields()
    else:
        clear_validation_cache()
        allowed_fields = _get_allowed_fields()

    if field_name.lower() not in allowed_fields:
        # If genome_catalog is empty, be permissive (allow any valid identifier)
        if len(allowed_fields) <= 3:  # Only common fields
            logger.debug(f"Genome catalog empty, allowing field: {field_name}")
            return field_name
        raise ValueError(f"Field name not found in genome_catalog: {field_name}")

    return field_name


def validate_tenant_id(tenant_id):
    """
    Validate tenant ID.

    Args:
        tenant_id: Tenant ID to validate

    Returns:
        Validated tenant ID as int, or None if None

    Raises:
        ValueError: If tenant ID is invalid
    """
    if tenant_id is None:
        return None

    try:
        tenant_id = int(tenant_id)
        if tenant_id < 1:
            raise ValueError(f"Tenant ID must be positive: {tenant_id}")
        return tenant_id
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid tenant ID: {tenant_id}") from e


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input.

    Args:
        value: String to sanitize
        max_length: Maximum length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value)}")

    # Remove null bytes and control characters
    value = value.replace("\x00", "")
    value = "".join(c for c in value if ord(c) >= 32 or c in "\n\r\t")

    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]

    return value


def validate_numeric_input(
    value, min_value=None, max_value=None, default_value=None, allow_float=True
):
    """
    Validate and sanitize numeric input to prevent injection and overflow.

    Args:
        value: Numeric value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        default_value: Default value if validation fails
        allow_float: Whether to allow floating point numbers

    Returns:
        Validated numeric value

    Raises:
        ValueError: If value is invalid and no default provided
    """
    # Convert to appropriate numeric type
    try:
        num_value = float(value) if allow_float else int(value)
    except (ValueError, TypeError) as e:
        if default_value is not None:
            return default_value
        raise ValueError(f"Invalid numeric value: {value}") from e

    # Check bounds
    if min_value is not None and num_value < min_value:
        if default_value is not None:
            return default_value
        raise ValueError(f"Value {num_value} below minimum {min_value}")

    if max_value is not None and num_value > max_value:
        if default_value is not None:
            return default_value
        raise ValueError(f"Value {num_value} above maximum {max_value}")

    return num_value if allow_float else int(num_value)
