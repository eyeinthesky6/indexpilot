# Workspace-Level Unicode/UTF-8 Encoding Solution

**Date**: 09-12-2025  
**Purpose**: Fix Unicode encoding at workspace level so Unicode characters and emojis work throughout the application without file-level changes

---

## Overview

This solution sets UTF-8 encoding at multiple workspace levels to ensure Unicode characters (✓, ❌, ✅, emojis, etc.) work correctly throughout the application without requiring file-level encoding fixes.

---

## Solution Components

### 1. Python Site Customization (`sitecustomize.py`)

**Location**: Project root (will be installed to venv)

This file is automatically imported by Python on startup and:
- Sets UTF-8 encoding for stdin, stdout, stderr
- Configures environment variables for subprocess calls
- Works globally for all Python processes

**Installation**:
```bash
python scripts/install_unicode_support.py
```

Or manually copy `sitecustomize.py` to:
- **Windows venv**: `venv/Lib/site-packages/sitecustomize.py`
- **Unix venv**: `venv/lib/python3.x/site-packages/sitecustomize.py`

### 2. Workspace Settings (`.vscode/settings.json`)

Already configured with:
- `PYTHONIOENCODING=utf-8`
- `PYTHONUTF8=1`
- Terminal profiles configured for UTF-8

### 3. Makefile Environment Variables

Updated to export encoding variables:
```makefile
export PYTHONIOENCODING := utf-8
export PYTHONUTF8 := 1
```

All `make` commands now automatically use UTF-8 encoding.

### 4. Pytest Configuration (`pytest.ini`)

Updated to set encoding environment variables:
```ini
env = 
    PYTHONIOENCODING=utf-8
    PYTHONUTF8=1
```

All pytest runs now use UTF-8 encoding.

### 5. Batch Scripts

Already configured:
- `run.bat` - Sets UTF-8 encoding
- `run-simulation.bat` - Sets UTF-8 encoding

---

## Installation Steps

### Step 1: Install sitecustomize.py

Run the installation script:
```bash
python scripts/install_unicode_support.py
```

This copies `sitecustomize.py` to your virtual environment's site-packages directory.

### Step 2: Verify Installation

Test that UTF-8 encoding is working:
```python
import sys
print(f"stdout encoding: {sys.stdout.encoding}")
print(f"default encoding: {sys.getdefaultencoding()}")
print("Test: 你好世界 🌍 ✓ ❌ ✅")
# Should output: utf-8 for both and display Unicode correctly
```

### Step 3: Restart Terminal

Close and reopen your terminal in Cursor to ensure environment variables are loaded.

---

## How It Works

### Layer 1: Python Site Customization
- `sitecustomize.py` is automatically imported by Python
- Sets encoding for all Python processes
- Works for both direct execution and subprocess calls

### Layer 2: Environment Variables
- Set in `.vscode/settings.json` for Cursor terminals
- Exported in `Makefile` for make commands
- Set in `pytest.ini` for pytest runs
- Set in batch scripts for Windows commands

### Layer 3: Terminal Configuration
- Git Bash profile configured with UTF-8
- Command Prompt profile sets code page 65001 (UTF-8)
- PowerShell profile sets UTF-8 encoding

---

## Benefits

✅ **No file-level changes needed** - Encoding is set at workspace level  
✅ **Works for all Python processes** - Direct execution, subprocess, pytest, etc.  
✅ **Unicode characters work everywhere** - ✓, ❌, ✅, emojis, international characters  
✅ **Consistent across all tools** - Make, pytest, batch scripts, IDE terminals  
✅ **Automatic** - Once installed, works for all future Python processes  

---

## Troubleshooting

### Encoding Still Not Working

1. **Verify sitecustomize.py is installed**:
   ```bash
   ls venv/Lib/site-packages/sitecustomize.py  # Windows
   ls venv/lib/python*/site-packages/sitecustomize.py  # Unix
   ```

2. **Check environment variables**:
   ```bash
   echo $PYTHONIOENCODING  # Should output: utf-8
   echo $PYTHONUTF8        # Should output: 1
   ```

3. **Restart terminal** - Close and reopen terminal in Cursor

4. **Reinstall sitecustomize.py**:
   ```bash
   python scripts/install_unicode_support.py
   ```

### Subprocess Calls Still Failing

If subprocess calls still have encoding issues, they should inherit from the environment. However, you can explicitly set encoding (though it shouldn't be necessary):

```python
import os
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
result = subprocess.run(..., env=env, encoding="utf-8")
```

---

## Verification

After installation, test with:

```python
# Test 1: Direct print
print("✓ Test passed")
print("❌ Test failed")
print("✅ All good!")
print("你好世界 🌍")

# Test 2: Subprocess
import subprocess
result = subprocess.run(
    ["python", "-c", "print('✓ Unicode works!')"],
    capture_output=True,
    text=True,
    encoding="utf-8"
)
print(result.stdout)  # Should show: ✓ Unicode works!

# Test 3: Check encoding
import sys
assert sys.stdout.encoding == "utf-8", f"Expected utf-8, got {sys.stdout.encoding}"
```

---

## Maintenance

### When Creating New Virtual Environment

After creating a new venv, run:
```bash
python scripts/install_unicode_support.py
```

### When Updating Python Version

If you update Python version in venv, reinstall:
```bash
python scripts/install_unicode_support.py
```

---

## Files Modified

- ✅ `sitecustomize.py` - Created (Python site customization)
- ✅ `Makefile` - Added encoding exports
- ✅ `pytest.ini` - Added encoding environment variables
- ✅ `.vscode/settings.json` - Already had encoding (verified)
- ✅ `scripts/install_unicode_support.py` - Created (installation script)

---

## Notes

- `sitecustomize.py` must be in the site-packages directory to be automatically loaded
- Environment variables are inherited by subprocess calls
- Terminal must be restarted after changing `.vscode/settings.json`
- This solution works for both Windows and Unix systems

