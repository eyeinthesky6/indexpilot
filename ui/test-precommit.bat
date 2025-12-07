@echo off
echo Testing pre-commit hook...
echo.

echo Step 1: Generating types...
call npm run generate:types
if errorlevel 1 (
    echo Type generation failed, but continuing...
)

echo.
echo Step 2: Running lint-staged...
call npx lint-staged
if errorlevel 1 (
    echo Lint-staged failed
    exit /b 1
)

echo.
echo Pre-commit hook test complete!

