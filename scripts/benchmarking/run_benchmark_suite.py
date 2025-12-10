#!/usr/bin/env python3
"""
Run benchmark suite and auto-generate reports
Date: 08-12-2025
"""

import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print("=" * 60)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] {description} completed")
        if result.stdout:
            print(result.stdout[-500:])  # Last 500 chars
        return True
    else:
        print(f"[ERROR] {description} failed")
        if result.stderr:
            print(result.stderr[-500:])  # Last 500 chars
        return False


def main():
    """Run benchmark suite"""
    import argparse

    parser = argparse.ArgumentParser(description="Run benchmark suite and generate reports")
    parser.add_argument(
        "--scenario",
        default="small",
        choices=["small", "medium", "large"],
        help="Test scenario (default: small)",
    )
    parser.add_argument("--skip-baseline", action="store_true", help="Skip baseline test")
    parser.add_argument("--skip-autoindex", action="store_true", help="Skip autoindex test")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation")

    args = parser.parse_args()

    print("=" * 60)
    print("IndexPilot Benchmark Suite")
    print("=" * 60)
    print(f"Scenario: {args.scenario}")
    print(f"Working directory: {project_root}")

    results = []

    # Step 1: Baseline
    if not args.skip_baseline:
        cmd = f"python -m src.simulation.simulator baseline --scenario {args.scenario}"
        success = run_command(cmd, f"Baseline test ({args.scenario})")
        results.append(("Baseline", success))
    else:
        print("\n[Skipping] Baseline test")

    # Step 2: Autoindex
    if not args.skip_autoindex:
        cmd = f"python -m src.simulation.simulator autoindex --scenario {args.scenario}"
        success = run_command(cmd, f"Autoindex test ({args.scenario})")
        results.append(("Autoindex", success))
    else:
        print("\n[Skipping] Autoindex test")

    # Step 3: Generate report
    if not args.skip_report:
        cmd = "python -m src.scaled_reporting"
        success = run_command(cmd, "Performance report")
        results.append(("Report", success))

        # Step 4: Generate case study
        cmd = f'python scripts/benchmarking/generate_case_study.py --name "{args.scenario.capitalize()}_Scenario" --scenario {args.scenario}'
        success = run_command(cmd, "Case study generation")
        results.append(("Case Study", success))

        # Step 5: Update history tracking
        cmd = "python scripts/track_history.py"
        success = run_command(cmd, "History tracking update")
        results.append(("History Tracking", success))
    else:
        print("\n[Skipping] Report generation")

    # Summary
    print("\n" + "=" * 60)
    print("Benchmark Suite Summary")
    print("=" * 60)

    for name, success in results:
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {name}")

    all_passed = all(success for _, success in results)

    if all_passed:
        print("\n[SUCCESS] All benchmarks completed!")
        print("\nResults:")
        print("  - Baseline: docs/audit/toolreports/results_baseline.json")
        print("  - Autoindex: docs/audit/toolreports/results_with_auto_index.json")
        print(
            f"  - Case Study: docs/case_studies/CASE_STUDY_{args.scenario.capitalize()}_SCENARIO.md"
        )
        return 0
    else:
        print("\n[FAILED] Some benchmarks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
