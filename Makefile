# Daily Brief Agent — convenience targets (macOS / Linux).
# These are thin wrappers over scripts/setup.sh, the `daily-brief` CLI, and dev tooling.
# They run everything through the local .venv so no conda/global install is needed.

VENV    := .venv
PYTHON  := $(VENV)/bin/python
BIN     := $(VENV)/bin

# Use uv when available (faster); fall back to the venv's python -m pip.
UV := $(shell command -v uv 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help setup install env init-db run dry-run serve preview doctor \
        schedule list-runs test lint typecheck check clean distclean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Full one-command setup (venv + install + .env + init-db)
	./scripts/setup.sh

install: ## Create venv (if needed) and install package with dev deps
ifeq ($(UV),)
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
else
	uv venv --allow-existing --python ">=3.11" $(VENV)
	uv pip install --python $(VENV) -e ".[dev]"
endif

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

init-db: ## Initialize the SQLite database
	$(BIN)/daily-brief init-db

run: ## Run one digest now (sends via configured provider)
	$(BIN)/daily-brief run-now

dry-run: ## Run the full pipeline without sending (writes preview to var/outbox/)
	$(BIN)/daily-brief dry-run

preview: ## Render an email preview without sending
	$(BIN)/daily-brief preview-email

serve: ## Start the web dashboard at http://127.0.0.1:8000
	$(BIN)/daily-brief serve

doctor: ## Run configuration / readiness checks
	$(BIN)/daily-brief doctor

schedule: ## Start the APScheduler loop
	$(BIN)/daily-brief schedule

list-runs: ## Show recent run history
	$(BIN)/daily-brief list-runs --limit 10

test: ## Run the test suite
	$(BIN)/pytest

lint: ## Run ruff
	$(BIN)/ruff check src tests

typecheck: ## Run mypy (strict)
	$(BIN)/mypy src

check: lint typecheck test ## Run lint + typecheck + tests

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

distclean: clean ## Also remove the virtual environment
	rm -rf $(VENV)
