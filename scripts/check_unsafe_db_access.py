#!/usr/bin/env python3
"""
Lint check for unsafe database result access patterns.

Detects direct tuple index access (e.g., row[0], row[1]) that should use
safe_get_row_value() instead.

Usage:
    python scripts/check_unsafe_db_access.py
    python scripts/check_unsafe_db_access.py --fix  # Auto-fix suggestions
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# Patterns to detect unsafe tuple access
UNSAFE_PATTERNS = [
    # Direct tuple index access: row[0], row[1], etc.
    (r'\brow\[(\d+)\]\b', 'Direct tuple index access'),
    (r'\bresult\[(\d+)\]\b', 'Direct tuple index access'),
    (r'\btable_row\[(\d+)\]\b', 'Direct tuple index access'),
    (r'\bquery_row\[(\d+)\]\b', 'Direct tuple index access'),
    # Direct access from fetchone/fetchall: fetchone()[0], fetchall()[0][0]
    (r'fetchone\(\)\[(\d+)\]', 'Unsafe tuple access from fetchone()'),
    (r'fetchall\(\)\[(\d+)\]', 'Unsafe tuple access from fetchall()'),
    (r'fetchone\(\)\[(\d+)\]\[(\d+)\]', 'Unsafe nested tuple access from fetchone()'),
    (r'fetchall\(\)\[(\d+)\]\[(\d+)\]', 'Unsafe nested tuple access from fetchall()'),
    # Access with len check but still unsafe (should use helper)
    (r'row\[(\d+)\]\s+if\s+len\(row\)\s*>\s*\d+\s+else', 'Unsafe tuple access with len check'),
    (r'result\[(\d+)\]\s+if\s+len\(result\)\s*>\s*\d+\s+else', 'Unsafe tuple access with len check'),
]

# Files to check
SOURCE_DIRS = ['src', 'tests']
# Files to ignore
IGNORE_PATTERNS = [
    r'.*__pycache__.*',
    r'.*\.pyc$',
    r'.*test.*',  # Tests can use direct access for simplicity
    r'.*scripts/check_unsafe_db_access\.py$',  # This file itself
]

# Allowed patterns (exceptions)
ALLOWED_PATTERNS = [
    r'safe_get_row_value',  # Our safe helper function
    r'len\(row\)',  # Checking length is OK
    r'isinstance\(.*dict\)',  # Type checking is OK
    r'row\.get\(',  # Dict .get() is safe
    r'#.*row\[',  # Comments are OK
]


def should_ignore_file(file_path: Path) -> bool:
    """Check if file should be ignored."""
    file_str = str(file_path)
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, file_str, re.IGNORECASE):
            return True
    return False


def is_allowed_context(line: str, match_pos: int) -> bool:
    """Check if the match is in an allowed context."""
    # Check if it's in a comment
    comment_pos = line.find('#')
    if comment_pos != -1 and match_pos > comment_pos:
        return True
    
    # Check if it's part of an allowed pattern
    for pattern in ALLOWED_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    
    return False


def check_file(file_path: Path) -> list[dict[str, Any]]:
    """Check a single file for unsafe patterns."""
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return violations
    
    for line_num, line in enumerate(lines, 1):
        for pattern, description in UNSAFE_PATTERNS:
            for match in re.finditer(pattern, line):
                match_pos = match.start()
                
                # Skip if in allowed context
                if is_allowed_context(line, match_pos):
                    continue
                
                violations.append({
                    'file': str(file_path),
                    'line': line_num,
                    'column': match_pos + 1,
                    'pattern': match.group(0),
                    'description': description,
                    'code': line.rstrip(),
                })
    
    return violations


def check_directory(directory: Path) -> list[dict[str, Any]]:
    """Check all Python files in a directory."""
    violations = []
    
    for py_file in directory.rglob('*.py'):
        if should_ignore_file(py_file):
            continue
        
        file_violations = check_file(py_file)
        violations.extend(file_violations)
    
    return violations


def format_violation(violation: dict[str, Any]) -> str:
    """Format a violation for display."""
    return (
        f"{violation['file']}:{violation['line']}:{violation['column']}: "
        f"{violation['description']}: {violation['pattern']}\n"
        f"  {violation['code']}\n"
        f"  Use safe_get_row_value() from src.db instead\n"
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Check for unsafe database result access patterns'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Show fix suggestions (not implemented yet)',
    )
    parser.add_argument(
        '--files',
        nargs='+',
        help='Specific files to check (default: all src/ and tests/)',
    )
    args = parser.parse_args()
    
    violations = []
    
    if args.files:
        # Check specific files
        for file_path_str in args.files:
            file_path = Path(file_path_str)
            if file_path.exists() and file_path.suffix == '.py':
                violations.extend(check_file(file_path))
            else:
                print(f"Warning: {file_path} not found or not a Python file", file=sys.stderr)
    else:
        # Check all source directories
        project_root = Path(__file__).parent.parent
        for dir_name in SOURCE_DIRS:
            dir_path = project_root / dir_name
            if dir_path.exists():
                violations.extend(check_directory(dir_path))
            else:
                print(f"Warning: {dir_path} not found", file=sys.stderr)
    
    if violations:
        print(f"Found {len(violations)} unsafe database access pattern(s):\n")
        for violation in violations:
            print(format_violation(violation))
        
        print(
            "\nTo fix: Use safe_get_row_value() from src.db\n"
            "Example: value = safe_get_row_value(row, 'column_name', '') or safe_get_row_value(row, 0, '')\n"
            "See docs/tech/SAFE_DB_RESULT_HANDLING.md for details.\n"
        )
        return 1
    else:
        print("OK: No unsafe database access patterns found")
        return 0


if __name__ == '__main__':
    sys.exit(main())

