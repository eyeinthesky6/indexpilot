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
from typing import TypedDict

# Patterns to detect unsafe tuple access
UNSAFE_PATTERNS = [
    # Direct tuple index access: row[0], row[1], etc.
    (r"\brow\[(\d+)\]", "Direct tuple index access"),
    (r"\bresult\[(\d+)\]", "Direct tuple index access"),
    (r"\btable_row\[(\d+)\]", "Direct tuple index access"),
    (r"\bquery_row\[(\d+)\]", "Direct tuple index access"),
    # Common database result variable names
    (
        r"\b(data|record|item|entry|value|db_result|query_result|fetch_result)\[(\d+)\]",
        "Direct tuple index access (database result)",
    ),
    # Direct access from fetchone/fetchall: fetchone()[0], fetchall()[0][0]
    (r"fetchone\(\)\[(\d+)\]", "Unsafe tuple access from fetchone()"),
    (r"fetchall\(\)\[(\d+)\]", "Unsafe tuple access from fetchall()"),
    (r"fetchone\(\)\[(\d+)\]\[(\d+)\]", "Unsafe nested tuple access from fetchone()"),
    (r"fetchall\(\)\[(\d+)\]\[(\d+)\]", "Unsafe nested tuple access from fetchall()"),
    # Access with len check but still unsafe (should use helper)
    (r"row\[(\d+)\]\s+if\s+len\(row\)\s*>\s*\d+\s+else", "Unsafe tuple access with len check"),
    (
        r"result\[(\d+)\]\s+if\s+len\(result\)\s*>\s*\d+\s+else",
        "Unsafe tuple access with len check",
    ),
]

# Files to check
SOURCE_DIRS = ["src", "tests"]
# Files to ignore
IGNORE_PATTERNS = [
    r".*__pycache__.*",
    r".*\.pyc$",
    r"^tests/.*",  # Only ignore files in tests/ directory
    r".*scripts/check_unsafe_db_access\.py$",  # This file itself
]

# Allowed patterns (exceptions)
ALLOWED_PATTERNS = [
    r"safe_get_row_value",  # Our safe helper function
    r"len\(row\)",  # Checking length is OK
    r"isinstance\(.*dict\)",  # Type checking is OK
    r"row\.get\(",  # Dict .get() is safe
    r"result\.get\(",  # Dict .get() is safe
    r"data\.get\(",  # Dict .get() is safe
    r"record\.get\(",  # Dict .get() is safe
    r"#.*row\[",  # Comments are OK
    # Function return values (not database results) - these have context checks
    r"chi2_result\[",  # From chi2_contingency() function
    r"throttle_result\[",  # From should_throttle_index_creation() function
]


def should_ignore_file(file_path: Path) -> bool:
    """Check if file should be ignored."""
    file_str = str(file_path)
    return any(re.search(pattern, file_str, re.IGNORECASE) for pattern in IGNORE_PATTERNS)


def is_allowed_context(
    line: str, match_pos: int, lines: list[str] | None = None, line_num: int = 0
) -> bool:
    """Check if the match is in an allowed context."""
    # Check if it's in a comment
    comment_pos = line.find("#")
    if comment_pos != -1 and match_pos >= comment_pos:
        return True

    # Check if we're inside a docstring by looking at previous lines
    if lines is not None and line_num > 0:
        in_docstring = False
        docstring_quote = None
        for i in range(line_num - 1, -1, -1):
            prev_line = lines[i]
            # Check for docstring start/end
            if '"""' in prev_line:
                # Count occurrences to determine if we're inside
                count = prev_line.count('"""')
                if count % 2 == 1:  # Odd number means docstring boundary
                    in_docstring = not in_docstring
                    docstring_quote = '"""'
            elif "'''" in prev_line:
                count = prev_line.count("'''")
                if count % 2 == 1:
                    in_docstring = not in_docstring
                    docstring_quote = "'''"

            # If we found a docstring start, check current line
            if in_docstring and docstring_quote and docstring_quote in line:
                # Check if match is before closing quote
                quote_pos = line.find(docstring_quote)
                if quote_pos != -1 and match_pos < quote_pos:
                    return True
            elif in_docstring:
                # We're inside a docstring
                return True

    # Check if it's in a docstring or string literal on current line
    # Look for quotes around the match
    stripped = line.strip()
    # If line starts with quotes (docstring continuation) or contains quotes before match
    if (
        stripped.startswith('"""')
        or stripped.startswith("'''")
        or stripped.startswith('"')
        or stripped.startswith("'")
    ):
        # Check if match is inside quotes by finding quote pairs
        before = line[:match_pos]

        # Count unescaped quotes before match
        single_before = len(list(re.finditer(r"(?<!\\)'", before)))
        double_before = len(list(re.finditer(r'(?<!\\)"', before)))
        triple_single_before = before.count("'''") - before.count("\\'''")
        triple_double_before = before.count('"""') - before.count('\\"""')

        # If odd number of quotes before, we're inside a string
        if (
            (single_before % 2 == 1 and triple_single_before % 2 == 0)
            or (double_before % 2 == 1 and triple_double_before % 2 == 0)
            or (triple_single_before % 2 == 1)
            or (triple_double_before % 2 == 1)
        ):
            return True

    # Check if line contains common docstring/comment patterns
    if (
        ("e.g.," in line or "example" in line.lower() or "docstring" in line.lower())
        and match_pos > len(line) * 0.5  # Match is in second half (likely in example)
    ):
        return True

    # Check if it's part of an allowed pattern
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWED_PATTERNS)


class Violation(TypedDict):
    """Type definition for violation dictionary."""

    file: str
    line: int
    column: int
    pattern: str
    description: str
    code: str


def check_file(file_path: Path) -> list[Violation]:
    """Check a single file for unsafe patterns."""
    violations: list[Violation] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return violations

    for line_num, line in enumerate(lines, 1):
        for pattern, description in UNSAFE_PATTERNS:
            for match in re.finditer(pattern, line):
                match_pos = match.start()

                # Skip if in allowed context
                if is_allowed_context(line, match_pos, lines, line_num - 1):
                    continue

                violations.append(
                    {
                        "file": str(file_path),
                        "line": line_num,
                        "column": match_pos + 1,
                        "pattern": match.group(0),
                        "description": description,
                        "code": line.rstrip(),
                    }
                )

    return violations


def check_directory(directory: Path) -> list[Violation]:
    """Check all Python files in a directory."""
    violations: list[Violation] = []

    for py_file in directory.rglob("*.py"):
        if should_ignore_file(py_file):
            continue

        file_violations = check_file(py_file)
        violations.extend(file_violations)

    return violations


def format_violation(violation: Violation) -> str:
    """Format a violation for display."""
    return (
        f"{violation['file']}:{violation['line']}:{violation['column']}: "
        f"{violation['description']}: {violation['pattern']}\n"
        f"  {violation['code']}\n"
        f"  Use safe_get_row_value() from src.db instead\n"
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check for unsafe database result access patterns")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Show fix suggestions (not implemented yet)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Specific files to check (default: all src/ and tests/)",
    )
    args = parser.parse_args()

    violations: list[Violation] = []

    if args.files:
        # Check specific files
        for file_path_str in args.files:  # type: ignore[misc]  # argparse returns Any, but we know it's list[str]
            file_path = Path(str(file_path_str))
            if file_path.exists() and file_path.suffix == ".py":
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


if __name__ == "__main__":
    sys.exit(main())
