"""Schema loader - loads schema definitions from YAML, JSON, or Python config"""

import json
import logging
from pathlib import Path
from typing import Any, cast

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


def load_schema(config_path: str) -> dict[str, Any]:
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

    if suffix in ('.yaml', '.yml'):
        return load_schema_from_yaml(config_path)
    elif suffix == '.json':
        return load_schema_from_json(config_path)
    elif suffix == '.py':
        return load_schema_from_python(config_path)
    else:
        raise ValueError(
            f"Unsupported file format: {suffix}. "
            "Supported formats: .yaml, .yml, .json, .py"
        )


def load_schema_from_yaml(yaml_path: str) -> dict[str, Any]:
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
            "PyYAML is required for YAML schema files. "
            "Install with: pip install pyyaml"
        )

    try:
        with open(yaml_path, encoding='utf-8') as f:
            schema = yaml.safe_load(f)

        if not schema:
            raise ValueError("YAML file is empty")

        # Normalize structure
        if 'schema' in schema:
            return cast(dict[str, Any], schema['schema'])
        return cast(dict[str, Any], schema)

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {yaml_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error loading YAML from {yaml_path}: {e}") from e


def load_schema_from_json(json_path: str) -> dict[str, Any]:
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
        with open(json_path, encoding='utf-8') as f:
            schema = json.load(f)

        if not schema:
            raise ValueError("JSON file is empty")

        # Normalize structure
        if 'schema' in schema:
            return cast(dict[str, Any], schema['schema'])
        return cast(dict[str, Any], schema)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {json_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error loading JSON from {json_path}: {e}") from e


def load_schema_from_python(python_path: str) -> dict[str, Any]:
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

        if not hasattr(module, 'SCHEMA_DEFINITION'):
            raise ValueError(
                f"Python file {python_path} must define SCHEMA_DEFINITION variable"
            )

        schema = module.SCHEMA_DEFINITION

        if not isinstance(schema, dict):
            raise ValueError("SCHEMA_DEFINITION must be a dictionary")

        # Normalize structure
        if 'schema' in schema:
            return cast(dict[str, Any], schema['schema'])
        return cast(dict[str, Any], schema)

    except Exception as e:
        raise ValueError(f"Error loading Python config from {python_path}: {e}") from e


def convert_schema_to_genome_fields(schema: dict[str, Any]) -> list[tuple]:
    """
    Convert schema definition to genome catalog format.

    Args:
        schema: Schema definition dict

    Returns:
        list: List of tuples in format (table_name, field_name, field_type,
              is_required, is_indexable, default_expression, feature_group)
    """
    genome_fields = []
    tables = schema.get('tables', [])

    for table in tables:
        table_name = table.get('name')
        if not table_name:
            logger.warning("Table missing 'name' field, skipping")
            continue

        fields = table.get('fields', [])
        for field in fields:
            field_name = field.get('name')
            if not field_name:
                logger.warning(f"Field in table {table_name} missing 'name', skipping")
                continue

            genome_fields.append((
                table_name,
                field_name,
                field.get('type', 'TEXT'),
                field.get('required', False),
                field.get('indexable', True),
                field.get('default_expression', True),
                field.get('feature_group', 'core'),
            ))

    return genome_fields


def get_table_definitions(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Extract table definitions from schema.

    Args:
        schema: Schema definition dict

    Returns:
        dict: Dictionary mapping table names to table definitions
    """
    tables = schema.get('tables', [])
    return {table['name']: table for table in tables if 'name' in table}

