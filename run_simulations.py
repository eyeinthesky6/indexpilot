"""Run small and medium simulations and capture results summary"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_simulation(scenario: str) -> dict:
    """Run simulation and capture output"""
    print(f"\n{'='*80}")
    print(f"Running {scenario.upper()} scenario simulation...")
    print(f"{'='*80}\n")
    
    log_file = Path(f"logs/sim_{scenario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_file.parent.mkdir(exist_ok=True)
    
    try:
        # Run simulation with timeout (10 hours = 36000 seconds for all scenarios)
        # Use venv python if available, otherwise use system python
        venv_python_windows = Path("venv/Scripts/python.exe")
        venv_python_unix = Path("venv/bin/python")
        if venv_python_windows.exists():
            python_exe = str(venv_python_windows)
        elif venv_python_unix.exists():
            python_exe = str(venv_python_unix)
        else:
            python_exe = sys.executable
        result = subprocess.run(
            [python_exe, "-u", "-m", "src.simulation.simulator", "comprehensive", "--scenario", scenario],
            capture_output=True,
            text=True,
            timeout=36000,  # 10 hours for all scenarios
        )
        
        # Save full output
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"STDOUT:\n{result.stdout}\n\n")
            f.write(f"STDERR:\n{result.stderr}\n\n")
            f.write(f"Return code: {result.returncode}\n")
        
        # Extract summary from output
        summary = {
            "scenario": scenario,
            "return_code": result.returncode,
            "success": result.returncode == 0,
            "log_file": str(log_file),
            "stdout_lines": len(result.stdout.splitlines()),
            "stderr_lines": len(result.stderr.splitlines()),
        }
        
        # Try to extract key metrics from output
        output_lines = result.stdout.splitlines()
        for i, line in enumerate(output_lines):
            if "Avg:" in line and "P95:" in line and "P99:" in line:
                summary["latency_metrics"] = line.strip()
            if "Total queries:" in line or "queries completed" in line.lower():
                summary["query_count"] = line.strip()
            if "indexes created" in line.lower():
                summary["indexes_created"] = line.strip()
            if "improvement" in line.lower() and "%" in line:
                summary["improvement"] = line.strip()
        
        # Check for results file
        results_file = Path(f"docs/audit/toolreports/results_comprehensive.json")
        if results_file.exists():
            try:
                with open(results_file, "r") as f:
                    results_data = json.load(f)
                    summary["results_file"] = str(results_file)
                    summary["has_results"] = True
                    if "baseline" in results_data:
                        summary["baseline_metrics"] = results_data.get("baseline", {})
                    if "autoindex" in results_data:
                        summary["autoindex_metrics"] = results_data.get("autoindex", {})
            except Exception as e:
                summary["results_error"] = str(e)
        
        return summary
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  Simulation timed out after timeout period")
        return {
            "scenario": scenario,
            "success": False,
            "error": "timeout",
            "log_file": str(log_file),
        }
    except Exception as e:
        print(f"❌ Error running simulation: {e}")
        return {
            "scenario": scenario,
            "success": False,
            "error": str(e),
            "log_file": str(log_file),
        }

def main():
    """Run both simulations and create summary"""
    print("="*80)
    print("IndexPilot Simulation Runner")
    print("Running Small and Medium Scenarios")
    print("="*80)
    
    results = {}
    
    # Run small simulation
    results["small"] = run_simulation("small")
    
    # Run medium simulation
    results["medium"] = run_simulation("medium")
    
    # Create summary report
    summary_file = Path(f"docs/audit/toolreports/simulation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*80)
    print("SIMULATION SUMMARY")
    print("="*80)
    
    for scenario in ["small", "medium"]:
        result = results[scenario]
        print(f"\n{scenario.upper()} Scenario:")
        print(f"  Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        if "latency_metrics" in result:
            print(f"  Latency: {result['latency_metrics']}")
        if "query_count" in result:
            print(f"  Queries: {result['query_count']}")
        if "indexes_created" in result:
            print(f"  Indexes: {result['indexes_created']}")
        if "improvement" in result:
            print(f"  Improvement: {result['improvement']}")
        print(f"  Log: {result.get('log_file', 'N/A')}")
    
    print(f"\n📄 Full summary saved to: {summary_file}")
    print("="*80)

if __name__ == "__main__":
    main()

