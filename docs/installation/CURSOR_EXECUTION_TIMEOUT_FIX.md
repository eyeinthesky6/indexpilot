# Cursor IDE Execution Timeout Fix

**Date**: 07-12-2025  
**Issue**: Commands canceled after 5-10 seconds even with Legacy Terminal Tool enabled  
**Solution**: Set EXECUTION_TIMEOUT_MS environment variable

---

## Problem

Even with Legacy Terminal Tool enabled, commands are still being canceled after 5-10 seconds. This is due to Cursor's MCP (Model Context Protocol) execution timeout.

---

## Solution: Set EXECUTION_TIMEOUT_MS

Based on Cursor MCP documentation, you can increase the execution timeout by setting the `EXECUTION_TIMEOUT_MS` environment variable.

### Method 1: Workspace Settings (Recommended)

Add to `.vscode/settings.json`:

```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000"
  }
}
```

**Value:** `300000` = 5 minutes (300,000 milliseconds)

You can adjust this value:
- `600000` = 10 minutes
- `1800000` = 30 minutes
- `3600000` = 60 minutes (1 hour)

### Method 2: System Environment Variable

Set as a Windows environment variable:

1. Open System Properties:
   - Press `Win + R`
   - Type: `sysdm.cpl`
   - Press Enter

2. Go to "Advanced" tab > "Environment Variables"

3. Under "User variables", click "New":
   - Variable name: `EXECUTION_TIMEOUT_MS`
   - Variable value: `300000`

4. Restart Cursor

### Method 3: Terminal Session

Set in the current terminal session (temporary):

```cmd
set EXECUTION_TIMEOUT_MS=300000
```

---

## Verification

After setting `EXECUTION_TIMEOUT_MS`:

1. **Restart Cursor completely**

2. **Test with a long command:**
   ```bash
   python -c "import time; print('Starting...'); time.sleep(30); print('Done after 30 seconds')"
   ```

3. **Test with medium simulation:**
   ```bash
   python -u -m src.simulator comprehensive --scenario medium
   ```

4. **Expected behavior:**
   - Commands should not be canceled before the timeout expires
   - Commands should run for at least 5 minutes (or your configured timeout)

---

## Combined Settings

For best results, use all these settings together:

1. **Legacy Terminal Tool** (enabled in Cursor settings)
2. **EXECUTION_TIMEOUT_MS** (set to 300000 or higher)
3. **Terminal stability settings** (already in `.vscode/settings.json`)
4. **.cursor/rules** (prevents AI from canceling commands)

---

## References

- [Cursor MCP Server Documentation](https://cursormcp.net/en/mcpserver/shinpr-sub-agents-mcp)
- [Cursor Forum - Commands auto-cancelled](https://forum.cursor.com/t/commands-in-agent-get-auto-cancelled/140950)

---

## If This Doesn't Work

If setting `EXECUTION_TIMEOUT_MS` doesn't solve the issue:

1. **Run commands directly in terminal** (bypasses AI assistant completely):
   - Open terminal: `Ctrl+` ` (backtick)
   - Run commands directly, not through AI assistant

2. **Use background execution with output redirection:**
   ```bash
   python -u -m src.simulator comprehensive --scenario medium > sim_output.log 2>&1 &
   ```

3. **Check Cursor version:**
   - Update to latest: `Help > Check for Updates`
   - Some versions have better timeout handling

4. **Report the issue:**
   - [Cursor GitHub Issues](https://github.com/cursor/cursor/issues)
   - Include that Legacy Terminal Tool is enabled and EXECUTION_TIMEOUT_MS is set

---

**Last Updated**: 07-12-2025

