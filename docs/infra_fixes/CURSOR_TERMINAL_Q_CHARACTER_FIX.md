# Cursor IDE Terminal 'q' Character Bug Fix

**Date**: 07-12-2025  
**Issue**: Terminal commands prepended with 'q' character in Cursor IDE

---

## Problem

When executing terminal commands in Cursor IDE, a 'q' character sometimes appears before the command, causing commands to fail. This is often accompanied by sequences like `q^D^C` or `q^C`.

**Symptoms:**
- Commands appear as `q<command>` instead of just `<command>`
- Commands fail to execute correctly
- Issue may appear after using Cursor's "stop" or "skip" functions
- Terminal may show escape sequences or control characters

**Example:**
```bash
# Expected:
python -m src.simulator

# Actual:
qpython -m src.simulator
```

---

## Root Cause

The 'q' character issue in Cursor IDE terminals is caused by several potential factors:

1. **Terminal Escape Sequences (DECSCUSR)**: Cursor style sequences like `ESC [ 1 q` are used to set cursor shape, but can be misinterpreted by terminal emulators, causing the 'q' character to be displayed.

2. **Cursor IDE Bug**: A known bug in Cursor IDE where using "stop" or "skip" functions causes the next terminal command to be prepended with 'q'. This is a software bug that has been reported to Cursor's development team.

3. **Terminal Configuration Conflicts**: Custom terminal configurations or themes (like Powerlevel10k for Zsh) can interfere with Cursor's terminal operations, leading to unintended character insertion.

4. **Terminal Emulator Interpretation**: Some terminal emulators incorrectly interpret cursor style sequences, resulting in visible 'q' characters.

