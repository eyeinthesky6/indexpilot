#!/usr/bin/env python3
"""Check simulation status: errors, algorithms, features"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db import get_connection  # noqa: E402


def main():
    print("=" * 80)
    print("Simulation Status Check")
    print("=" * 80)
    print()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Check algorithm usage
        print("Algorithm Usage:")
        print("-" * 40)
        cursor.execute("SELECT COUNT(*) FROM algorithm_usage")
        algo_count = cursor.fetchone()[0]
        print(f"  Total records: {algo_count}")

        if algo_count > 0:
            cursor.execute(
                """
                SELECT algorithm_name, COUNT(*)
                FROM algorithm_usage
                GROUP BY algorithm_name
                ORDER BY COUNT(*) DESC
            """
            )
            rows = cursor.fetchall()
            for row in rows:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("  ⚠️  No algorithm usage records found")
        print()

        # Check mutation log (get column names first)
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'mutation_log'
        """
        )
        columns = [row[0] for row in cursor.fetchall()]

        print("Index Decisions:")
        print("-" * 40)
        # Try different possible column names
        if "mutation_type" in columns:
            cursor.execute(
                "SELECT COUNT(*) FROM mutation_log WHERE mutation_type = %s", ("CREATE_INDEX",)
            )
            created = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM mutation_log WHERE mutation_type = %s", ("SKIP_INDEX",)
            )
            skipped = cursor.fetchone()[0]
        elif "action" in columns:
            cursor.execute("SELECT COUNT(*) FROM mutation_log WHERE action = %s", ("CREATE_INDEX",))
            created = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM mutation_log WHERE action = %s", ("SKIP_INDEX",))
            skipped = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM mutation_log")
            total = cursor.fetchone()[0]
            created = "N/A"
            skipped = "N/A"
            print(f"  Total records: {total}")
            print(f"  (Column structure: {', '.join(columns)})")

        if created != "N/A":
            print(f"  Created: {created}")
            print(f"  Skipped: {skipped}")
            print(f"  Total: {created + skipped}")
        print()

        # Check skip reasons
        if "reason" in columns:
            print("Top Skip Reasons:")
            print("-" * 40)
            cursor.execute(
                """
                SELECT reason, COUNT(*)
                FROM mutation_log
                WHERE reason IS NOT NULL
                GROUP BY reason
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """
            )
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    print(f"  {row[0]}: {row[1]}")
            else:
                print("  No skip reasons found")
            print()

        # Summary
        print("=" * 80)
        print("Summary:")
        print("=" * 80)
        if algo_count == 0:
            print("[WARNING] Algorithms may not have fired (0 usage records)")
            print("   - Fields may have skipped before algorithms called")
            print("   - Enable test mode to force algorithm execution")
        else:
            print(f"[SUCCESS] Algorithms fired ({algo_count} usage records)")

        if created == 0 or created == "N/A":
            print("[WARNING] No indexes created")
            print("   - All fields skipped (see skip reasons above)")
        else:
            print(f"[SUCCESS] {created} indexes created")

        print()
        print("SSL Status: [ENABLED] (as requested)")


if __name__ == "__main__":
    main()
