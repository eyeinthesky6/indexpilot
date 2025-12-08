@echo off
REM Download test databases for IndexPilot benchmarking
REM Date: 08-12-2025

setlocal enabledelayedexpansion

set DATASETS_DIR=..\..\data\benchmarking
if not exist "%DATASETS_DIR%" mkdir "%DATASETS_DIR%"

echo Downloading test databases for IndexPilot...

REM 1. Employees Database
echo Downloading Employees database...
if not exist "%DATASETS_DIR%\employees_db-full-1.0.6.tar.bz2" (
    curl -L -o "%DATASETS_DIR%\employees_db-full-1.0.6.tar.bz2" ^
        "https://github.com/datacharmer/test_db/archive/refs/heads/master.zip" || ^
    curl -L -o "%DATASETS_DIR%\employees_db-full-1.0.6.tar.bz2" ^
        "https://github.com/datacharmer/test_db/releases/download/v1.0.7/test_db-1.0.7.tar.gz"
    echo ✅ Employees database downloaded
) else (
    echo ✅ Employees database already downloaded
)

REM 2. Sakila Database (PostgreSQL version)
echo Downloading Sakila database...
if not exist "%DATASETS_DIR%\sakila-pg.zip" (
    curl -L -o "%DATASETS_DIR%\sakila-pg.zip" ^
        "https://www.postgresqltutorial.com/wp-content/uploads/2019/05/dvdrental.zip"
    if errorlevel 1 (
        echo ⚠️  Sakila download failed. Please download manually from:
        echo    https://www.postgresqltutorial.com/postgresql-sample-database/
    ) else (
        echo ✅ Sakila database downloaded
    )
) else (
    echo ✅ Sakila database already downloaded
)

REM 3. World Database
echo Downloading World database...
if not exist "%DATASETS_DIR%\world.sql" (
    curl -L -o "%DATASETS_DIR%\world.sql" ^
        "https://www.postgresqltutorial.com/wp-content/uploads/2019/05/world.sql"
    if errorlevel 1 (
        echo ⚠️  World database download failed. Please download manually from:
        echo    https://www.postgresqltutorial.com/postgresql-sample-database/
    ) else (
        echo ✅ World database downloaded
    )
) else (
    echo ✅ World database already downloaded
)

echo.
echo ✅ Download complete!
echo Next steps:
echo   1. Extract archives: cd datasets ^&^& unzip sakila-pg.zip
echo   2. Run setup scripts: python scripts\setup_sakila.py
echo   3. See docs\testing\DATASET_SETUP.md for details

