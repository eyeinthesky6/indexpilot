@echo off
REM Run simulation in background with output redirection
REM This allows the simulation to complete even if Cursor AI assistant cancels

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul 2>&1

if "%1"=="" (
    echo Usage: run-simulation.bat [scenario]
    echo   scenario: small, medium, large, or stress-test
    exit /b 1
)

set SCENARIO=%1
set LOGFILE=logs\sim_%SCENARIO%_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

echo Starting %SCENARIO% simulation...
echo Output will be saved to: %LOGFILE%
echo.

REM Run simulation and redirect all output to log file
REM Use Python 3.13 explicitly
C:\Python313\python.exe -u -m src.simulator comprehensive --scenario %SCENARIO% > "%LOGFILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Simulation completed successfully!
    echo Check output in: %LOGFILE%
) else (
    echo.
    echo Simulation failed with error code: %ERRORLEVEL%
    echo Check output in: %LOGFILE%
    exit /b %ERRORLEVEL%
)

