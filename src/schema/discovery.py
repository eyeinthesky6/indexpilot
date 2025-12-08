"""Schema file auto-discovery from codebase"""

import logging
from pathlib import Path
from typing import Any

from src.schema.loader import load_schema
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)


def discover_schema_files(search_path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Auto-discover schema configuration files in the codebase.

    Searches for files matching patterns:
    - schema_config*.yaml
    - schema_config*.yml
    - schema_config*.json
    - schema_config*.py

    Args:
        search_path: Directory to search (default: project root)

    Returns:
        List of dicts with 'path', 'name', 'type' for each discovered schema file
    """
    if search_path is None:
        # Default to project root (parent of src/)
        try:
            search_path = Path(__file__).parent.parent.parent
        except Exception:
            search_path = Path.cwd()
    else:
        search_path = Path(search_path)

    if not search_path.exists():
        logger.warning(f"Search path does not exist: {search_path}")
        return []

    schema_files = []
    patterns = [
        "schema_config*.yaml",
        "schema_config*.yml",
        "schema_config*.json",
        "schema_config*.py",
    ]

    for pattern in patterns:
        for file_path in search_path.rglob(pattern):
            # Skip hidden files and common ignore patterns
            if any(part.startswith(".") for part in file_path.parts):
                continue
            if "node_modules" in file_path.parts or "__pycache__" in file_path.parts:
                continue

            file_type = (
                "yaml" if file_path.suffix in (".yaml", ".yml") else file_path.suffix[1:]
            )  # Remove dot

            schema_files.append(
                {
                    "path": str(file_path),
                    "name": file_path.stem,
                    "type": file_type,
                    "relative_path": str(file_path.relative_to(search_path)),
                }
            )

    # Sort by name for consistent ordering
    schema_files.sort(key=lambda x: x["name"])

    return schema_files


def load_discovered_schema(schema_file_info: dict[str, Any]) -> JSONDict | None:
    """
    Load a discovered schema file.

    Args:
        schema_file_info: Dict from discover_schema_files() with 'path' key

    Returns:
        Schema definition dict, or None if loading failed
    """
    try:
        schema_path = schema_file_info.get("path")
        if not schema_path:
            logger.error("Schema file info missing 'path'")
            return None

        schema = load_schema(schema_path)
        logger.info(f"Successfully loaded schema from {schema_path}")
        return schema
    except Exception as e:
        logger.warning(f"Failed to load schema from {schema_file_info.get('path', 'unknown')}: {e}")
        return None


def auto_discover_and_load_schema(preferred_name: str | None = None) -> JSONDict | None:
    """
    Auto-discover and load schema file from codebase.

    If preferred_name is provided, tries to find a schema file matching that name.
    Otherwise, returns the first discovered schema file.

    Args:
        preferred_name: Preferred schema file name (e.g., "schema_config_stock_market")

    Returns:
        Schema definition dict, or None if no schema found
    """
    schema_files = discover_schema_files()

    if not schema_files:
        logger.warning("No schema configuration files found in codebase")
        return None

    # If preferred name specified, try to find matching file
    if preferred_name:
        for schema_file in schema_files:
            if preferred_name.lower() in schema_file["name"].lower():
                logger.info(f"Found preferred schema file: {schema_file['path']}")
                return load_discovered_schema(schema_file)

    # Otherwise, use first discovered file
    logger.info(f"Using first discovered schema file: {schema_files[0]['path']}")
    return load_discovered_schema(schema_files[0])
