# IndexPilot Quick Start Guide

## Running Simulations

### ✅ Recommended: Direct Terminal

**For all simulations, use the terminal directly (not AI assistant):**

1. Open terminal: `Ctrl+` ` (backtick) or `Terminal > New Terminal`
2. Run simulation:
   ```bash
   python -u -m src.simulator comprehensive --scenario medium
   ```

**Why?** Cursor's AI assistant has a 5-10 second timeout that can't be overridden.

---

### Alternative: Batch Script with Logging

**Use `run-simulation.bat` to save output to logs:**

```bash
# In direct terminal:
run-simulation.bat medium
```

Output saved to: `logs\sim_medium_YYYYMMDD_HHMMSS.log`

---

## First Run Setup

**After installation, assess your setup:**

```bash
# Run setup assessment (checks database, initialization status)
python scripts/assess_setup.py

# Interactive mode (lists all available databases)
python scripts/assess_setup.py --interactive
```

**See**: `docs/installation/FIRST_RUN_SETUP.md` for complete first-run guide.

---

## Common Commands

### Quick Commands (Can use AI assistant):
```bash
# Activate virtual environment first (if using venv)
# On Windows (Git Bash):
source venv/Scripts/activate
# On Windows (CMD):
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Assess setup status
python scripts/assess_setup.py

# Check database connection
python -c "from src.db import get_connection; print('DB OK')"

# View logs
type logs\autoindex_output.log

# Run tests
pytest tests/ -v
```

### Long Commands (Use direct terminal):
```bash
# Simulations
python -u -m src.simulator comprehensive --scenario medium
python -u -m src.simulator comprehensive --scenario large
python -u -m src.simulator comprehensive --scenario stress-test

# Or use batch script:
run-simulation.bat medium
run-simulation.bat large
run-simulation.bat stress-test
```

---

## Cursor AI Assistant Limitations

**Use AI assistant for:**
- ✅ Code changes
- ✅ Quick commands (< 10 seconds)
- ✅ File operations
- ✅ Status checks

**Don't use AI assistant for:**
- ❌ Long-running simulations
- ❌ Commands that take > 10 seconds
- ❌ Build processes

**For long operations, always use the terminal directly.**

---

## Need Help?

- **Terminal timeout issues**: See `docs/installation/CURSOR_AI_ASSISTANT_LIMITATIONS.md`
- **Unicode issues**: See `docs/installation/WINDOWS_UNICODE_FIX.md`
- **Installation**: See `docs/installation/HOW_TO_INSTALL.md`

---

**Last Updated**: 07-12-2025

