"""Schema loader - loads schema definitions from YAML, JSON, or Python config"""

import json
import logging
from pathlib import Path
from typing import cast

from src.type_definitions import JSONDict, JSONValue

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


def load_schema(config_path: str) -> JSONDict:
    """
    Load schema from configuration file (auto-detects format).

    Supports:
    - YAML files (.yaml, .yml)
    - JSON files (.json)
    - Python files (.py) - must define SCHEMA_DEFINITION variable

    Args:
        config_path: Path to schema configuration file

    Returns:
        dict: Schema definition

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If file format is unsupported or invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Schema config file not found: {config_path}")

    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return load_schema_from_yaml(config_path)
    elif suffix == ".json":
        return load_schema_from_json(config_path)
    elif suffix == ".py":
        return load_schema_from_python(config_path)
    else:
        raise ValueError(
            f"Unsupported file format: {suffix}. Supported formats: .yaml, .yml, .json, .py"
        )


def load_schema_from_yaml(yaml_path: str) -> JSONDict:
    """
    Load schema from YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        dict: Schema definition

    Raises:
        ImportError: If PyYAML is not installed
        ValueError: If YAML is invalid
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for YAML schema files. Install with: pip install pyyaml"
        )

    try:
        with open(yaml_path, encoding="utf-8") as f:
            loaded_data: object = yaml.safe_load(f)

        if not loaded_data:
            raise ValueError("YAML file is empty")

        if not isinstance(loaded_data, dict):
            raise ValueError(f"YAML file {yaml_path} must contain a dictionary")

        # Type narrowing: isinstance check ensures it's a dict
        schema: JSONDict = cast(JSONDict, loaded_data)

        # Normalize structure
        if "schema" in schema:
            schema_val = schema.get("schema")
            if isinstance(schema_val, dict):
                return schema_val
        return schema

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {yaml_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error loading YAML from {yaml_path}: {e}") from e


def load_schema_from_json(json_path: str) -> JSONDict:
    """
    Load schema from JSON file.

    Args:
        json_path: Path to JSON file

    Returns:
        dict: Schema definition

    Raises:
        ValueError: If JSON is invalid
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            loaded_data: object = json.load(f)

        if not loaded_data:
            raise ValueError("JSON file is empty")

        if not isinstance(loaded_data, dict):
            raise ValueError(f"JSON file {json_path} must contain a dictionary")

        schema: JSONDict = cast(JSONDict, loaded_data)

        # Normalize structure
        if "schema" in schema:
            schema_val: JSONValue = schema.get("schema")
            if isinstance(schema_val, dict):
                return cast(JSONDict, schema_val)
        return schema

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {json_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error loading JSON from {json_path}: {e}") from e


def load_schema_from_python(python_path: str) -> JSONDict:
    """
    Load schema from Python file.

    The Python file must define a variable named SCHEMA_DEFINITION.

    Example:
        # schema_config.py
        SCHEMA_DEFINITION = {
            "tables": [...]
        }

    Args:
        python_path: Path to Python file

    Returns:
        dict: Schema definition

    Raises:
        ValueError: If SCHEMA_DEFINITION is not found or invalid
    """
    try:
        # Load Python file as module
        import importlib.util

        spec = importlib.util.spec_from_file_location("schema_config", python_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load Python file: {python_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "SCHEMA_DEFINITION"):
            raise ValueError(f"Python file {python_path} must define SCHEMA_DEFINITION variable")

        schema_obj: object = module.SCHEMA_DEFINITION

        if not isinstance(schema_obj, dict):
            raise ValueError("SCHEMA_DEFINITION must be a dictionary")

        schema: JSONDict = cast(JSONDict, schema_obj)

        # Normalize structure
        if "schema" in schema:
            schema_val: JSONValue = schema.get("schema")
            if isinstance(schema_val, dict):
                return cast(JSONDict, schema_val)
        return schema

    except Exception as e:
        raise ValueError(f"Error loading Python config from {python_path}: {e}") from e


def convert_schema_to_genome_fields(
    schema: JSONDict,
) -> list[tuple[str, str, str, bool, bool, bool, str]]:
    """
    Convert schema definition to genome catalog format.

    Args:
        schema: Schema definition dict

    Returns:
        list: List of tuples in format (table_name, field_name, field_type,
              is_required, is_indexable, default_expression, feature_group)
    """
    genome_fields: list[tuple[str, str, str, bool, bool, bool, str]] = []
    tables_val = schema.get("tables", [])
    if not isinstance(tables_val, list):
        return genome_fields

    for table_val in tables_val:
        if not isinstance(table_val, dict):
            continue
        table: JSONDict = table_val
        table_name_val = table.get("name")
        if not isinstance(table_name_val, str):
            logger.warning("Table missing 'name' field, skipping")
            continue
        table_name = table_name_val

        fields_val = table.get("fields", [])
        if not isinstance(fields_val, list):
            continue
        for field_val in fields_val:
            if not isinstance(field_val, dict):
                continue
            field: JSONDict = field_val
            field_name_val = field.get("name")
            if not isinstance(field_name_val, str):
                logger.warning(f"Field in table {table_name} missing 'name', skipping")
                continue
            field_name = field_name_val

            type_val = field.get("type", "TEXT")
            field_type = type_val if isinstance(type_val, str) else "TEXT"
            required_val = field.get("required", False)
            is_required = required_val if isinstance(required_val, bool) else False
            indexable_val = field.get("indexable", True)
            is_indexable = indexable_val if isinstance(indexable_val, bool) else True
            default_expr_val = field.get("default_expression", True)
            default_expression = default_expr_val if isinstance(default_expr_val, bool) else True
            feature_group_val = field.get("feature_group", "core")
            feature_group = feature_group_val if isinstance(feature_group_val, str) else "core"

            genome_fields.append(
                (
                    table_name,
                    field_name,
                    field_type,
                    is_required,
                    is_indexable,
                    default_expression,
                    feature_group,
                )
            )

    return genome_fields


def get_table_definitions(schema: JSONDict) -> dict[str, JSONDict]:
    """
    Extract table definitions from schema.

    Args:
        schema: Schema definition dict

    Returns:
        dict: Dictionary mapping table names to table definitions
    """
    tables_val = schema.get("tables", [])
    if not isinstance(tables_val, list):
        return {}
    result: dict[str, JSONDict] = {}
    for table_val in tables_val:
        if not isinstance(table_val, dict):
            continue
        table: JSONDict = table_val
        name_val = table.get("name")
        if isinstance(name_val, str):
            result[name_val] = table
    return result
