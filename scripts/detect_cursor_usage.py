#!/usr/bin/env python3
"""
Cursor Usage Detection Tool

Detects all cursor usage patterns in the codebase to identify what needs to be migrated.

Usage:
    # Detect all cursor usage patterns
    python scripts/detect_cursor_usage.py --all

    # Focus on specific file/folder
    python scripts/detect_cursor_usage.py --focus src/simulation/

    # Show detailed analysis
    python scripts/detect_cursor_usage.py --all --detailed
"""

import argparse
import ast
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


class CursorPatternDetector(ast.NodeVisitor):
    """AST visitor to detect all cursor usage patterns"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.patterns: list[dict[str, Any]] = []
        self.current_line = 0
        self.in_with_get_connection = False
        self.connection_var_name = None
        self.context_stack: list[dict[str, Any]] = []

    def visit_With(self, node: ast.With):
        """Track with statements"""
        # Check for get_connection() pattern
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func = item.context_expr.func
                if isinstance(func, ast.Name) and func.id == "get_connection":
                    self.in_with_get_connection = True
                    if item.optional_vars:
                        self.connection_var_name = (
                            item.optional_vars.id
                            if isinstance(item.optional_vars, ast.Name)
                            else None
                        )
                    self.context_stack.append({
                        "type": "with_get_connection",
                        "line": node.lineno,
                        "end_line": node.end_lineno if hasattr(node, "end_lineno") else None,
                        "conn_var": self.connection_var_name,
                    })
                    break

        # Check for get_cursor() pattern (already standardized)
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func = item.context_expr.func
                if isinstance(func, ast.Name) and func.id == "get_cursor":
                    self.patterns.append({
                        "type": "already_standardized",
                        "line": node.lineno,
                        "end_line": node.end_lineno if hasattr(node, "end_lineno") else None,
                        "status": "ok",
                    })

        self.generic_visit(node)

        # Pop context when done
        if self.in_with_get_connection:
            if self.context_stack:
                self.context_stack.pop()
            self.in_with_get_connection = False
            self.connection_var_name = None

    def visit_Assign(self, node: ast.Assign):
        """Track cursor assignments"""
        # Check for cursor = conn.cursor(...) pattern
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if isinstance(node.value, ast.Call):
                    call = node.value
                    if (
                        isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.attr == "cursor"
                    ):
                        # Found cursor assignment
                        conn_var = call.func.value.id
                        uses_real_dict = False
                        uses_regular = False

                        # Check for RealDictCursor
                        for arg in call.args:
                            if isinstance(arg, ast.Call):
                                if isinstance(arg.func, ast.Name) and arg.func.id == "RealDictCursor":
                                    uses_real_dict = True
                            elif isinstance(arg, ast.Name) and arg.id == "RealDictCursor":
                                uses_real_dict = True

                        for kw in call.keywords:
                            if kw.arg == "cursor_factory":
                                if isinstance(kw.value, ast.Name) and kw.value.id == "RealDictCursor":
                                    uses_real_dict = True
                                elif isinstance(kw.value, ast.Call):
                                    if isinstance(kw.value.func, ast.Name) and kw.value.func.id == "RealDictCursor":
                                        uses_real_dict = True

                        if not uses_real_dict:
                            uses_regular = True

                        self.patterns.append({
                            "type": "cursor_assignment",
                            "line": node.lineno,
                            "cursor_var": var_name,
                            "conn_var": conn_var,
                            "uses_real_dict": uses_real_dict,
                            "uses_regular": uses_regular,
                            "in_with_get_connection": self.in_with_get_connection,
                            "context": self.context_stack[-1] if self.context_stack else None,
                        })

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Track cursor and connection method calls"""
        if isinstance(node.func, ast.Attribute):
            obj = node.func.value
            if isinstance(obj, ast.Name):
                # Check for cursor.close()
                if node.func.attr == "close":
                    self.patterns.append({
                        "type": "cursor_close",
                        "line": node.lineno,
                        "cursor_var": obj.id,
                    })

                # Check for conn.commit(), conn.rollback(), conn.autocommit
                if node.func.attr in ("commit", "rollback", "autocommit"):
                    if self.in_with_get_connection and obj.id == self.connection_var_name:
                        self.patterns.append({
                            "type": f"conn_{node.func.attr}",
                            "line": node.lineno,
                            "conn_var": obj.id,
                        })

        self.generic_visit(node)