**References:**
- [Cursor Forum - Terminal shows q^D^C](https://forum.cursor.com/t/the-terminal-always-shows-q-d-c-for-no-reason/110587)
- [Cursor Forum - Bug: q prepended after stop/skip](https://forum.cursor.com/t/bug-a-q-is-prepended-to-terminal-commands-after-using-stop-or-skip-in-cursor/132819)
- [Cursor Forum - Agent sends spurious q c d commands](https://forum.cursor.com/t/agent-sends-spurious-q-c-d-commands-with-default-terminal-command-prompt/111888)
- [GitHub Issue #3138](https://github.com/cursor/cursor/issues/3138)

---

## Solutions

### Solution 0: Configure Cursor User Settings (CRITICAL - Do This First!)

**⚠️ IMPORTANT:** Cursor IDE has **separate user settings** from workspace settings. The 'q' character bug may require configuration in **both** locations.

**Cursor User Settings Location (Windows):**
```
%APPDATA%\Cursor\User\settings.json
```

**How to Access:**
1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Add the same terminal settings as workspace settings

**Required User Settings:**
```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb"
  },
  "terminal.integrated.defaultProfile.windows": "Command Prompt",
  "terminal.integrated.shellIntegration.enabled": true
}
```

**See `CURSOR_USER_SETTINGS_SYNC.md` for complete sync guide.**

**After configuring user settings:**
1. **Restart Cursor completely** (close all windows)
2. **Close and reopen terminal**
3. Test if issue is resolved

---

### Solution 1: Update Cursor IDE (Recommended Second Step)

**The Cursor development team has been working on fixes for this issue in subsequent releases.**

1. Check your current Cursor version: `Help > About`
2. Update to the latest version: `Help > Check for Updates`
3. Restart Cursor completely after updating
4. Test if the issue persists

**This is the most reliable fix if the bug has been addressed in newer versions.**

---

### Solution 2: Terminal Stability Settings (Recommended)

**Add terminal stability settings to prevent escape sequence conflicts:**

These settings help stabilize terminal behavior and reduce escape sequence issues. They're already configured in `.vscode/settings.json`:

```json
{
  "terminal.integrated.commandTimeout": 0,
  "terminal.integrated.killOnExit": "never",
  "terminal.integrated.enablePersistentSessions": true,
  "terminal.integrated.persistentSessionReviveProcess": "onExit",
  "terminal.integrated.scrollback": 10000,
  "terminal.integrated.enableMultiLinePasteWarning": false,
  "terminal.integrated.automationProfile.windows": null
}
```

**Note:** These settings help with terminal stability but don't directly fix the 'q' character bug. The primary fix is to restart terminal after stop/skip or use direct terminal.

### Solution 2b: Disable Terminal Cursor Style Sequences (Optional - May Break Features)

**⚠️ Warning:** Setting `TERM=dumb` disables cursor style sequences but may affect terminal features like syntax highlighting, colors, and some interactive programs. Only use if other solutions don't work.

**For Windows Command Prompt:**

```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb"
  },
  "terminal.integrated.profiles.windows": {
    "Command Prompt": {
      "path": ["${env:windir}\\System32\\cmd.exe"],
      "args": ["/k", "chcp 65001 >nul 2>&1 && set TERM=dumb"],
      "icon": "terminal-cmd"
    }
  }
}
```

**For PowerShell:**

```json
{
  "terminal.integrated.profiles.windows": {
    "PowerShell": {
      "source": "PowerShell",
      "args": [
        "-NoExit",
        "-Command",
        "$env:TERM='dumb'"
      ],
      "icon": "terminal-powershell"
    }
  }
}
```

**For Git Bash:**

```json
{
  "terminal.integrated.profiles.windows": {
    "Git Bash": {
      "path": ["${env:ProgramFiles}\\Git\\bin\\bash.exe"],
      "args": [],
      "env": {
        "TERM": "dumb"
      },
      "icon": "terminal-bash"
    }
  }
}
```

---

### Solution 3: Review and Disable Terminal Customizations

**If you're using custom terminal configurations:**

1. **Check for Powerlevel10k or similar themes:**
   - Check `~/.zshrc` or `~/.bashrc` for theme configurations
   - Temporarily disable or comment out theme loading
   - Restart terminal and test

2. **Check for cursor style configurations:**
   - Search for `DECSCUSR` or cursor style sequences in shell config files
   - Comment out or remove these configurations
   - Restart terminal

3. **Use minimal shell configuration:**
   - Create a minimal `.bashrc` or `.zshrc` for testing
   - Gradually add configurations back to identify the culprit

---

### Solution 4: Restart Terminal After Stop/Skip

**If the issue occurs after using Cursor's "stop" or "skip" functions:**

1. **Close the affected terminal:**
   - Right-click terminal tab > "Kill Terminal"
   - Or use `Ctrl+Shift+` ` to close terminal

2. **Open a new terminal:**
   - `Terminal > New Terminal`
   - Or `Ctrl+` ` (backtick)

3. **Avoid using stop/skip:**
   - Instead of using stop/skip, let commands complete naturally
   - Or use `Ctrl+C` directly in the terminal if needed

---

### Solution 5: Use Direct Terminal (Workaround)

**For critical commands, use Cursor's terminal directly instead of AI assistant:**

1. Open terminal in Cursor (`Ctrl+` ` or `Terminal > New Terminal`)
2. Type commands directly (not through AI assistant)
3. This bypasses the AI assistant's command execution layer

**This workaround avoids the bug entirely when using the terminal directly.**

---

### Solution 6: Terminal Settings Configuration (Already Applied)

**Terminal stability settings are already configured in `.vscode/settings.json`:**

These settings help stabilize terminal behavior and reduce escape sequence conflicts. They're part of the standard configuration for this project.

---

## Troubleshooting

### Issue Persists After Updates

1. **Clear Cursor Cache:**
   - Close Cursor completely
   - Delete Cursor cache directory (location varies by OS)
   - Restart Cursor

2. **Reset Terminal Settings:**
   - Remove custom terminal configurations
   - Use default terminal profiles
   - Test with minimal configuration

3. **Check for Conflicting Extensions:**
   - Disable terminal-related extensions
   - Test if issue persists
   - Re-enable extensions one by one

### Commands Still Show 'q' Character

1. **Manual Command Entry:**
   - Type commands directly in terminal (not via AI)
   - This confirms if it's an AI assistant issue vs terminal issue

2. **Different Terminal Profile:**
   - Try switching between Command Prompt, PowerShell, Git Bash
   - One profile may work better than others

3. **Report to Cursor:**
   - If issue persists, report to Cursor support
   - Include: OS version, Cursor version, terminal type, steps to reproduce

---

## Verification

To verify the fix works:

1. **Test Basic Command:**
   ```bash
   echo "test"
   # Should output: test (not qtest)
   ```

2. **Test Python Command:**
   ```bash
   python --version
   # Should show Python version (not qpython)
   ```

3. **Test After Stop/Skip:**
   - Use stop/skip function in Cursor
   - Run a command
   - Verify no 'q' character appears

---

## Prevention

**Best Practices to Avoid This Issue:**

1. **Keep Cursor Updated:** Regularly update to latest version
2. **Use Direct Terminal:** For critical commands, use terminal directly
3. **Minimal Terminal Config:** Avoid overly complex terminal customizations
4. **Restart Terminal:** If you notice the issue, restart terminal immediately
5. **Report Issues:** Report persistent issues to Cursor development team

---

## Related Issues

- **User Settings Sync:** See `CURSOR_USER_SETTINGS_SYNC.md` - **CRITICAL: Check this if fix doesn't work!**
- **Terminal Timeout:** See `CURSOR_TERMINAL_TIMEOUT_FIX.md` for timeout issues
- **Unicode Encoding:** See `WINDOWS_UNICODE_FIX.md` for encoding issues
- **Command Auto-Canceling:** Related to MCP timeout limitations

---

## Conclusion

**The 'q' character issue is a known bug in Cursor IDE that can be caused by:**
- Terminal escape sequence misinterpretation
- Cursor IDE software bugs (especially after stop/skip)
- Terminal configuration conflicts

**Recommended Approach:**
1. **Update Cursor to latest version** (most important - fixes are being released)
2. **Restart terminal after using stop/skip** (primary workaround)
3. **Use direct terminal** for critical commands instead of AI assistant
4. **Review terminal customizations** if issue persists (Powerlevel10k, etc.)
5. **Only use TERM=dumb as last resort** (may break terminal features)
6. Report persistent issues to Cursor support

**This is a Cursor IDE limitation/bug, not an issue with IndexPilot or your code.**

---

**Last Updated**: 07-12-2025

