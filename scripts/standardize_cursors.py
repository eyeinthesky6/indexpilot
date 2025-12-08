#!/usr/bin/env python3
"""
Cursor Standardization Script

Replaces manual cursor creation patterns with standardized get_cursor() context manager.

Usage:
    # Dry run (show what would change)
    python scripts/standardize_cursors.py --dry-run

    # Focus on specific file
    python scripts/standardize_cursors.py --focus src/simulation/simulator.py --dry-run

    # Focus on folder
    python scripts/standardize_cursors.py --focus src/simulation/ --dry-run

    # Live edit (make actual changes)
    python scripts/standardize_cursors.py --focus src/simulation/ --live

    # Scan multiple files/folders
    python scripts/standardize_cursors.py --focus src/simulation/ src/auto_indexer.py --dry-run
"""

import argparse
import ast
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


class CursorUsageAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze cursor usage patterns"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.cursor_patterns: list[dict[str, Any]] = []
        self.current_line = 0
        self.in_with_get_connection = False
        self.connection_var_name = None
        self.cursor_var_name = None
        self.uses_conn_commit = False
        self.uses_conn_rollback = False
        self.uses_conn_autocommit = False
        self.uses_connection_settings = False
        self.uses_real_dict_cursor = False
        self.uses_regular_cursor = False
        self.context_lines: list[int] = []

    def visit_With(self, node: ast.With):
        """Track with statements to identify get_connection() patterns"""
        # Check if this is a get_connection() context
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func = item.context_expr.func
                if isinstance(func, ast.Name) and func.id == "get_connection":
                    self.in_with_get_connection = True
                    if item.optional_vars:
                        self.connection_var_name = item.optional_vars.id if isinstance(item.optional_vars, ast.Name) else None
                    self.context_lines = list(range(node.lineno, node.end_lineno + 1 if hasattr(node, 'end_lineno') else node.lineno + 50))
                    break

        # Visit children
        self.generic_visit(node)

        # Reset after visiting
        if self.in_with_get_connection:
            self.in_with_get_connection = False
            self.connection_var_name = None
            self.context_lines = []

    def visit_Assign(self, node: ast.Assign):
        """Track cursor assignments"""
        if not self.in_with_get_connection:
            return

        # Check for cursor = conn.cursor(...) pattern
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if isinstance(node.value, ast.Call):
                    call = node.value
                    if isinstance(call.func, ast.Attribute):
                        # Check if it's conn.cursor(...)
                        if (
                            isinstance(call.func.value, ast.Name)
                            and call.func.value.id == self.connection_var_name
                            and call.func.attr == "cursor"
                        ):
                            self.cursor_var_name = var_name
                            # Check for RealDictCursor
                            if call.args:
                                for arg in call.args:
                                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                                        if arg.func.id == "RealDictCursor":
                                            self.uses_real_dict_cursor = True
                            elif call.keywords:
                                for kw in call.keywords:
                                    if kw.arg == "cursor_factory":
                                        if isinstance(kw.value, ast.Name) and kw.value.id == "RealDictCursor":
                                            self.uses_real_dict_cursor = True
                            else:
                                self.uses_regular_cursor = True

                            # Record pattern
                            self.cursor_patterns.append({
                                "line": node.lineno,
                                "cursor_var": var_name,
                                "conn_var": self.connection_var_name,
                                "uses_real_dict": self.uses_real_dict_cursor,
                                "uses_regular": self.uses_regular_cursor,
                            })

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Track connection method calls"""
        if not self.in_with_get_connection:
            return

        if isinstance(node.func, ast.Attribute):
            obj = node.func.value
            if isinstance(obj, ast.Name) and obj.id == self.connection_var_name:
                if node.func.attr == "commit":
                    self.uses_conn_commit = True
                elif node.func.attr == "rollback":
                    self.uses_conn_rollback = True
                elif node.func.attr == "autocommit":
                    self.uses_conn_autocommit = True

        # Check for SET statements
        if isinstance(node.func, ast.Attribute) and node.func.attr == "execute":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == self.cursor_var_name:
                if node.args and isinstance(node.args[0], ast.Constant):
                    sql = str(node.args[0].value)
                    if re.search(r"SET\s+(statement_timeout|lock_timeout|TRANSACTION)", sql, re.IGNORECASE):
                        self.uses_connection_settings = True

        self.generic_visit(node)


class CursorStandardizer:
    """Standardizes cursor usage patterns"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            "files_processed": 0,
            "files_modified": 0,
            "patterns_found": 0,
            "patterns_replaced": 0,
            "patterns_skipped": 0,
            "errors": 0,
        }

    def analyze_file(self, file_path: Path) -> dict[str, Any]:
        """Analyze a file for cursor usage patterns"""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            analyzer = CursorUsageAnalyzer(file_path)
            analyzer.visit(tree)

            # Also do regex-based analysis for more patterns
            patterns = self._find_patterns_regex(content, file_path)

            return {
                "file": file_path,
                "patterns": patterns,
                "ast_patterns": analyzer.cursor_patterns,
                "uses_conn_commit": analyzer.uses_conn_commit,
                "uses_conn_rollback": analyzer.uses_conn_rollback,
                "uses_conn_autocommit": analyzer.uses_conn_autocommit,
                "uses_connection_settings": analyzer.uses_connection_settings,
            }
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            self.stats["errors"] += 1
            return {"file": file_path, "patterns": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            self.stats["errors"] += 1
            return {"file": file_path, "patterns": [], "error": str(e)}

    def _find_patterns_regex(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """Find cursor patterns using regex (more comprehensive)"""
        patterns = []
        lines = content.split("\n")

        # Pattern 1: with get_connection() as conn: cursor = conn.cursor(...)
        pattern1 = re.compile(
            r"with\s+get_connection\(\)\s+as\s+(\w+):\s*\n"
            r"(?:.*\n)*?"
            r"(\s+)(\w+)\s*=\s*\1\.cursor\((?:cursor_factory\s*=\s*RealDictCursor)?\)"
        )

        for match in pattern1.finditer(content):
            indent = match.group(2)
            cursor_var = match.group(3)
            conn_var = match.group(1)
            start_line = content[: match.start()].count("\n") + 1

            # Check if this pattern can be safely replaced
            context_start = match.start()
            context_end = min(match.end() + 500, len(content))  # Look ahead 500 chars
            context = content[context_start:context_end]

            # Check for special cases
            needs_connection = bool(
                re.search(rf"{re.escape(conn_var)}\.(commit|rollback|autocommit)", context)
                or re.search(r"SET\s+(statement_timeout|lock_timeout|TRANSACTION)", context, re.IGNORECASE)
            )

            uses_real_dict = "RealDictCursor" in match.group(0)

            patterns.append({
                "line": start_line,
                "type": "with_get_connection_cursor",
                "cursor_var": cursor_var,
                "conn_var": conn_var,
                "indent": indent,
                "match_text": match.group(0),
                "needs_connection": needs_connection,
                "uses_real_dict": uses_real_dict,
                "safe_to_replace": not needs_connection and uses_real_dict,
            })

        return patterns

    def can_safely_replace(self, pattern: dict[str, Any], file_analysis: dict[str, Any]) -> bool:
        """Determine if a pattern can be safely replaced"""
        # Skip if file has special connection usage
        if file_analysis.get("uses_conn_autocommit"):
            return False
        if file_analysis.get("uses_connection_settings"):
            return False

        # Skip if pattern needs connection object
        if pattern.get("needs_connection"):
            return False

        # Only replace RealDictCursor patterns (most common)
        if not pattern.get("uses_real_dict", True):
            # Regular cursors might be intentional
            return False

        return True

    def replace_pattern(self, content: str, pattern: dict[str, Any]) -> tuple[str, bool]:
        """Replace a cursor pattern with get_cursor()"""
        lines = content.split("\n")
        pattern_line = pattern["line"] - 1  # 0-indexed

        if pattern_line >= len(lines):
            return content, False

        # Find the with get_connection block
        # Look for: with get_connection() as conn:
        conn_var = pattern.get("conn_var", "conn")
        cursor_var = pattern.get("cursor_var", "cursor")

        # Find the with statement
        with_line_idx = None
        for i in range(max(0, pattern_line - 20), pattern_line + 1):
            if re.search(rf"with\s+get_connection\(\)\s+as\s+{re.escape(conn_var)}:", lines[i]):
                with_line_idx = i
                break

        if with_line_idx is None:
            return content, False

        # Find the cursor assignment line
        cursor_line_idx = None
        for i in range(with_line_idx, min(len(lines), with_line_idx + 30)):
            if re.search(rf"{re.escape(cursor_var)}\s*=\s*{re.escape(conn_var)}\.cursor", lines[i]):
                cursor_line_idx = i
                break

        if cursor_line_idx is None:
            return content, False

        # Find the try/finally block
        try_line_idx = None
        finally_line_idx = None
        cursor_close_line_idx = None

        for i in range(cursor_line_idx, min(len(lines), cursor_line_idx + 50)):
            if lines[i].strip().startswith("try:"):
                try_line_idx = i
            elif lines[i].strip().startswith("finally:"):
                finally_line_idx = i
            elif re.search(rf"{re.escape(cursor_var)}\.close\(\)", lines[i]):
                cursor_close_line_idx = i

        # Build replacement
        indent = len(lines[with_line_idx]) - len(lines[with_line_idx].lstrip())

        # Replace with get_cursor()
        new_lines = lines.copy()

        # Replace the with statement
        new_lines[with_line_idx] = " " * indent + f"with get_cursor() as {cursor_var}:"

        # Remove cursor assignment line
        if cursor_line_idx is not None:
            new_lines.pop(cursor_line_idx)
            # Adjust indices
            if try_line_idx and try_line_idx > cursor_line_idx:
                try_line_idx -= 1
            if finally_line_idx and finally_line_idx > cursor_line_idx:
                finally_line_idx -= 1
            if cursor_close_line_idx and cursor_close_line_idx > cursor_line_idx:
                cursor_close_line_idx -= 1

        # Remove cursor.close() in finally block
        if cursor_close_line_idx is not None:
            new_lines.pop(cursor_close_line_idx)

        # If finally block is now empty, remove it
        if finally_line_idx is not None:
            # Check if finally block is empty
            finally_content = "\n".join(
                lines[finally_line_idx + 1 : cursor_close_line_idx if cursor_close_line_idx else len(lines)]
            ).strip()
            if not finally_content or finally_content == "pass":
                # Remove finally block
                for i in range(finally_line_idx, cursor_close_line_idx + 1 if cursor_close_line_idx else len(lines)):
                    if i < len(new_lines):
                        new_lines.pop(finally_line_idx)

        return "\n".join(new_lines), True

    def process_file(self, file_path: Path, focus_mode: bool = False) -> dict[str, Any]:
        """Process a single file"""
        logger.info(f"Analyzing {file_path}...")
        self.stats["files_processed"] += 1

        analysis = self.analyze_file(file_path)
        if "error" in analysis:
            return analysis

        patterns = analysis.get("patterns", [])
        self.stats["patterns_found"] += len(patterns)

        if not patterns:
            return {"file": file_path, "status": "no_patterns", "patterns": []}

        # Filter patterns that can be safely replaced
        replaceable = [
            p for p in patterns if self.can_safely_replace(p, analysis)
        ]

        if not replaceable:
            self.stats["patterns_skipped"] += len(patterns)
            return {
                "file": file_path,
                "status": "no_replaceable",
                "patterns": patterns,
                "reason": "Patterns need connection object or are not RealDictCursor",
            }

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would replace {len(replaceable)} pattern(s) in {file_path}")
            for p in replaceable:
                logger.info(f"    Line {p['line']}: {p.get('type', 'unknown')}")
            return {
                "file": file_path,
                "status": "would_replace",
                "patterns": replaceable,
                "count": len(replaceable),
            }

        # Live edit mode
        try:
            content = file_path.read_text(encoding="utf-8")
            modified = False
            replacements_made = 0

            for pattern in replaceable:
                new_content, replaced = self.replace_pattern(content, pattern)
                if replaced:
                    content = new_content
                    modified = True
                    replacements_made += 1

            if modified:
                file_path.write_text(content, encoding="utf-8")
                self.stats["files_modified"] += 1
                self.stats["patterns_replaced"] += replacements_made
                logger.info(f"  [LIVE] Replaced {replacements_made} pattern(s) in {file_path}")
                return {
                    "file": file_path,
                    "status": "modified",
                    "replacements": replacements_made,
                }
            else:
                return {
                    "file": file_path,
                    "status": "no_changes",
                    "patterns": replaceable,
                }
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            self.stats["errors"] += 1
            return {"file": file_path, "status": "error", "error": str(e)}

    def process_paths(self, paths: list[Path], focus_mode: bool = False) -> list[dict[str, Any]]:
        """Process multiple files/folders"""
        files_to_process: list[Path] = []

        for path in paths:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.warning(f"Path does not exist: {path}")
                continue

            if path_obj.is_file():
                if path_obj.suffix == ".py":
                    files_to_process.append(path_obj)
            elif path_obj.is_dir():
                # Find all Python files
                for py_file in path_obj.rglob("*.py"):
                    # Skip __pycache__ and .pyc files
                    if "__pycache__" not in str(py_file):
                        files_to_process.append(py_file)

        # Remove duplicates and sort
        files_to_process = sorted(set(files_to_process))

        logger.info(f"Found {len(files_to_process)} Python file(s) to process")

        results = []
        for file_path in files_to_process:
            result = self.process_file(file_path, focus_mode)
            results.append(result)

        return results

    def print_stats(self):
        """Print statistics"""
        print("\n" + "=" * 60)
        print("CURSOR STANDARDIZATION STATISTICS")
        print("=" * 60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Files modified: {self.stats['files_modified']}")
        print(f"Patterns found: {self.stats['patterns_found']}")
        print(f"Patterns replaced: {self.stats['patterns_replaced']}")
        print(f"Patterns skipped: {self.stats['patterns_skipped']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Standardize cursor usage patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--focus",
        nargs="+",
        help="Focus on specific file(s) or folder(s)",
        default=[],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry run mode (show what would change, default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live edit mode (make actual changes, overrides --dry-run)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all Python files in src/ and scripts/",
    )

    args = parser.parse_args()

    # Determine mode
    dry_run = not args.live

    if dry_run:
        logger.info("Running in DRY RUN mode (no changes will be made)")
    else:
        logger.warning("Running in LIVE mode (changes will be made to files)")

    # Determine paths to process
    if args.all:
        paths = [Path("src"), Path("scripts")]
        logger.info("Processing all Python files in src/ and scripts/")
    elif args.focus:
        paths = [Path(p) for p in args.focus]
        logger.info(f"Focusing on: {', '.join(str(p) for p in paths)}")
    else:
        logger.error("Must specify --focus or --all")
        parser.print_help()
        sys.exit(1)

    # Run standardizer
    standardizer = CursorStandardizer(dry_run=dry_run)
    results = standardizer.process_paths(paths, focus_mode=bool(args.focus))

    # Print results
    standardizer.print_stats()

    # Summary
    if dry_run:
        print("\n💡 Run with --live to apply changes")
    else:
        print("\n✅ Changes applied")

    # Exit code
    if standardizer.stats["errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

