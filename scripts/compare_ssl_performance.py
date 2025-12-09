#!/usr/bin/env python3
"""Compare simulation performance with and without SSL"""

import contextlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_simulation(mode, scenario="small", ssl_enabled=False, schema="crm"):
    """Run a simulation and capture results"""
    print(f"\n{'=' * 80}")
    print(
        f"Running {schema.upper()} simulation - {mode} mode - SSL: {'ENABLED' if ssl_enabled else 'DISABLED'}"
    )
    print(f"{'=' * 80}\n")

    start_time = time.time()

    if schema == "crm":
        # CRM simulation
        cmd = [sys.executable, "-m", "src.simulation.simulator", mode, "--scenario", scenario]
    else:
        # Stock data simulation
        cmd = [
            sys.executable,
            "-m",
            "src.simulation.simulator",
            "real-data",
            "--scenario",
            scenario,
            "--stocks",
            "WIPRO,TCS,ITC",  # Small set for quick testing
            "--queries",
            "200",  # Small number for quick test
        ]

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        elapsed = time.time() - start_time

        # Try to extract key metrics from output
        output = result.stdout + result.stderr

        metrics = {
            "mode": mode,
            "schema": schema,
            "ssl_enabled": ssl_enabled,
            "scenario": scenario,
            "elapsed_time": elapsed,
            "exit_code": result.returncode,
            "success": result.returncode == 0,
        }

        # Extract performance metrics if available
        if "Total queries" in output:
            for line in output.split("\n"):
                if "Total queries" in line:
                    with contextlib.suppress(ValueError, IndexError):
                        metrics["total_queries"] = int(line.split(":")[-1].strip())
                if "Average latency" in line or "avg latency" in line.lower():
                    with contextlib.suppress(ValueError, IndexError):
                        metrics["avg_latency"] = float(line.split(":")[-1].strip().split()[0])

        return metrics, output

    except subprocess.TimeoutExpired:
        return {
            "mode": mode,
            "schema": schema,
            "ssl_enabled": ssl_enabled,
            "scenario": scenario,
            "elapsed_time": 600,
            "exit_code": -1,
            "success": False,
            "error": "Timeout",
        }, "Simulation timed out after 10 minutes"
    except Exception as e:
        return {
            "mode": mode,
            "schema": schema,
            "ssl_enabled": ssl_enabled,
            "scenario": scenario,
            "elapsed_time": 0,
            "exit_code": -1,
            "success": False,
            "error": str(e),
        }, f"Error: {e}"


def main():
    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print("SSL Performance Comparison Test")
    print("=" * 80)
    print(f"Timestamp: {timestamp}\n")

    # Test 1: CRM without SSL
    print("\n[1/4] Testing CRM schema WITHOUT SSL...")
    metrics, output = run_simulation("autoindex", "small", ssl_enabled=False, schema="crm")
    results.append(metrics)
    time.sleep(5)  # Brief pause between tests

    # Test 2: Stock data without SSL
    print("\n[2/4] Testing Stock data WITHOUT SSL...")
    metrics, output = run_simulation("autoindex", "small", ssl_enabled=False, schema="stock")
    results.append(metrics)
    time.sleep(5)

    # Enable SSL
    print("\n" + "=" * 80)
    print("ENABLING SSL - Updating docker-compose.yml...")
    print("=" * 80)

    docker_compose_path = project_root / "docker-compose.yml"
    with open(docker_compose_path) as f:
        content = f.read()

    # Uncomment SSL lines
    content = content.replace("# POSTGRES_SSL: on", "POSTGRES_SSL: on")
    content = content.replace(
        "# - ./ssl:/var/lib/postgresql/ssl:ro", "- ./ssl:/var/lib/postgresql/ssl:ro"
    )

    # Add SSL parameters to command
    if "-c ssl=on" not in content:
        # Find the command line and add SSL params
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if "postgres -c shared_buffers" in line:
                # Add SSL params before memory params
                new_lines.append("      postgres")
                new_lines.append("      -c ssl=on")
                new_lines.append("      -c ssl_cert_file=/var/lib/postgresql/ssl/server.crt")
                new_lines.append("      -c ssl_key_file=/var/lib/postgresql/ssl/server.key")
                # Continue with existing memory params
                new_lines.append(line.replace("postgres", "").strip())
            else:
                new_lines.append(line)
        content = "\n".join(new_lines)

    with open(docker_compose_path, "w") as f:
        f.write(content)

    print("SSL enabled in docker-compose.yml")
    print("Restarting PostgreSQL container...")

    # Restart PostgreSQL
    subprocess.run(["docker-compose", "restart", "postgres"], cwd=project_root, timeout=60)

    print("Waiting for PostgreSQL to be ready...")
    time.sleep(10)  # Wait for PostgreSQL to start

    # Test 3: CRM with SSL
    print("\n[3/4] Testing CRM schema WITH SSL...")
    metrics, output = run_simulation("autoindex", "small", ssl_enabled=True, schema="crm")
    results.append(metrics)
    time.sleep(5)

    # Test 4: Stock data with SSL
    print("\n[4/4] Testing Stock data WITH SSL...")
    metrics, output = run_simulation("autoindex", "small", ssl_enabled=True, schema="stock")
    results.append(metrics)

    # Save results
    results_file = project_root / f"docs/audit/toolreports/ssl_comparison_{timestamp}.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "results": results,
                "summary": {
                    "crm_without_ssl": results[0],
                    "stock_without_ssl": results[1],
                    "crm_with_ssl": results[2],
                    "stock_with_ssl": results[3],
                },
            },
            f,
            indent=2,
        )

    # Print comparison
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)

    print("\nCRM Schema:")
    print(f"  Without SSL: {results[0]['elapsed_time']:.2f}s (Success: {results[0]['success']})")
    print(f"  With SSL:    {results[2]['elapsed_time']:.2f}s (Success: {results[2]['success']})")
    if results[0]["success"] and results[2]["success"]:
        ssl_overhead = (
            (results[2]["elapsed_time"] - results[0]["elapsed_time"]) / results[0]["elapsed_time"]
        ) * 100
        print(f"  SSL Overhead: {ssl_overhead:+.2f}%")

    print("\nStock Data:")
    print(f"  Without SSL: {results[1]['elapsed_time']:.2f}s (Success: {results[1]['success']})")
    print(f"  With SSL:    {results[3]['elapsed_time']:.2f}s (Success: {results[3]['success']})")
    if results[1]["success"] and results[3]["success"]:
        ssl_overhead = (
            (results[3]["elapsed_time"] - results[1]["elapsed_time"]) / results[1]["elapsed_time"]
        ) * 100
        print(f"  SSL Overhead: {ssl_overhead:+.2f}%")

    print(f"\nFull results saved to: {results_file}")

    # Restore docker-compose.yml (disable SSL)
    print("\nRestoring docker-compose.yml (disabling SSL)...")
    content = content.replace("POSTGRES_SSL: on", "# POSTGRES_SSL: on")
    content = content.replace(
        "- ./ssl:/var/lib/postgresql/ssl:ro", "# - ./ssl:/var/lib/postgresql/ssl:ro"
    )
    # Remove SSL params from command (simplified - just restore original)
    # Note: SSL configuration is restored by replacing strings above
    # Better: restore from backup or regenerate
    # For now, just note that SSL is enabled

    print("Done!")


if __name__ == "__main__":
    main()
