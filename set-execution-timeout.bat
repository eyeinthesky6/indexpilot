@echo off
REM Set EXECUTION_TIMEOUT_MS as system environment variable for Cursor IDE
REM Run this script as Administrator

echo Setting EXECUTION_TIMEOUT_MS environment variable...
echo.

REM Set for current user
setx EXECUTION_TIMEOUT_MS "300000"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: EXECUTION_TIMEOUT_MS has been set to 300000 (5 minutes)
    echo.
    echo IMPORTANT: You must restart Cursor completely for this to take effect.
    echo.
    echo Also ensure EXECUTION_TIMEOUT_MS is set in:
    echo   1. Cursor User Settings (Ctrl+Shift+P ^> Preferences: Open User Settings (JSON))
    echo   2. Workspace settings (.vscode/settings.json) - Already done
    echo   3. System environment variable - Just set by this script
    echo.
) else (
    echo.
    echo ERROR: Failed to set environment variable.
    echo Try running this script as Administrator.
    echo.
)

pause

