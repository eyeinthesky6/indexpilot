#!/usr/bin/env python
"""Validate simulation results from comprehensive test runs"""

import json
import sys
from pathlib import Path

from src.type_definitions import JSONValue


def validate_result_file(filepath: str) -> dict[str, JSONValue]:
    """
    Validate a single result JSON file.

    Returns:
        dict with validation status, errors, and metrics
    """
    try:
        with open(filepath) as f:
            data = json.load(f)

        errors = []
        warnings = []
        metrics = {}

        # Validate structure
        if not isinstance(data, dict):
            errors.append("Result is not a JSON object")
            return {"valid": False, "errors": errors, "warnings": warnings, "metrics": metrics}

        # Check required fields based on filename
        filename = Path(filepath).name
        if "baseline" in filename:
            required_fields = [
                "phase",
                "num_tenants",
                "queries_per_tenant",
                "total_queries",
                "overall_avg_ms",
                "overall_p95_ms",
                "overall_p99_ms",
            ]
        elif "auto_index" in filename:
            required_fields = [
                "phase",
                "num_tenants",
                "queries_per_tenant",
                "total_queries",
                "indexes_created",
                "overall_avg_ms",
                "overall_p95_ms",
                "overall_p99_ms",
            ]
        elif "comprehensive" in filename:
            required_fields = [
                "scenario",
                "num_tenants",
                "queries_per_tenant",
                "autoindex_results",
                "verification_results",
            ]
        else:
            required_fields = []

        if not isinstance(data, dict):
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "metrics": metrics,
            }

        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Extract and validate metrics
        if "overall_avg_ms" in data:
            avg = data["overall_avg_ms"]
            if not isinstance(avg, int | float) or avg < 0:
                errors.append(f"Invalid overall_avg_ms: {avg}")
            else:
                metrics["average_latency_ms"] = avg

        if "overall_p95_ms" in data:
            p95 = data["overall_p95_ms"]
            if not isinstance(p95, int | float) or p95 < 0:
                errors.append(f"Invalid overall_p95_ms: {p95}")
            else:
                metrics["p95_latency_ms"] = p95

        if "overall_p99_ms" in data:
            p99 = data["overall_p99_ms"]
            if not isinstance(p99, int | float) or p99 < 0:
                errors.append(f"Invalid overall_p99_ms: {p99}")
            else:
                metrics["p99_latency_ms"] = p99

        if "total_queries" in data:
            total = data["total_queries"]
            if not isinstance(total, int) or total <= 0:
                errors.append(f"Invalid total_queries: {total}")
            else:
                metrics["total_queries"] = total

        if "indexes_created" in data:
            indexes = data["indexes_created"]
            if not isinstance(indexes, int) or indexes < 0:
                errors.append(f"Invalid indexes_created: {indexes}")
            else:
                metrics["indexes_created"] = indexes

        # Check verification results if present
        if isinstance(data, dict) and "verification_results" in data:
            verif = data["verification_results"]
            if isinstance(verif, dict):
                summary = verif.get("summary")
                if isinstance(summary, dict):
                    all_passed = summary.get("all_passed")
                    if all_passed is False:
                        warnings.append("Feature verification did not pass all checks")
                    metrics["verification_passed"] = (
                        bool(all_passed) if all_passed is not None else False
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "metrics": metrics,
        }

    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [f"JSON decode error: {str(e)}"],
            "warnings": [],
            "metrics": {},
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Unexpected error: {str(e)}"],
            "warnings": [],
            "metrics": {},
        }


def main():
    """Validate all result files"""
    results_dir = Path("docs/audit/toolreports")

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return 1

    result_files = sorted(results_dir.glob("results_*.json"))

    if not result_files:
        print("No result files found")
        return 1

    print("=" * 80)
    print("SIMULATION RESULTS VALIDATION")
    print("=" * 80)

    all_valid = True
    summary = {}

    for filepath in result_files:
        print(f"\n[{filepath.name}]")
        validation = validate_result_file(str(filepath))

        if not validation["valid"]:
            all_valid = False
            print("  Status: FAILED")
            for error in validation["errors"]:
                print(f"    ✗ {error}")
        else:
            print("  Status: PASSED")

        for warning in validation["warnings"]:
            print(f"    ⚠ {warning}")

        if validation["metrics"]:
            print("  Metrics:")
            for key, value in validation["metrics"].items():
                if isinstance(value, float):
                    print(f"    - {key}: {value:.2f}")
                else:
                    print(f"    - {key}: {value}")

        summary[filepath.name] = validation

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(summary)
    passed = sum(1 for v in summary.values() if v["valid"])
    failed = total - passed

    print(f"Total test files: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if all_valid:
        print("\n[SUCCESS] All simulations passed validation!")
        return 0
    else:
        print("\n[FAILURE] Some simulations failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
