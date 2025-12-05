"""Schema validator - validates schema definitions"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate_schema(schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate schema definition.

    Args:
        schema: Schema definition dict

    Returns:
        tuple: (is_valid, list_of_errors)
    """
    errors = []

    # Check top-level structure
    if not isinstance(schema, dict):
        errors.append("Schema must be a dictionary")  # type: ignore[unreachable]
        return (False, errors)

    # Check tables
    if 'tables' not in schema:
        errors.append("Schema must have 'tables' key")
        return False, errors

    tables = schema.get('tables', [])
    if not isinstance(tables, list):
        errors.append("'tables' must be a list")
        return False, errors

    if len(tables) == 0:
        errors.append("Schema must have at least one table")
        return False, errors

    # Validate each table
    table_names = set()
    for i, table in enumerate(tables):
        table_errors = _validate_table(table, i)
        errors.extend(table_errors)

        # Check for duplicate table names
        if 'name' in table:
            table_name = table['name']
            if table_name in table_names:
                errors.append(f"Duplicate table name: {table_name}")
            table_names.add(table_name)

    return len(errors) == 0, errors


def _validate_table(table: dict[str, Any], index: int) -> list[str]:
    """Validate a single table definition."""
    errors: list[str] = []
    prefix = f"Table[{index}]"

    if not isinstance(table, dict):
        errors.append(f"{prefix}: Must be a dictionary")  # type: ignore[unreachable]
        return errors

    # Check required fields
    if 'name' not in table:
        errors.append(f"{prefix}: Missing required field 'name'")
    elif not isinstance(table['name'], str) or not table['name']:
        errors.append(f"{prefix}: 'name' must be a non-empty string")

    # Check fields
    if 'fields' not in table:
        errors.append(f"{prefix}: Missing required field 'fields'")
    elif not isinstance(table['fields'], list):
        errors.append(f"{prefix}: 'fields' must be a list")
    elif len(table['fields']) == 0:
        errors.append(f"{prefix}: Must have at least one field")
    else:
        # Validate each field
        field_names = set()
        for j, field in enumerate(table['fields']):
            field_errors = _validate_field(field, f"{prefix}.Field[{j}]")
            errors.extend(field_errors)

            # Check for duplicate field names
            if 'name' in field:
                field_name = field['name']
                if field_name in field_names:
                    errors.append(f"{prefix}: Duplicate field name: {field_name}")
                field_names.add(field_name)

    # Validate indexes (optional)
    if 'indexes' in table:
        indexes = table['indexes']
        if not isinstance(indexes, list):
            errors.append(f"{prefix}: 'indexes' must be a list")
        else:
            for j, index_def in enumerate(indexes):
                index_errors = _validate_index(index_def, f"{prefix}.Index[{j}]")
                errors.extend(index_errors)

    return errors


def _validate_field(field: dict[str, Any], prefix: str) -> list[str]:
    """Validate a single field definition."""
    errors: list[str] = []

    if not isinstance(field, dict):
        errors.append(f"{prefix}: Must be a dictionary")  # type: ignore[unreachable]
        return errors

    # Check required fields
    if 'name' not in field:
        errors.append(f"{prefix}: Missing required field 'name'")
    elif not isinstance(field['name'], str) or not field['name']:
        errors.append(f"{prefix}: 'name' must be a non-empty string")

    if 'type' not in field:
        errors.append(f"{prefix}: Missing required field 'type'")
    elif not isinstance(field['type'], str) or not field['type']:
        errors.append(f"{prefix}: 'type' must be a non-empty string")

    # Validate optional fields
    optional_fields = {
        'required': bool,
        'indexable': bool,
        'default_expression': bool,
        'feature_group': str,
    }

    for key, expected_type in optional_fields.items():
        if key in field:
            value = field[key]
            if not isinstance(value, expected_type):
                errors.append(
                    f"{prefix}: '{key}' must be of type {expected_type.__name__}"
                )

    return errors


def _validate_index(index_def: dict[str, Any], prefix: str) -> list[str]:
    """Validate an index definition."""
    errors: list[str] = []

    if not isinstance(index_def, dict):
        errors.append(f"{prefix}: Must be a dictionary")  # type: ignore[unreachable]
        return errors

    # Check required fields
    if 'fields' not in index_def:
        errors.append(f"{prefix}: Missing required field 'fields'")
    elif not isinstance(index_def['fields'], list) or len(index_def['fields']) == 0:
        errors.append(f"{prefix}: 'fields' must be a non-empty list")

    # Validate index type (optional)
    if 'type' in index_def:
        valid_types = ['btree', 'hash', 'gin', 'gist', 'brin']
        if index_def['type'] not in valid_types:
            errors.append(
                f"{prefix}: 'type' must be one of {valid_types}"
            )

    return errors

