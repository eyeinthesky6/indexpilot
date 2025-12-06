"""Schema abstraction layer for IndexPilot"""

import importlib.util
import sys
from pathlib import Path

from src.schema.loader import (
    load_schema,
    load_schema_from_json,
    load_schema_from_python,
    load_schema_from_yaml,
)
from src.schema.validator import validate_schema

# Import init_schema from the schema.py module file (not the package) for backward compatibility
# This avoids circular import issues between src/schema.py (module) and src/schema/ (package)
_schema_package_dir = Path(__file__).parent.parent
_schema_module_path = _schema_package_dir / 'schema.py'
if _schema_module_path.exists():
    _spec = importlib.util.spec_from_file_location('src.schema_module', _schema_module_path)
    if _spec and _spec.loader:
        _schema_module = importlib.util.module_from_spec(_spec)
        sys.modules['src.schema_module'] = _schema_module
        _spec.loader.exec_module(_schema_module)
        init_schema = _schema_module.init_schema  # type: ignore[misc]
        init_schema_from_config = _schema_module.init_schema_from_config  # type: ignore[misc]
    else:
        # Fallback: try direct import
        import src.schema as schema_module
        init_schema = schema_module.init_schema  # type: ignore[misc]
        init_schema_from_config = schema_module.init_schema_from_config  # type: ignore[misc]
else:
    # Module file doesn't exist, create stub functions
    def init_schema():
        raise NotImplementedError("init_schema not available - schema.py module not found")

    def init_schema_from_config(*args, **kwargs):
        raise NotImplementedError("init_schema_from_config not available - schema.py module not found")

__all__ = [
    'load_schema',
    'load_schema_from_yaml',
    'load_schema_from_json',
    'load_schema_from_python',
    'validate_schema',
    'init_schema',
    'init_schema_from_config',
]

