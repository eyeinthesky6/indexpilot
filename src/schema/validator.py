"""Schema validator - validates schema definitions"""

import logging

from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)


def validate_schema(schema: object) -> tuple[bool, list[str]]:
    """
    Validate schema definition.

    Args:
        schema: Schema definition dict (accepts object for runtime validation)

    Returns:
        tuple: (is_valid, list_of_errors)
    """
    errors = []

    # Check top-level structure (runtime safety check)
    if not isinstance(schema, dict):
        errors.append("Schema must be a dictionary")
        return (False, errors)

    # Type narrowing: schema is now known to be a dict
    schema_dict: JSONDict = schema

    # Check tables
    if "tables" not in schema_dict:
        errors.append("Schema must have 'tables' key")
        return False, errors

    tables = schema_dict.get("tables", [])
    if not isinstance(tables, list):
        errors.append("'tables' must be a list")
        return False, errors

    if len(tables) == 0:
        errors.append("Schema must have at least one table")
        return False, errors

    # Validate each table
    table_names: set[str] = set()
    for i, table_val in enumerate(tables):
        if not isinstance(table_val, dict):
            errors.append(f"Table[{i}]: Must be a dictionary")
            continue
        table: JSONDict = table_val
        table_errors = _validate_table(table, i)
        errors.extend(table_errors)

        # Check for duplicate table names
        if "name" in table:
            name_val = table.get("name")
            if isinstance(name_val, str):
                table_name = name_val
                if table_name in table_names:
                    errors.append(f"Duplicate table name: {table_name}")
                table_names.add(table_name)

    return len(errors) == 0, errors


def _validate_table(table: object, index: int) -> list[str]:
    """Validate a single table definition."""
    errors: list[str] = []
    prefix = f"Table[{index}]"

    # Type guard (runtime safety check)
    if not isinstance(table, dict):
        errors.append(f"{prefix}: Must be a dictionary")
        return errors

    # Type narrowing: table is now known to be a dict
    table_dict: JSONDict = table

    # Check required fields
    if "name" not in table_dict:
        errors.append(f"{prefix}: Missing required field 'name'")
    elif not isinstance(table_dict["name"], str) or not table_dict["name"]:
        errors.append(f"{prefix}: 'name' must be a non-empty string")

    # Check fields
    if "fields" not in table_dict:
        errors.append(f"{prefix}: Missing required field 'fields'")
    elif not isinstance(table_dict["fields"], list):
        errors.append(f"{prefix}: 'fields' must be a list")
    elif len(table_dict["fields"]) == 0:
        errors.append(f"{prefix}: Must have at least one field")
    else:
        # Validate each field
        field_names: set[str] = set()
        fields_val = table_dict.get("fields")
        if isinstance(fields_val, list):
            for j, field_val in enumerate(fields_val):
                if not isinstance(field_val, dict):
                    errors.append(f"{prefix}.Field[{j}]: Must be a dictionary")
                    continue
                field: JSONDict = field_val
                field_errors = _validate_field(field, f"{prefix}.Field[{j}]")
                errors.extend(field_errors)

                # Check for duplicate field names
                if "name" in field:
                    name_val = field.get("name")
                    if isinstance(name_val, str):
                        field_name = name_val
                        if field_name in field_names:
                            errors.append(f"{prefix}: Duplicate field name: {field_name}")
                        field_names.add(field_name)

    # Validate indexes (optional)
    if "indexes" in table_dict:
        indexes_val = table_dict.get("indexes")
        if not isinstance(indexes_val, list):
            errors.append(f"{prefix}: 'indexes' must be a list")
        else:
            for j, index_val in enumerate(indexes_val):
                if not isinstance(index_val, dict):
                    errors.append(f"{prefix}.Index[{j}]: Must be a dictionary")
                    continue
                index_def: JSONDict = index_val
                index_errors = _validate_index(index_def, f"{prefix}.Index[{j}]")
                errors.extend(index_errors)

    return errors


def _validate_field(field: object, prefix: str) -> list[str]:
    """Validate a single field definition."""
    errors: list[str] = []

    # Type guard (runtime safety check)
    if not isinstance(field, dict):
        errors.append(f"{prefix}: Must be a dictionary")
        return errors

    # Type narrowing: field is now known to be a dict
    field_dict: JSONDict = field

    # Check required fields
    if "name" not in field_dict:
        errors.append(f"{prefix}: Missing required field 'name'")
    elif not isinstance(field_dict["name"], str) or not field_dict["name"]:
        errors.append(f"{prefix}: 'name' must be a non-empty string")

    if "type" not in field_dict:
        errors.append(f"{prefix}: Missing required field 'type'")
    elif not isinstance(field_dict["type"], str) or not field_dict["type"]:
        errors.append(f"{prefix}: 'type' must be a non-empty string")

    # Validate optional fields
    optional_fields = {
        "required": bool,
        "indexable": bool,
        "default_expression": bool,
        "feature_group": str,
    }

    for key, expected_type in optional_fields.items():
        if key in field_dict:
            value = field_dict[key]
            if not isinstance(value, expected_type):
                errors.append(f"{prefix}: '{key}' must be of type {expected_type.__name__}")

    return errors


def _validate_index(index_def: object, prefix: str) -> list[str]:
    """Validate an index definition."""
    errors: list[str] = []

    # Type guard (runtime safety check)
    if not isinstance(index_def, dict):
        errors.append(f"{prefix}: Must be a dictionary")
        return errors

    # Type narrowing: index_def is now known to be a dict
    index_dict: JSONDict = index_def

    # Check required fields
    if "fields" not in index_dict:
        errors.append(f"{prefix}: Missing required field 'fields'")
    elif not isinstance(index_dict["fields"], list) or len(index_dict["fields"]) == 0:
        errors.append(f"{prefix}: 'fields' must be a non-empty list")

    # Validate index type (optional)
    if "type" in index_dict:
        valid_types = ["btree", "hash", "gin", "gist", "brin"]
        if index_dict["type"] not in valid_types:
            errors.append(f"{prefix}: 'type' must be one of {valid_types}")

    return errors