class CursorDetector:
    """Detects all cursor usage patterns"""

    def __init__(self, detailed: bool = False):
        self.detailed = detailed
        self.stats = {
            "files_processed": 0,
            "files_with_patterns": 0,
            "total_patterns": 0,
            "patterns_by_type": defaultdict(int),
            "errors": 0,
        }

    def detect_file(self, file_path: Path) -> dict[str, Any]:
        """Detect cursor patterns in a file"""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            # AST-based detection
            detector = CursorPatternDetector(file_path)
            detector.visit(tree)

            # Regex-based detection (for patterns AST might miss)
            regex_patterns = self._detect_regex(content, file_path)

            # Combine results
            all_patterns = detector.patterns + regex_patterns

            # Analyze patterns
            analysis = self._analyze_patterns(all_patterns, content, file_path)

            if all_patterns:
                self.stats["files_with_patterns"] += 1
                self.stats["total_patterns"] += len(all_patterns)
                for p in all_patterns:
                    self.stats["patterns_by_type"][p.get("type", "unknown")] += 1

            return {
                "file": file_path,
                "patterns": all_patterns,
                "analysis": analysis,
                "pattern_count": len(all_patterns),
            }
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            self.stats["errors"] += 1
            return {"file": file_path, "patterns": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            self.stats["errors"] += 1
            return {"file": file_path, "patterns": [], "error": str(e)}

    def _detect_regex(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """Detect patterns using regex (complementary to AST)"""
        patterns = []
        lines = content.split("\n")

        # Pattern 1: with get_connection() as conn:
        for i, line in enumerate(lines, 1):
            if re.search(r"with\s+get_connection\(\)\s+as\s+\w+\s*:", line):
                patterns.append({
                    "type": "with_get_connection_regex",
                    "line": i,
                    "line_content": line.strip(),
                })

        # Pattern 2: cursor = conn.cursor(...)
        for i, line in enumerate(lines, 1):
            if re.search(r"\w+\s*=\s*\w+\.cursor\(", line):
                match = re.search(r"(\w+)\s*=\s*(\w+)\.cursor\(", line)
                if match:
                    cursor_var = match.group(1)
                    conn_var = match.group(2)
                    uses_real_dict = "RealDictCursor" in line
                    patterns.append({
                        "type": "cursor_assignment_regex",
                        "line": i,
                        "cursor_var": cursor_var,
                        "conn_var": conn_var,
                        "uses_real_dict": uses_real_dict,
                        "line_content": line.strip(),
                    })

        # Pattern 3: cursor.close()
        for i, line in enumerate(lines, 1):
            if re.search(r"\w+\.close\(\)", line):
                match = re.search(r"(\w+)\.close\(\)", line)
                if match:
                    var_name = match.group(1)
                    patterns.append({
                        "type": "cursor_close_regex",
                        "line": i,
                        "cursor_var": var_name,
                        "line_content": line.strip(),
                    })

        # Pattern 4: Already using get_cursor()
        for i, line in enumerate(lines, 1):
            if re.search(r"with\s+get_cursor\(\)\s+as\s+\w+\s*:", line):
                patterns.append({
                    "type": "already_standardized_regex",
                    "line": i,
                    "line_content": line.strip(),
                    "status": "ok",
                })

        # Pattern 5: Direct cursor creation (not in with block)
        for i, line in enumerate(lines, 1):
            # Look for cursor = conn.cursor() not inside a with block
            if re.search(r"\w+\s*=\s*\w+\.cursor\(", line):
                # Check if previous lines have "with get_connection"
                context_start = max(0, i - 20)
                context = "\n".join(lines[context_start:i])
                if not re.search(r"with\s+get_connection", context):
                    match = re.search(r"(\w+)\s*=\s*(\w+)\.cursor\(", line)
                    if match:
                        patterns.append({
                            "type": "direct_cursor_creation",
                            "line": i,
                            "cursor_var": match.group(1),
                            "conn_var": match.group(2),
                            "line_content": line.strip(),
                            "warning": "Cursor created outside with get_connection() block",
                        })

        return patterns

    def _analyze_patterns(
        self, patterns: list[dict[str, Any]], content: str, file_path: Path
    ) -> dict[str, Any]:
        """Analyze patterns to determine migration status"""
        analysis = {
            "needs_migration": False,
            "migration_complexity": "simple",
            "blockers": [],
            "warnings": [],
            "safe_to_migrate": True,
            "migratable_count": 0,
        }

        # Filter out already standardized patterns
        already_standardized_types = ("already_standardized", "already_standardized_regex")
        non_standardized = [p for p in patterns if p.get("type") not in already_standardized_types]

        # Check for blockers (patterns that prevent migration)
        has_conn_commit = any(p.get("type") == "conn_commit" for p in patterns)
        has_conn_rollback = any(p.get("type") == "conn_rollback" for p in patterns)
        has_conn_autocommit = any(p.get("type") == "conn_autocommit" for p in patterns)

        if has_conn_commit or has_conn_rollback or has_conn_autocommit:
            analysis["blockers"].append("Uses conn.commit()/rollback()/autocommit - needs connection object")
            analysis["safe_to_migrate"] = False
            analysis["migration_complexity"] = "complex"

        # Deduplicate: prefer AST patterns over regex (more accurate)
        # Group by line number and pattern type
        cursor_assignments = {}
        for p in non_standardized:
            ptype = p.get("type", "")
            line = p.get("line")
            
            # Only count actual cursor assignments that need migration
            if ptype in ("cursor_assignment", "cursor_assignment_regex"):
                if line not in cursor_assignments or "regex" not in ptype:
                    cursor_assignments[line] = p

        # Find all with get_connection blocks to check context
        with_blocks = []
        for p in non_standardized:
            if p.get("type") in ("with_get_connection", "with_get_connection_regex"):
                with_blocks.append(p.get("line"))

        # Count migratable patterns (cursor assignments in with get_connection blocks)
        migratable = []
        excluded_by_blocker = []
        excluded_not_in_with = []
        excluded_no_real_dict = []
        lines = content.split("\n")
        
        # Find get_cursor() definition line
        get_cursor_def_line = None
        for i, line_content in enumerate(lines, 1):
            if "def get_cursor" in line_content:
                get_cursor_def_line = i
                break
        
        for line, pattern in cursor_assignments.items():
            # CRITICAL: Never migrate get_cursor() function definition itself
            line_num = pattern.get("line")
            if line_num and get_cursor_def_line:
                # If pattern is within 20 lines of get_cursor definition, skip it
                if abs(get_cursor_def_line - line_num) < 20:
                    excluded_not_in_with.append((line_num, pattern))
                    continue  # Skip - this is the get_cursor() definition itself
            line_num = pattern.get("line")
            if line_num is None:
                continue
                
            # Check if this cursor assignment is within a with get_connection block
            # Find the nearest with get_connection before this line
            in_with_block = False
            for with_line in with_blocks:
                if with_line < line_num:
                    # Check if we're still in that block (look ahead up to 100 lines)
                    block_end = min(len(lines), with_line + 100)
                    for check_line in range(with_line, block_end):
                        if check_line == line_num:
                            in_with_block = True
                            break
                        # Check if we've left the block (less indentation)
                        if check_line < len(lines):
                            with_indent = len(lines[with_line - 1]) - len(lines[with_line - 1].lstrip())
                            check_indent = len(lines[check_line]) - len(lines[check_line].lstrip())
                            if check_line > with_line and check_indent <= with_indent and lines[check_line].strip():
                                break
                    if in_with_block:
                        break
            
            # Also check AST context if available
            if not in_with_block:
                in_with_block = pattern.get("in_with_get_connection") or pattern.get("context") is not None

            if in_with_block:
                # Check for blockers - if file uses conn.commit/rollback/autocommit, can't migrate
                if not analysis["safe_to_migrate"]:
                    excluded_by_blocker.append((line_num, pattern))
                # Check if uses RealDictCursor (preferred) or regular cursor (might still be migratable)
                elif not pattern.get("uses_real_dict", False):
                    # Regular cursor - might still be migratable, but less common
                    # Only exclude if we're being strict
                    excluded_no_real_dict.append((line_num, pattern))
                else:
                    # Migratable!
                    migratable.append(pattern)
            else:
                # Not in with get_connection block - might be direct creation
                excluded_not_in_with.append((line_num, pattern))

        analysis["migratable_count"] = len(migratable)
        analysis["migratable_patterns"] = migratable
        analysis["excluded_by_blocker"] = excluded_by_blocker
        analysis["excluded_not_in_with"] = excluded_not_in_with
        analysis["excluded_no_real_dict"] = excluded_no_real_dict

        # Check for patterns that need migration
        if migratable:
            analysis["needs_migration"] = True

        # Check for direct cursor creation (outside with block) - these are warnings but might be migratable
        direct_creations = [p for p in patterns if p.get("type") == "direct_cursor_creation"]
        if direct_creations:
            analysis["warnings"].append(f"Found {len(direct_creations)} cursor creation(s) outside with block")
            if not analysis["blockers"]:
                analysis["migration_complexity"] = "complex"

        # Check if already standardized (no migratable patterns)
        already_standardized = [
            p for p in patterns
            if p.get("type") in already_standardized_types
        ]
        if already_standardized and not migratable:
            analysis["needs_migration"] = False
            analysis["status"] = "already_standardized"

        return analysis

    def process_paths(self, paths: list[Path]) -> list[dict[str, Any]]:
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
                for py_file in path_obj.rglob("*.py"):
                    if "__pycache__" not in str(py_file):
                        files_to_process.append(py_file)

        files_to_process = sorted(set(files_to_process))
        logger.info(f"Found {len(files_to_process)} Python file(s) to analyze")

        results = []
        for i, file_path in enumerate(files_to_process, 1):
            self.stats["files_processed"] += 1
            result = self.detect_file(file_path)
            results.append(result)

            if result.get("pattern_count", 0) > 0:
                logger.info(
                    f"[{i}/{len(files_to_process)}] {file_path}: "
                    f"{result['pattern_count']} pattern(s) found"
                )

        return results

    def print_report(self, results: list[dict[str, Any]]):
        """Print detection report"""
        print("\n" + "=" * 80)
        print("CURSOR USAGE DETECTION REPORT")
        print("=" * 80)

        # Summary
        print(f"\nFiles processed: {self.stats['files_processed']}")
        print(f"Files with patterns: {self.stats['files_with_patterns']}")
        print(f"Total patterns detected: {self.stats['total_patterns']}")
        print(f"Errors: {self.stats['errors']}")

        # Pattern breakdown (excluding already standardized)
        print("\nPattern breakdown (excluding already standardized):")
        for pattern_type, count in sorted(self.stats["patterns_by_type"].items()):
            if "already_standardized" not in pattern_type:
                print(f"  {pattern_type}: {count}")

        # Files needing migration (only count migratable patterns)
        files_needing_migration = []
        total_migratable = 0
        total_excluded_blocker = 0
        total_excluded_not_in_with = 0
        total_excluded_no_real_dict = 0
        
        for result in results:
            analysis = result.get("analysis", {})
            migratable_count = analysis.get("migratable_count", 0)
            if migratable_count > 0:
                files_needing_migration.append(result)
                total_migratable += migratable_count
            total_excluded_blocker += len(analysis.get("excluded_by_blocker", []))
            total_excluded_not_in_with += len(analysis.get("excluded_not_in_with", []))
            total_excluded_no_real_dict += len(analysis.get("excluded_no_real_dict", []))

        print(f"\nFiles needing migration: {len(files_needing_migration)}")
        print(f"Total instances to migrate: {total_migratable}")
        print(f"\nExcluded patterns:")
        print(f"  Blocked (uses conn.commit/rollback/autocommit): {total_excluded_blocker}")
        print(f"  Not in with get_connection block: {total_excluded_not_in_with}")
        print(f"  Regular cursor (not RealDictCursor): {total_excluded_no_real_dict}")

        if files_needing_migration:
            print("\nFiles that need migration:")
            for result in files_needing_migration:
                file_path = result["file"]
                analysis = result.get("analysis", {})
                migratable_count = analysis.get("migratable_count", 0)
                complexity = analysis.get("migration_complexity", "unknown")
                blockers = analysis.get("blockers", [])
                warnings = analysis.get("warnings", [])

                print(f"\n  {file_path}")
                print(f"    Instances to migrate: {migratable_count}")
                print(f"    Complexity: {complexity}")
                if blockers:
                    print(f"    Blockers: {', '.join(blockers)}")
                if warnings:
                    print(f"    Warnings: {', '.join(warnings)}")

                if self.detailed:
                    print(f"    Migratable pattern details:")
                    for pattern in analysis.get("migratable_patterns", []):
                        line = pattern.get("line", "?")
                        cursor_var = pattern.get("cursor_var", "?")
                        conn_var = pattern.get("conn_var", "?")
                        print(f"      Line {line}: cursor={cursor_var}, conn={conn_var}")
                    
                    # Show excluded patterns if any
                    excluded_blocker = analysis.get("excluded_by_blocker", [])
                    if excluded_blocker:
                        print(f"    Excluded (blocker): {len(excluded_blocker)} pattern(s)")
                        for line_num, pattern in excluded_blocker[:5]:  # Show first 5
                            print(f"      Line {line_num}: {pattern.get('cursor_var', '?')} (file uses conn.commit/rollback)")
                    
                    excluded_not_in_with = analysis.get("excluded_not_in_with", [])
                    if excluded_not_in_with:
                        print(f"    Excluded (not in with block): {len(excluded_not_in_with)} pattern(s)")
                        for line_num, pattern in excluded_not_in_with[:5]:  # Show first 5
                            print(f"      Line {line_num}: {pattern.get('cursor_var', '?')} (direct creation)")
                    
                    excluded_no_real_dict = analysis.get("excluded_no_real_dict", [])
                    if excluded_no_real_dict:
                        print(f"    Excluded (regular cursor): {len(excluded_no_real_dict)} pattern(s)")
                        for line_num, pattern in excluded_no_real_dict[:5]:  # Show first 5
                            print(f"      Line {line_num}: {pattern.get('cursor_var', '?')} (not RealDictCursor)")

        # Already standardized files
        already_standardized = [
            r for r in results
            if r.get("analysis", {}).get("status") == "already_standardized"
        ]

        if already_standardized:
            print(f"\nAlready standardized files: {len(already_standardized)}")
            if self.detailed:
                for result in already_standardized[:10]:  # Show first 10
                    print(f"  {result['file']}")

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Detect cursor usage patterns in codebase",
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
        "--all",
        action="store_true",
        help="Process all Python files in src/ and scripts/",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed pattern information",
    )

    args = parser.parse_args()

    # Determine paths to process
    if args.all:
        paths = [Path("src"), Path("scripts")]
        logger.info("Analyzing all Python files in src/ and scripts/")
    elif args.focus:
        paths = [Path(p) for p in args.focus]
        logger.info(f"Focusing on: {', '.join(str(p) for p in paths)}")
    else:
        logger.error("Must specify --focus or --all")
        parser.print_help()
        sys.exit(1)

    # Run detector
    detector = CursorDetector(detailed=args.detailed)
    results = detector.process_paths(paths)

    # Print report
    detector.print_report(results)

    # Exit code
    if detector.stats["errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

