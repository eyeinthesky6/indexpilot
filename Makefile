.PHONY: help init-db run-tests run-sim-baseline run-sim-autoindex run-sim-comprehensive report clean lint lint-check typecheck format check quality pylint-check pyright-check circular-check

help:
	@echo "Available commands:"
	@echo "  make init-db                - Initialize database (start Postgres and setup schema)"
	@echo "  make run-tests              - Run pytest tests"
	@echo "  make run-sim-baseline       - Run baseline simulation (no auto-indexing)"
	@echo "  make run-sim-autoindex     - Run simulation with auto-indexing"
	@echo "  make run-sim-comprehensive  - Run comprehensive simulation (tests all features)"
	@echo "  make report                 - Generate performance report"
	@echo "  make clean                  - Clean up results and stop containers"
	@echo "  make lint                   - Run ruff linting (auto-fix enabled)"
	@echo "  make lint-check             - Run ruff linting (check only, no auto-fix)"
	@echo "  make typecheck              - Run mypy type checking"
	@echo "  make format                 - Auto-format code with ruff"
	@echo "  make check                  - Run all checks (lint + typecheck)"
	@echo "  make quality                - Run all quality tools (format, lint-check, mypy, pylint, pyright, circular)"
	@echo "  make pylint-check          - Run pylint static analysis"
	@echo "  make pyright-check          - Run pyright type checking"
	@echo "  make circular-check         - Check for circular imports"

init-db:
	@echo "Starting Postgres container..."
	docker-compose up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 5
	@echo "Initializing schema..."
	python -m src.schema
	@echo "Bootstrapping genome catalog..."
	python -m src.genome
	@echo "Database initialized!"

run-tests:
	pytest tests/ -v

run-sim-baseline:
	@echo "Running baseline simulation..."
	python -u -m src.simulator baseline

run-sim-autoindex:
	@echo "Running auto-index simulation..."
	python -u -m src.simulator autoindex

run-sim-comprehensive:
	@echo "Running comprehensive simulation (medium scenario)..."
	@echo "This tests all product features across different database sizes"
	python -u -m src.simulator comprehensive --scenario medium

run-sim-comprehensive-small:
	@echo "Running comprehensive simulation (small scenario)..."
	python -u -m src.simulator comprehensive --scenario small

run-sim-comprehensive-large:
	@echo "Running comprehensive simulation (large scenario)..."
	python -u -m src.simulator comprehensive --scenario large

report:
	@echo "Generating report..."
	python -m src.reporting

clean:
	@echo "Cleaning up..."
	rm -f docs/audit/toolreports/results_*.json
	rm -f docs/audit/toolreports/*.json
	rm -f docs/audit/toolreports/*.md
	rm -f docs/audit/toolreports/logs/*.log
	docker-compose down
	@echo "Cleanup complete!"

lint:
	@echo "Running ruff linting (with auto-fix)..."
	python -m ruff check --fix src/

lint-check:
	@echo "Running ruff linting (check only, no auto-fix)..."
	python -m ruff check src/

typecheck:
	@echo "Running mypy type checking..."
	@python -m mypy src/ --config-file mypy.ini
	@echo ""
	@echo "Running pyright type checking..."
	@python -m pyright src/
	@echo ""
	@echo "Type checking complete (mypy + pyright)"

format:
	@echo "Auto-formatting code with ruff..."
	python -m ruff format src/

check: lint typecheck
	@echo "All checks complete!"

pylint-check:
	@echo "Running pylint static analysis..."
	@python -m pylint src/ --rcfile=pylintrc || true

pyright-check:
	@echo "Running pyright type checking..."
	@python -m pyright src/ || true

circular-check:
	@echo "Checking for circular imports with pylint..."
	@python -m pylint src/ --disable=all --enable=import-error,cyclic-import --rcfile=pylintrc || true

quality: format lint-check typecheck pylint-check pyright-check circular-check
	@echo "========================================="
	@echo "All quality checks complete!"
	@echo "========================================="

