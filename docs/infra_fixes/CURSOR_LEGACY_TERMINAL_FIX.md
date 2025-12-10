# Cursor IDE Legacy Terminal Tool Fix

**Date**: 07-12-2025  
**Issue**: Commands being canceled prematurely in Cursor AI assistant  
**Solution**: Enable Legacy Terminal Tool

---

## Problem

Commands executed through Cursor's AI assistant are being canceled after 5-10 seconds, even though they should run longer. This prevents long-running simulations and other operations from completing.

---

## Solution: Enable Legacy Terminal Tool

Based on Cursor community forums, enabling the **Legacy Terminal Tool** can fix command cancellation issues.

### Steps to Enable:

1. **Open Cursor Settings:**
   - Press `Ctrl+,` (or `Cmd+,` on Mac)
   - Or go to `File > Preferences > Settings`

2. **Navigate to Terminal Settings:**
   - Search for "terminal" in settings
   - Or go to: `Agents > Inline Editing & Terminal`

3. **Enable Legacy Terminal Tool:**
   - Find the setting: **"Legacy Terminal Tool"** or **"Use Legacy Terminal"**
   - Enable/Check this option
   - This reverts the terminal tool to a previous version that handles command execution more reliably

4. **Restart Cursor:**
   - Close Cursor completely
   - Reopen Cursor
   - The setting should now be active

### Alternative: Settings JSON

If you prefer to edit settings directly, you can add this to your Cursor settings (not `.vscode/settings.json`, but Cursor's own settings):

1. Open Command Palette: `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: "Preferences: Open User Settings (JSON)"
3. Add:
   ```json
   {
     "cursor.terminal.useLegacyTool": true
   }
   ```

**Note:** The exact setting name may vary by Cursor version. Check Cursor's settings UI for the exact option name.

---

## Verification

After enabling Legacy Terminal Tool:

1. **Test with a short command:**
   ```bash
   python -c "import time; time.sleep(5); print('Done')"
   ```

2. **Test with medium simulation:**
   ```bash
   python -u -m src.simulator comprehensive --scenario medium
   ```

3. **Expected behavior:**
   - Commands should not be canceled prematurely
   - Commands should run to completion
   - No "Command was canceled by the user" messages

---

## Additional Settings

Along with Legacy Terminal Tool, ensure these settings are configured (already in `.vscode/settings.json`):

- `terminal.integrated.commandTimeout: 0` - Disable terminal timeout
- `terminal.integrated.shellIntegration.enabled: true` - Better command detection
- `TERM=dumb` - Prevent escape sequence issues
- Simplified prompt - Help Cursor detect command completion

---

## References

- [Cursor Forum - Commands in agent get auto-cancelled](https://forum.cursor.com/t/commands-in-agent-get-auto-cancelled/140950)
- [Cursor Forum - Terminal command execution hangs](https://forum.cursor.com/t/terminal-command-execution-hangs-on-complex-commands/74671)
- [Cursor Forum - AI assistant terminal commands never auto-complete](https://forum.cursor.com/t/bug-ai-assistant-terminal-commands-never-auto-complete/101844)

---

## If Legacy Terminal Tool Doesn't Work

If enabling Legacy Terminal Tool doesn't solve the issue:

1. **Run commands directly in terminal** (bypasses AI assistant timeout):
   - Open terminal: `Ctrl+` ` (backtick)
   - Run commands directly, not through AI assistant

2. **Check Cursor version:**
   - Update to latest version: `Help > Check for Updates`
   - Some versions have better terminal handling

3. **Report the issue:**
   - [Cursor GitHub Issues](https://github.com/cursor/cursor/issues)
   - [Cursor Community Forum](https://forum.cursor.com)

---

**Last Updated**: 07-12-2025

