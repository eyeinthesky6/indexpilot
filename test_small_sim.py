"""Quick test to verify simulator can load and run small scenario"""
import sys
import subprocess
from pathlib import Path

# Use venv python if available, otherwise use system python
venv_python_windows = Path("venv/Scripts/python.exe")
venv_python_unix = Path("venv/bin/python")
if venv_python_windows.exists():
    python_exe = str(venv_python_windows)
elif venv_python_unix.exists():
    python_exe = str(venv_python_unix)
else:
    python_exe = sys.executable

print("Testing simulator with Python 3.13...")
print(f"Python: {python_exe}")

try:
    # Test imports
    print("\n1. Testing imports...")
    result = subprocess.run(
        [python_exe, "-c", "import sys; sys.path.insert(0, '.'); from src.simulation.simulator import SCENARIOS; print('✓ Simulator module loads successfully'); print(f'Small scenario: {SCENARIOS[\"small\"]}')"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    if result.returncode != 0:
        print(f"❌ Import test failed with code {result.returncode}")
        sys.exit(1)
    
    # Run small simulation
    print("\n2. Running small simulation...")
    result = subprocess.run(
        [python_exe, "-u", "-m", "src.simulation.simulator", "comprehensive", "--scenario", "small"],
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes for small
    )
    
    print("\n=== STDOUT ===")
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    
    if result.stderr:
        print("\n=== STDERR ===")
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    
    print(f"\n=== Return Code: {result.returncode} ===")
    
    if result.returncode == 0:
        print("✅ Simulation completed successfully!")
    else:
        print("❌ Simulation failed!")
        # Check for common errors
        output = result.stdout + result.stderr
        if "Traceback" in output or "Error" in output or "Exception" in output:
            print("\nErrors found in output above.")
        sys.exit(1)
        
except subprocess.TimeoutExpired:
    print("❌ Simulation timed out")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

