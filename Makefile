.PHONY: help init-db run-tests run-sim-baseline run-sim-autoindex run-sim-comprehensive report clean lint typecheck format check

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
	@echo "  make typecheck              - Run mypy type checking"
	@echo "  make format                 - Auto-format code with ruff"
	@echo "  make check                  - Run all checks (lint + typecheck)"

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
	python -m src.simulator baseline

run-sim-autoindex:
	@echo "Running auto-index simulation..."
	python -m src.simulator autoindex

run-sim-comprehensive:
	@echo "Running comprehensive simulation (medium scenario)..."
	@echo "This tests all product features across different database sizes"
	python -m src.simulator comprehensive --scenario medium

run-sim-comprehensive-small:
	@echo "Running comprehensive simulation (small scenario)..."
	python -m src.simulator comprehensive --scenario small

run-sim-comprehensive-large:
	@echo "Running comprehensive simulation (large scenario)..."
	python -m src.simulator comprehensive --scenario large

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

typecheck:
	@echo "Running mypy type checking..."
	python -m mypy src/ --config-file mypy.ini

format:
	@echo "Auto-formatting code with ruff..."
	python -m ruff format src/

check: lint typecheck
	@echo "All checks complete!"

