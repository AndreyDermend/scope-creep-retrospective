.PHONY: help install install-dev test test-cov lint format run web clean report hook check

PY := python3
SRC := src/scope_creep
TESTS := tests

help:  ## Show this help
	@echo "Scope-Creep Retrospective — dev commands"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install runtime dependencies
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

install-dev:  ## Install dev + runtime dependencies
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .

test:  ## Run tests
	PYTHONPATH=src $(PY) -m pytest $(TESTS)

test-cov:  ## Run tests with coverage report
	PYTHONPATH=src $(PY) -m pytest $(TESTS) --cov=scope_creep --cov-report=term-missing

lint:  ## Lint with ruff
	$(PY) -m ruff check $(SRC) $(TESTS)

format:  ## Auto-format with ruff
	$(PY) -m ruff format $(SRC) $(TESTS)
	$(PY) -m ruff check --fix $(SRC) $(TESTS)

check: lint test  ## Run all checks (lint + tests) — CI-equivalent

run:  ## Run the full three-agent pipeline (terminal UI)
	PYTHONPATH=src $(PY) -m scope_creep.main

web:  ## Run the full three-agent pipeline (web UI on http://localhost:8000)
	PYTHONPATH=src $(PY) -m scope_creep.main --ui web

report:  ## Regenerate HTML report from saved transcripts
	PYTHONPATH=src $(PY) -m scope_creep.ui.report

hook:  ## Install the pre-commit hook
	pre-commit install

clean:  ## Remove generated artifacts
	rm -rf transcripts docs/report.html prediction.csv presentation.pptx
	rm -rf training.csv scoring.csv
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
