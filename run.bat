@echo off
REM Windows batch script for running the project
REM Set UTF-8 encoding for Windows console
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Use venv python if available, otherwise use system python
if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

if "%1"=="init-db" (
    echo Starting Postgres container...
    docker-compose up -d
    timeout /t 5 /nobreak >nul
    echo Initializing schema...
    %PYTHON% -c "import sys; sys.path.insert(0, '.'); from src.schema import init_schema; init_schema()"
    echo Bootstrapping genome catalog...
    %PYTHON% -c "import sys; sys.path.insert(0, '.'); from src.genome import bootstrap_genome_catalog; bootstrap_genome_catalog()"
    echo Database initialized!
    goto :end
)

if "%1"=="test" (
    %PYTHON% -m pytest tests/ -v
    goto :end
)

if "%1"=="sim-baseline" (
    %PYTHON% -u -m src.simulation.simulator baseline
    goto :end
)

if "%1"=="sim-autoindex" (
    %PYTHON% -u -m src.simulation.simulator autoindex
    goto :end
)

if "%1"=="report" (
    %PYTHON% -m src.reporting
    goto :end
)

if "%1"=="sim-scaled" (
    echo Running scaled simulation: 100 tenants, 10k+ rows, 100k queries...
    %PYTHON% -m src.simulation.simulator scaled
    echo Generating scaled analysis report...
    %PYTHON% -m src.scaled_reporting
    goto :end
)

if "%1"=="sim-comprehensive" (
    if "%2"=="" (
        echo Running comprehensive simulation with medium scenario...
        echo Note: For long simulations, output is redirected to logs\ directory
        %PYTHON% -u -m src.simulation.simulator comprehensive --scenario medium
    ) else (
        echo Running comprehensive simulation with %2 scenario...
        echo Note: For long simulations, output is redirected to logs\ directory
        %PYTHON% -u -m src.simulation.simulator comprehensive --scenario %2
    )
    goto :end
)

if "%1"=="scaled-report" (
    %PYTHON% -m src.scaled_reporting
    goto :end
)

if "%1"=="lint" (
    echo Running ruff linting with auto-fix...
    %PYTHON% -m ruff check --fix src/
    goto :end
)

if "%1"=="format" (
    echo Auto-formatting code with ruff...
    %PYTHON% -m ruff format src/
    goto :end
)

if "%1"=="typecheck" (
    echo Running mypy type checking...
    %PYTHON% -m mypy src/ --config-file mypy.ini
    goto :end
)

if "%1"=="check" (
    echo Running all checks...
    %PYTHON% -m ruff check --fix src/
    %PYTHON% -m mypy src/ --config-file mypy.ini
    goto :end
)

echo Usage: run.bat [init-db|test|sim-baseline|sim-autoindex|sim-scaled|sim-comprehensive|report|scaled-report|lint|format|typecheck|check]
echo   sim-comprehensive [scenario] - Run comprehensive simulation (small|medium|large|stress-test)
:end

