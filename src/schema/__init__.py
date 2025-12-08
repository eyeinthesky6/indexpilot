"""Schema abstraction layer for IndexPilot"""

from src.schema.auto_discovery import (
    discover_and_bootstrap_schema,
    discover_schema_from_database,
)
from src.schema.change_detection import detect_and_sync_schema_changes
from src.schema.discovery import (
    auto_discover_and_load_schema,
    discover_schema_files,
    load_discovered_schema,
)
from src.schema.initialization import init_schema, init_schema_from_config
from src.schema.loader import (
    convert_schema_to_genome_fields,
    load_schema,
    load_schema_from_json,
    load_schema_from_python,
    load_schema_from_yaml,
)
from src.schema.validator import validate_schema

__all__ = [
    "load_schema",
    "load_schema_from_yaml",
    "load_schema_from_json",
    "load_schema_from_python",
    "convert_schema_to_genome_fields",
    "validate_schema",
    "init_schema",
    "init_schema_from_config",
    "discover_schema_from_database",
    "discover_and_bootstrap_schema",
    "discover_schema_files",
    "load_discovered_schema",
    "auto_discover_and_load_schema",
    "detect_and_sync_schema_changes",
]
