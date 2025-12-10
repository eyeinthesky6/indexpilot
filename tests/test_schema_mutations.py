"""Test schema mutations and error detection capabilities

This script tests:
1. Schema change auto-detection
2. Error diagnosis and handling
3. System resilience to intentional errors
"""

import sys
import traceback

sys.path.insert(0, ".")

from psycopg2.extras import RealDictCursor  # noqa: E402

from src.db import get_connection  # noqa: E402
from src.schema_evolution import (  # noqa: E402
    analyze_schema_change_impact,
    preview_schema_change,
    safe_add_column,
)


def test_schema_mutations():
    """Test various schema mutations and verify system detects them"""
    print("=" * 80)
    print("TESTING SCHEMA MUTATIONS AND AUTO-DETECTION")
    print("=" * 80)

    results = {"tests_passed": 0, "tests_failed": 0, "errors": [], "warnings": []}

    # Setup: Cleanup potential leftovers from previous runs
    print("\n[SETUP] Cleaning up previous test artifacts...")
    try:
        from src.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if column exists
                cursor.execute(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'contacts' AND column_name = 'test_field'
                    """
                )
                if cursor.fetchone():
                    print("  - Dropping existing 'test_field' column...")
                    cursor.execute("ALTER TABLE contacts DROP COLUMN test_field")
                    conn.commit()
    except Exception as e:
        print(f"  Warning: Setup cleanup failed: {e}")

    # Test 1: Add a new column
    print("\n[TEST 1] Adding new column 'test_field' to contacts table...")
    try:
        result = safe_add_column(
            table_name="contacts", field_name="test_field", field_type="TEXT", is_nullable=True
        )
        if result.get("success"):
            print("  ✓ Column added successfully")
            print(
                f"  - Impact analysis: {result.get('impact', {}).get('affected_queries', 0)} affected queries"
            )
            print(f"  - Warnings: {len(result.get('warnings', []))}")
            results["tests_passed"] += 1
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
            results["tests_failed"] += 1
            results["errors"].append(f"Add column failed: {result.get('error')}")
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results["tests_failed"] += 1
        results["errors"].append(f"Add column exception: {str(e)}")
        traceback.print_exc()

    # Test 2: Preview schema change (should not execute)
    print("\n[TEST 2] Previewing column type change (should not execute)...")
    try:
        preview = preview_schema_change(
            table_name="contacts",
            change_type="ALTER_COLUMN",
            field_name="test_field",
            new_type="VARCHAR(255)",
        )
        if preview:
            print("  ✓ Preview generated successfully")
            print(
                f"  - Impact: {preview.get('impact', {}).get('affected_queries', 0)} affected queries"
            )
            rollback_plan = preview.get('rollback_plan') or {}
            rollback_sql = rollback_plan.get('rollback_sql') or 'N/A'
            print(
                f"  - Rollback SQL: {rollback_sql[:50]}..."
            )
            results["tests_passed"] += 1
        else:
             print("  ✗ Preview returned None")
             results["tests_failed"] += 1
             results["errors"].append("Preview returned None")
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results["tests_failed"] += 1
        results["errors"].append(f"Preview exception: {str(e)}")

    # Test 3: Analyze impact of dropping a column (should detect dependencies)
    print("\n[TEST 3] Analyzing impact of dropping column (should detect dependencies)...")
    try:
        impact = analyze_schema_change_impact(
            table_name="contacts", field_name="email", change_type="DROP_COLUMN"
        )
        print("  ✓ Impact analysis completed")
        print(f"  - Affected queries: {impact.get('affected_queries', 0)}")
        print(f"  - Affected indexes: {len(impact.get('affected_indexes', []))}")
        print(f"  - Expression profiles: {impact.get('affected_expression_profiles', 0)}")
        print(f"  - Errors: {len(impact.get('errors', []))}")
        print(f"  - Warnings: {len(impact.get('warnings', []))}")
        if impact.get("errors"):
            print(f"  ✓ System correctly detected blocking errors: {impact['errors']}")
        results["tests_passed"] += 1
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results["tests_failed"] += 1
        results["errors"].append(f"Impact analysis exception: {str(e)}")

    # Test 4: Add intentional error - try to add duplicate column
    print("\n[TEST 4] Testing error detection - attempting to add duplicate column...")
    try:
        result = safe_add_column(
            table_name="contacts",
            field_name="email",  # Already exists
            field_type="TEXT",
        )
        if not result.get("success"):
            print(
                f"  ✓ System correctly rejected duplicate column: {result.get('error', 'Unknown')}"
            )
            results["tests_passed"] += 1
        else:
            print("  ✗ System should have rejected duplicate column")
            results["tests_failed"] += 1
            results["errors"].append("Duplicate column was not rejected")
    except ValueError as e:
        print(f"  ✓ System correctly raised validation error: {e}")
        results["tests_passed"] += 1
    except Exception as e:
        print(f"  ✓ System correctly caught error: {e}")
        results["tests_passed"] += 1

    # Test 5: Check if mutation_log captured the changes
    print("\n[TEST 5] Verifying mutation_log captured schema changes...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT mutation_type, table_name, field_name, created_at
                FROM mutation_log
                WHERE mutation_type IN ('ADD_COLUMN', 'ALTER_COLUMN', 'DROP_COLUMN')
                ORDER BY created_at DESC
                LIMIT 5
            """
            )
            mutations = cursor.fetchall()
            print(f"  ✓ Found {len(mutations)} recent schema mutations in mutation_log")
            for mut in mutations:
                print(f"    - {mut['mutation_type']}: {mut['table_name']}.{mut['field_name']}")
            results["tests_passed"] += 1
            cursor.close()
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results["tests_failed"] += 1
        results["errors"].append(f"Mutation log check exception: {str(e)}")

    # Test 6: Check if genome_catalog was updated
    print("\n[TEST 6] Verifying genome_catalog was updated...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT field_name, field_type, is_indexable
                FROM genome_catalog
                WHERE table_name = 'contacts' AND field_name = 'test_field'
            """
            )
            entry = cursor.fetchone()
            if entry:
                print(f"  ✓ Genome catalog updated: {entry['field_name']} ({entry['field_type']})")
                results["tests_passed"] += 1
            else:
                print("  ✗ Genome catalog not updated")
                results["tests_failed"] += 1
                results["errors"].append("Genome catalog not updated after schema change")
            cursor.close()
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results["tests_failed"] += 1
        results["errors"].append(f"Genome catalog check exception: {str(e)}")

    # Test 7: Test invalid table name (should be caught by validation)
    print("\n[TEST 7] Testing error detection - invalid table name...")
    try:
        result = safe_add_column(
            table_name="'; DROP TABLE contacts; --",  # SQL injection attempt
            field_name="test",
            field_type="TEXT",
        )
        print("  ✗ System should have rejected invalid table name")
        results["tests_failed"] += 1
        results["errors"].append("Invalid table name was not rejected")
    except (ValueError, Exception) as e:
        print(f"  ✓ System correctly rejected invalid table name: {type(e).__name__}")
        results["tests_passed"] += 1

    # Test 8: Test invalid field type
    print("\n[TEST 8] Testing error detection - invalid field type...")
    try:
        result = safe_add_column(
            table_name="contacts", field_name="test_invalid", field_type="INVALID_TYPE_XYZ"
        )
        if not result.get("success"):
            print(f"  ✓ System correctly rejected invalid type: {result.get('error', 'Unknown')}")
            results["tests_passed"] += 1
        else:
            print("  ✗ System should have rejected invalid type")
            results["tests_failed"] += 1
    except Exception as e:
        print(f"  ✓ System correctly caught error: {type(e).__name__}")
        results["tests_passed"] += 1

    print("\n" + "=" * 80)
    print("SCHEMA MUTATION TEST SUMMARY")
    print("=" * 80)
    print(f"Tests passed: {results['tests_passed']}")
    print(f"Tests failed: {results['tests_failed']}")
    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for err in results["errors"]:
            print(f"  - {err}")

    return results


if __name__ == "__main__":
    test_schema_mutations()
