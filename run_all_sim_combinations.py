"""Run all simulation combinations one at a time with monitoring
   - CRM data: baseline, autoindex, scaled, comprehensive modes with small and medium scenarios
   - Backtesting data: real-data mode with small and medium equivalent query counts
   
   Runs sequentially, saves progress after each, and creates comparison table with previous runs
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def load_previous_results() -> dict:
    """Load previous simulation results for comparison"""
    previous_results = {}

    # Check for previous comprehensive results
    results_dir = Path("docs/audit/toolreports")

    # Load comprehensive results
    comprehensive_file = results_dir / "results_comprehensive.json"
    if comprehensive_file.exists():
        try:
            with open(comprehensive_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    previous_results["comprehensive"] = data
        except Exception as e:
            print(f"WARNING: Could not load comprehensive results: {e}")

    # Load baseline results
    baseline_file = results_dir / "results_baseline.json"
    if baseline_file.exists():
        try:
            with open(baseline_file) as f:
                data = json.load(f)
                previous_results["baseline"] = data
        except Exception:
            pass

    # Load autoindex results
    autoindex_file = results_dir / "results_with_auto_index.json"
    if autoindex_file.exists():
        try:
            with open(autoindex_file) as f:
                data = json.load(f)
                previous_results["autoindex"] = data
        except Exception:
            pass

    # Load real-data results
    realdata_file = results_dir / "results_real_data.json"
    if realdata_file.exists():
        try:
            with open(realdata_file) as f:
                data = json.load(f)
                previous_results["real-data"] = data
        except Exception:
            pass

    # Load previous summary files
    for summary_file in results_dir.glob("simulation_*.json"):
        try:
            with open(summary_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    previous_results[summary_file.stem] = data
        except Exception:
            pass

    return previous_results


def extract_metrics_from_output(output: str) -> dict:
    """Extract key metrics from simulation output"""
    metrics = {}
    lines = output.splitlines()

    for line in lines:
        if "Avg:" in line and "P95:" in line and "P99:" in line:
            metrics["latency_metrics"] = line.strip()
        if "Total queries:" in line or "queries completed" in line.lower():
            metrics["query_count"] = line.strip()
        if "indexes created" in line.lower():
            metrics["indexes_created"] = line.strip()
        if "improvement" in line.lower() and "%" in line:
            metrics["improvement"] = line.strip()
        if "Performance Change:" in line or "improvement" in line.lower():
            # Try to extract percentage
            import re
            match = re.search(r'([+-]?\d+\.?\d*)\s*%', line)
            if match:
                metrics["improvement_pct"] = float(match.group(1))

    return metrics


def run_simulation(
    mode: str,
    scenario: str = None,
    data_type: str = "crm",
    queries: int = None,
    progress_file: Path = None
) -> dict:
    """Run a single simulation with real-time output"""
    if data_type == "crm":
        # CRM data simulations
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "src.simulation.simulator",
            mode,
        ]
        if scenario:
            cmd.extend(["--scenario", scenario])
        description = f"{mode} - {scenario} (CRM)"
    else:
        # Backtesting data simulations
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

    log_file = Path(f"logs/sim_{mode}_{scenario or 'realdat'}_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_file.parent.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}")
    print(f"Log file: {log_file}")
    print(f"{'='*80}\n")

    start_time = datetime.now()

    try:
        # Run with real-time output (not captured)
        with open(log_file, "w", encoding="utf-8") as log_f:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                timeout=36000,  # 10 hours timeout
            )

            # Write to both log file and console in real-time
            output_lines = result.stdout.splitlines()
            for line in output_lines:
                print(line)
                log_f.write(line + "\n")
                log_f.flush()
                sys.stdout.flush()

            log_f.write(f"\n\nReturn code: {result.returncode}\n")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Extract metrics
        metrics = extract_metrics_from_output(result.stdout)

        summary = {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "queries": queries,
            "description": description,
            "return_code": result.returncode,
            "success": result.returncode == 0,
            "log_file": str(log_file),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "stdout_lines": len(result.stdout.splitlines()),
            **metrics,
        }

        # Try to load results from JSON files
        results_dir = Path("docs/audit/toolreports")
        if mode == "comprehensive":
            results_file = results_dir / "results_comprehensive.json"
        elif mode == "baseline":
            results_file = results_dir / "results_baseline.json"
        elif mode == "autoindex":
            results_file = results_dir / "results_with_auto_index.json"
        elif mode == "real-data":
            results_file = results_dir / "results_real_data.json"
        else:
            results_file = None

        if results_file and results_file.exists():
            try:
                with open(results_file) as f:
                    results_data = json.load(f)
                    summary["results_data"] = results_data
            except Exception as e:
                summary["results_load_error"] = str(e)

        # Save progress immediately
        if progress_file:
            save_progress(progress_file, summary)

        status = "SUCCESS" if result.returncode == 0 else "FAILED"
        print(f"\n{'='*80}")
        print(f"Completed: {description}")
        print(f"Status: {status}")
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        if "improvement_pct" in summary:
            print(f"Improvement: {summary['improvement_pct']:.1f}%")
        print(f"{'='*80}\n")

        return summary

    except subprocess.TimeoutExpired:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\nWARNING: Simulation timed out after {duration:.1f} seconds: {description}")
        summary = {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "success": False,
            "error": "timeout",
            "log_file": str(log_file),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
        }
        if progress_file:
            save_progress(progress_file, summary)
        return summary
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\nERROR: Error running simulation: {description} - {e}")
        summary = {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "success": False,
            "error": str(e),
            "log_file": str(log_file),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
        }
        if progress_file:
            save_progress(progress_file, summary)
        return summary


def save_progress(progress_file: Path, new_result: dict):
    """Save progress incrementally"""
    # Load existing progress
    if progress_file.exists():
        try:
            with open(progress_file) as f:
                progress = json.load(f)
        except Exception:
            progress = {}
    else:
        progress = {}

    # Add new result
    key = f"{new_result['data_type']}_{new_result['mode']}_{new_result.get('scenario', 'realdat')}"
    progress[key] = new_result

    # Save
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2, default=str)


def create_comparison_table(current_results: dict, previous_results: dict) -> str:
    """Create a comparison table between current and previous runs"""
    table_lines = []
    table_lines.append("\n" + "=" * 100)
    table_lines.append("SIMULATION RESULTS COMPARISON")
    table_lines.append("=" * 100)
    table_lines.append("")
    table_lines.append(f"{'Test':<40} {'Status':<12} {'Duration':<12} {'Improvement':<15} {'Notes':<20}")
    table_lines.append("-" * 100)

    for key, result in sorted(current_results.items()):
        status = "PASS" if result.get("success") else "FAIL"
        duration = f"{result.get('duration_seconds', 0):.1f}s"
        improvement = ""
        if "improvement_pct" in result:
            improvement = f"{result['improvement_pct']:.1f}%"
        elif "improvement" in result:
            improvement = result["improvement"][:14]

        notes = ""
        if "error" in result:
            notes = f"Error: {result['error'][:18]}"

        # Check if we have previous results to compare
        prev_key = None
        for prev_k in previous_results:
            if key in prev_k or prev_k in key:
                prev_key = prev_k
                break

        if prev_key and prev_key in previous_results:
            prev = previous_results[prev_key]
            if isinstance(prev, dict):
                if "improvement_pct" in prev:
                    prev_imp = prev["improvement_pct"]
                    if "improvement_pct" in result:
                        diff = result["improvement_pct"] - prev_imp
                        notes = f"Δ {diff:+.1f}% vs prev"

        table_lines.append(f"{key:<40} {status:<12} {duration:<12} {improvement:<15} {notes:<20}")

    table_lines.append("=" * 100)
    return "\n".join(table_lines)


def main():
    """Run all simulation combinations one at a time"""
    print("=" * 80)
    print("IndexPilot - All Simulation Combinations (Sequential)")
    print("Excluding: large and stress-test scenarios")
    print("=" * 80)

    # Load previous results for comparison
    print("\nLoading previous results for comparison...")
    previous_results = load_previous_results()
    print(f"Loaded {len(previous_results)} previous result sets")

    # Progress file
    progress_file = Path(
        f"docs/audit/toolreports/simulation_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    results = {}

    # CRM data simulations
    crm_modes = ["baseline", "autoindex", "scaled", "comprehensive"]
    crm_scenarios = ["small", "medium"]

    print("\n" + "=" * 80)
    print("PHASE 1: CRM Data Simulations")
    print("=" * 80)
    print(f"Total: {len(crm_modes) * len(crm_scenarios)} simulations")

    sim_count = 0
    for scenario in crm_scenarios:
        for mode in crm_modes:
            sim_count += 1
            print(f"\n[{sim_count}/{len(crm_modes) * len(crm_scenarios)}] ", end="")
            key = f"crm_{mode}_{scenario}"
            results[key] = run_simulation(mode, scenario, data_type="crm", progress_file=progress_file)

    # Backtesting data simulations
    # Small equivalent: 10 tenants × 200 queries = 2000 queries
    # Medium equivalent: 50 tenants × 500 queries = 25000 queries
    backtesting_configs = [
        ("small", 2000),
        ("medium", 25000),
    ]

    print("\n" + "=" * 80)
    print("PHASE 2: Backtesting Data Simulations")
    print("=" * 80)
    print(f"Total: {len(backtesting_configs)} simulations")

    for idx, (scenario, queries) in enumerate(backtesting_configs, 1):
        print(f"\n[{idx}/{len(backtesting_configs)}] ", end="")
        key = f"backtesting_realdat_{scenario}"
        results[key] = run_simulation("real-data", scenario, data_type="backtesting", queries=queries, progress_file=progress_file)

    # Final summary file
    summary_file = Path(
        f"docs/audit/toolreports/simulation_all_combinations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Create comparison table
    comparison_table = create_comparison_table(results, previous_results)
    print(comparison_table)

    # Save comparison table
    comparison_file = summary_file.with_suffix(".comparison.txt")
    with open(comparison_file, "w") as f:
        f.write(comparison_table)

    # Overall statistics
    total = len(results)
    successful = sum(1 for r in results.values() if r.get("success"))
    failed = total - successful

    print(f"\n{'='*80}")
    print(f"Overall: {successful}/{total} successful, {failed} failed")
    print(f"Full summary: {summary_file}")
    print(f"Comparison table: {comparison_file}")
    print(f"Progress log: {progress_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
