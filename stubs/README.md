# Type Stubs Directory

This directory contains type stub files (`.pyi`) for third-party libraries that don't have complete type information, improving mypy type checking accuracy.

## Purpose

Type stubs provide type information for libraries without modifying their source code. This allows:
- Better type checking with mypy
- Reduced `Any` type warnings
- Improved IDE autocomplete and type hints
- Better code maintainability

## Current Stubs

### `fastapi.pyi`
Type stubs for FastAPI framework, providing proper type signatures for:
- `FastAPI` class and its decorator methods (`get`, `post`, `put`, `delete`)
- `HTTPException` class
- `CORSMiddleware` class

## Adding New Stubs

### Option 1: Install Official Stub Packages
Many libraries have official type stub packages on PyPI:
```bash
pip install types-psycopg2  # For psycopg2
pip install types-requests  # For requests
# Check PyPI for other types-* packages
```

### Option 2: Create Custom Stubs
If no official stubs exist, create a `.pyi` file in this directory:

1. **Create the stub file**: `stubs/library_name.pyi`
2. **Define type signatures**: Use ellipsis (`...`) for function bodies
3. **Example**:
   ```python
   # stubs/library_name.pyi
   from typing import Any, Callable, TypeVar
   
   _T = TypeVar("_T")
   
   class SomeClass:
       def method(self, arg: str) -> int: ...
   ```

## Configuration

The stubs directory is configured in `mypy.ini`:
```ini
[mypy]
mypy_path = stubs
```

Mypy will automatically discover and use stub files in this directory.

## Best Practices

1. **Keep stubs minimal**: Only include the types you actually use
2. **Match library versions**: Update stubs when upgrading libraries
3. **Document limitations**: Add comments for incomplete type coverage
4. **Test regularly**: Run `make typecheck` after adding/updating stubs
5. **Prefer official stubs**: Use `types-*` packages when available

## Maintenance

- Review stubs when upgrading third-party libraries
- Update stubs if new library features are used
- Remove stubs if official packages become available
- Document any known limitations in stub files

## References

- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 561 - Distributing and Packaging Type Information](https://www.python.org/dev/peps/pep-0561/)
- [Mypy Type Stubs Documentation](https://mypy.readthedocs.io/en/stable/stubs.html)
- [Typeshed Repository](https://github.com/python/typeshed) - Official Python type stubs

