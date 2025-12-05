@echo off
REM Windows batch script for running the project

if "%1"=="init-db" (
    echo Starting Postgres container...
    docker-compose up -d
    timeout /t 5 /nobreak >nul
    echo Initializing schema...
    python -m src.schema
    echo Bootstrapping genome catalog...
    python -m src.genome
    echo Database initialized!
    goto :end
)

if "%1"=="test" (
    pytest tests/ -v
    goto :end
)

if "%1"=="sim-baseline" (
    python -m src.simulator baseline
    goto :end
)

if "%1"=="sim-autoindex" (
    python -m src.simulator autoindex
    goto :end
)

if "%1"=="report" (
    python -m src.reporting
    goto :end
)

if "%1"=="sim-scaled" (
    echo Running scaled simulation: 100 tenants, 10k+ rows, 100k queries...
    python -m src.simulator scaled
    echo Generating scaled analysis report...
    python -m src.scaled_reporting
    goto :end
)

if "%1"=="scaled-report" (
    python -m src.scaled_reporting
    goto :end
)

if "%1"=="lint" (
    echo Running ruff linting with auto-fix...
    python -m ruff check --fix src/
    goto :end
)

if "%1"=="format" (
    echo Auto-formatting code with ruff...
    python -m ruff format src/
    goto :end
)

if "%1"=="typecheck" (
    echo Running mypy type checking...
    python -m mypy src/ --config-file mypy.ini
    goto :end
)

if "%1"=="check" (
    echo Running all checks...
    python -m ruff check --fix src/
    python -m mypy src/ --config-file mypy.ini
    goto :end
)

echo Usage: run.bat [init-db|test|sim-baseline|sim-autoindex|sim-scaled|report|scaled-report|lint|format|typecheck|check]
:end

