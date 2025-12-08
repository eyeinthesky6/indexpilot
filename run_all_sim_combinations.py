"""Run all simulation combinations except large and stress-test
   - CRM data: baseline, autoindex, scaled, comprehensive modes with small and medium scenarios
   - Backtesting data: real-data mode with small and medium equivalent query counts
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_simulation(mode: str, scenario: str = None, data_type: str = "crm", queries: int = None) -> dict:
    """Run a simulation and capture output"""
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
    
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"{'='*80}\n")
    print(f"Command: {' '.join(cmd)}\n")
    
    log_file = Path(f"logs/sim_{mode}_{scenario or 'realdat'}_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_file.parent.mkdir(exist_ok=True)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=36000,  # 10 hours timeout
        )
        
        # Save full output
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"STDOUT:\n{result.stdout}\n\n")
            f.write(f"STDERR:\n{result.stderr}\n\n")
            f.write(f"Return code: {result.returncode}\n")
        
        summary = {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "queries": queries,
            "description": description,
            "return_code": result.returncode,
            "success": result.returncode == 0,
            "log_file": str(log_file),
            "stdout_lines": len(result.stdout.splitlines()),
            "stderr_lines": len(result.stderr.splitlines()),
        }
        
        # Extract key metrics from output
        output_lines = result.stdout.splitlines()
        for line in output_lines:
            if "Avg:" in line and "P95:" in line and "P99:" in line:
                summary["latency_metrics"] = line.strip()
            if "Total queries:" in line or "queries completed" in line.lower():
                summary["query_count"] = line.strip()
            if "indexes created" in line.lower():
                summary["indexes_created"] = line.strip()
            if "improvement" in line.lower() and "%" in line:
                summary["improvement"] = line.strip()
        
        return summary
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  Simulation timed out: {description}")
        return {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "success": False,
            "error": "timeout",
            "log_file": str(log_file),
        }
    except Exception as e:
        print(f"❌ Error running simulation: {description} - {e}")
        return {
            "mode": mode,
            "scenario": scenario,
            "data_type": data_type,
            "description": description,
            "success": False,
            "error": str(e),
            "log_file": str(log_file),
        }


def main():
    """Run all simulation combinations"""
    print("=" * 80)
    print("IndexPilot - All Simulation Combinations")
    print("Excluding: large and stress-test scenarios")
    print("=" * 80)
    
    results = {}
    
    # CRM data simulations
    crm_modes = ["baseline", "autoindex", "scaled", "comprehensive"]
    crm_scenarios = ["small", "medium"]
    
    print("\n" + "=" * 80)
    print("PHASE 1: CRM Data Simulations")
    print("=" * 80)
    
    for scenario in crm_scenarios:
        for mode in crm_modes:
            key = f"crm_{mode}_{scenario}"
            results[key] = run_simulation(mode, scenario, data_type="crm")
    
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
    
    for scenario, queries in backtesting_configs:
        key = f"backtesting_realdat_{scenario}"
        results[key] = run_simulation("real-data", scenario, data_type="backtesting", queries=queries)
    
    # Create summary report
    summary_file = Path(
        f"docs/audit/toolreports/simulation_all_combinations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SIMULATION SUMMARY")
    print("=" * 80)
    
    # CRM results
    print("\n📊 CRM Data Simulations:")
    for scenario in crm_scenarios:
        print(f"\n  {scenario.upper()} Scenario:")
        for mode in crm_modes:
            key = f"crm_{mode}_{scenario}"
            result = results.get(key, {})
            status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
            print(f"    {mode:15s}: {status}")
            if "error" in result:
                print(f"      Error: {result['error']}")
            if "latency_metrics" in result:
                print(f"      Latency: {result['latency_metrics']}")
    
    # Backtesting results
    print("\n📈 Backtesting Data Simulations:")
    for scenario, queries in backtesting_configs:
        key = f"backtesting_realdat_{scenario}"
        result = results.get(key, {})
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        print(f"  {scenario.upper()} equivalent ({queries} queries): {status}")
        if "error" in result:
            print(f"    Error: {result['error']}")
        if "latency_metrics" in result:
            print(f"    Latency: {result['latency_metrics']}")
    
    # Overall statistics
    total = len(results)
    successful = sum(1 for r in results.values() if r.get("success"))
    failed = total - successful
    
    print(f"\n{'='*80}")
    print(f"Overall: {successful}/{total} successful, {failed} failed")
    print(f"📄 Full summary saved to: {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

