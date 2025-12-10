#!/usr/bin/env python3
"""
Track benchmark history over time.
Reads latest result JSONs and appends to history CSV and Markdown dashboard.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "docs" / "audit" / "toolreports"
HISTORY_FILE = PROJECT_ROOT / "docs" / "audit" / "benchmark_history.csv"
DASHBOARD_FILE = PROJECT_ROOT / "docs" / "audit" / "BENCHMARK_DASHBOARD.md"

def load_json(filename):
    path = REPORTS_DIR / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def update_history():
    print("Updating benchmark history...")

    # Load latest results
    baseline = load_json("results_baseline.json")
    autoindex = load_json("results_with_auto_index.json")
    real_data = load_json("results_real_data.json")

    entries = []
    timestamp = datetime.now().isoformat()

    # Process CRM simulation (Baseline vs Autoindex)
    if baseline and autoindex:
        scenario = "CRM_Simulation"
        # Determine size from config if available or infer
        size = "Unknown"
        if "num_tenants" in baseline:
            if baseline["num_tenants"] == 10:
                size = "Small"
            elif baseline["num_tenants"] == 50:
                size = "Medium"
            elif baseline["num_tenants"] == 100:
                size = "Large"

        baseline_avg = baseline.get("overall_avg_ms", 0)
        autoindex_avg = autoindex.get("overall_avg_ms", 0)
        baseline_p99 = baseline.get("overall_p99_ms", 0)
        autoindex_p99 = autoindex.get("overall_p99_ms", 0)

        improvement_pct = 0
        if baseline_avg > 0:
            improvement_pct = ((baseline_avg - autoindex_avg) / baseline_avg) * 100

        entries.append({
            "timestamp": timestamp,
            "scenario": f"{scenario}_{size}",
            "baseline_avg_ms": f"{baseline_avg:.2f}",
            "autoindex_avg_ms": f"{autoindex_avg:.2f}",
            "improvement_pct": f"{improvement_pct:.2f}",
            "baseline_p99_ms": f"{baseline_p99:.2f}",
            "autoindex_p99_ms": f"{autoindex_p99:.2f}"
        })

    # Process Real Data (Stock)
    if real_data:
        scenario = "Stock_Market"
        baseline_avg = real_data.get("baseline", {}).get("avg_duration_ms", 0)
        autoindex_avg = real_data.get("autoindex", {}).get("avg_duration_ms", 0)
        improvement_pct = real_data.get("improvement_pct", 0)

        entries.append({
            "timestamp": timestamp,
            "scenario": scenario,
            "baseline_avg_ms": f"{baseline_avg:.2f}",
            "autoindex_avg_ms": f"{autoindex_avg:.2f}",
            "improvement_pct": f"{improvement_pct:.2f}",
            "baseline_p99_ms": "N/A", # Real data output might simpler
            "autoindex_p99_ms": "N/A"
        })

    if not entries:
        print("No recent result files found to track.")
        return

    # Ensure directory exists
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Check if CSV exists to write header
    file_exists = HISTORY_FILE.exists()

    with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        fieldnames = ["timestamp", "scenario", "baseline_avg_ms", "autoindex_avg_ms", "improvement_pct", "baseline_p99_ms", "autoindex_p99_ms"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for entry in entries:
            writer.writerow(entry)
            print(f"Added entry for {entry['scenario']}")

    # Update Dashboard
    update_dashboard()

def update_dashboard():
    print("Updating dashboard...")
    if not HISTORY_FILE.exists():
        return

    rows = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Reverse to show newest first
    rows.reverse()

    md_content = f"""# IndexPilot Benchmark Dashboard
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Recent Runs

| Timestamp | Scenario | Baseline Avg (ms) | AutoIndex Avg (ms) | Improvement % | Baseline P99 (ms) | AutoIndex P99 (ms) |
|-----------|----------|-------------------|--------------------|---------------|-------------------|--------------------|
"""

    for row in rows[:20]: # Show last 20 runs
        # Add emoji for improvement
        imp = float(row["improvement_pct"])
        emoji = "🟢" if imp > 10 else "🟡" if imp > 0 else "🔴"

        md_content += f"| {row['timestamp'][:19]} | {row['scenario']} | {row['baseline_avg_ms']} | {row['autoindex_avg_ms']} | {emoji} {row['improvement_pct']}% | {row['baseline_p99_ms']} | {row['autoindex_p99_ms']} |\n"

    md_content += "\n## Trends\n\n(Visualization placeholders could go here)\n"

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Dashboard updated at {DASHBOARD_FILE}")

if __name__ == "__main__":
    update_history()

