#!/usr/bin/env python3
"""Run small simulations on CRM and backtesting data, then analyze and improve"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_simulation(mode: str, scenario: str = "small", data_type: str = "crm", queries: int = None) -> dict:
    """Run a single simulation and capture results"""
    if data_type == "crm":
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "src.simulation.simulator",
            mode,
            "--scenario",
            scenario,
        ]
        description = f"{mode} - {scenario} (CRM)"
    else:
        # Backtesting data
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "src.simulation.simulator",
            "real-data",
            "--data-dir",
            "data/backtesting",
        ]
        if queries:
            cmd.extend(["--queries", str(queries)])
        description = f"real-data - {scenario} equivalent ({queries} queries) - Backtesting"

    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*80}\n")

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes max
        )

        duration = time.time() - start_time
        success = result.returncode == 0

        print(f"\n{'='*80}")
        print(f"Completed: {description}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Success: {success}")
        print(f"{'='*80}\n")

        # Extract key metrics from output
        metrics = {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "duration_seconds": duration,
            "success": success,
            "returncode": result.returncode,
            "timestamp": datetime.now().isoformat(),
        }

        # Try to extract performance metrics from output
        output = result.stdout + result.stderr
        if "Total queries" in output:
            for line in output.split("\n"):
                if "Total queries" in line:
                    try:
                        metrics["total_queries"] = int(
                            line.split("Total queries")[1].split()[0]
                        )
                    except (ValueError, IndexError):
                        pass
                if "Average query time" in line or "avg query time" in line.lower():
                    try:
                        metrics["avg_query_time_ms"] = float(
                            line.split(":")[1].split()[0]
                        )
                    except (ValueError, IndexError):
                        pass
                if "Indexes created" in line or "indexes created" in line.lower():
                    try:
                        metrics["indexes_created"] = int(
                            line.split(":")[1].split()[0]
                        )
                    except (ValueError, IndexError):
                        pass

        if not success:
            metrics["error"] = result.stderr[:500]  # First 500 chars of error

        return metrics

    except subprocess.TimeoutExpired:
        print(f"\n{'='*80}")
        print(f"TIMEOUT: {description}")
        print(f"{'='*80}\n")
        return {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "duration_seconds": 1800,
            "success": False,
            "error": "Timeout after 30 minutes",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"ERROR: {description}")
        print(f"Exception: {e}")
        print(f"{'='*80}\n")
        return {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "duration_seconds": time.time() - start_time,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def analyze_results(results: dict) -> dict:
    """Analyze simulation results and identify improvement opportunities"""
    analysis = {
        "total_simulations": len(results),
        "successful": sum(1 for r in results.values() if r.get("success")),
        "failed": sum(1 for r in results.values() if not r.get("success")),
        "improvements": [],
        "recommendations": [],
    }

    # Group by mode
    by_mode = {}
    for key, result in results.items():
        mode = result.get("mode", "unknown")
        if mode not in by_mode:
            by_mode[mode] = []
        by_mode[mode].append(result)

    # Analyze performance
    avg_durations = {}
    for mode, mode_results in by_mode.items():
        durations = [r.get("duration_seconds", 0) for r in mode_results if r.get("success")]
        if durations:
            avg_durations[mode] = sum(durations) / len(durations)

    # Identify improvements
    if analysis["failed"] > 0:
        analysis["improvements"].append(
            {
                "type": "reliability",
                "issue": f"{analysis['failed']} simulations failed",
                "priority": "high",
                "suggestion": "Review error logs and fix underlying issues",
            }
        )

    # Compare modes
    if "baseline" in avg_durations and "autoindex" in avg_durations:
        improvement = (
            (avg_durations["baseline"] - avg_durations["autoindex"])
            / avg_durations["baseline"]
            * 100
        )
        if improvement > 0:
            analysis["improvements"].append(
                {
                    "type": "performance",
                    "issue": "Auto-indexing shows performance improvement",
                    "priority": "medium",
                    "suggestion": f"Auto-indexing is {improvement:.1f}% faster than baseline",
                }
            )

    return analysis


def main():
    """Run small simulations and analyze results"""
    print("=" * 80)
    print("IndexPilot - Small Simulations (CRM + Backtesting)")
    print("=" * 80)

    results = {}
    results_dir = project_root / "docs" / "audit" / "toolreports"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: CRM Data Simulations (small scenario)
    print("\n" + "=" * 80)
    print("PHASE 1: CRM Data Simulations (small)")
    print("=" * 80)

    crm_modes = ["baseline", "autoindex", "scaled", "comprehensive"]
    for mode in crm_modes:
        key = f"crm_{mode}_small"
        print(f"\n[{len(results) + 1}/8] Running {key}...")
        results[key] = run_simulation(mode, scenario="small", data_type="crm")
        time.sleep(2)  # Brief pause between simulations

    # Phase 2: Backtesting Data Simulations (small equivalent)
    print("\n" + "=" * 80)
    print("PHASE 2: Backtesting Data Simulations (small equivalent)")
    print("=" * 80)

    # Small equivalent: 10 tenants × 200 queries = 2000 queries
    key = "backtesting_realdat_small"
    print(f"\n[{len(results) + 1}/8] Running {key}...")
    results[key] = run_simulation("real-data", scenario="small", data_type="backtesting", queries=2000)
    time.sleep(2)

    # Save results
    results_file = results_dir / f"small_sim_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    # Analyze results
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    analysis = analyze_results(results)
    print(f"\nTotal simulations: {analysis['total_simulations']}")
    print(f"Successful: {analysis['successful']}")
    print(f"Failed: {analysis['failed']}")

    if analysis["improvements"]:
        print("\nImprovement Opportunities:")
        for imp in analysis["improvements"]:
            print(f"  [{imp['priority'].upper()}] {imp['type']}: {imp['issue']}")
            print(f"    → {imp['suggestion']}")

    # Save analysis
    analysis_file = results_dir / f"small_sim_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"\nAnalysis saved to: {analysis_file}")

    return results, analysis


if __name__ == "__main__":
    main()

