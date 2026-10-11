# jev-lab — default target prints help.
.DEFAULT_GOAL := help
UV ?= uv
APP ?= streamlit_app.py

.PHONY: help setup run run-live record cli bench test lint clean doctor budget-status

help: ## Show this help.
	@echo "jev-lab commands:"
	@echo "  make setup    Install deps (uv sync)"
	@echo "  make run      Launch app in DEMO mode (no key needed)"
	@echo "  make run-live Launch app in LIVE mode (needs TYPESAFE_API_KEY)"
	@echo "  make record   Re-record demo responses from live API (needs key)"
	@echo "  make cli      Terminal version of the Playground demo"
	@echo "  make bench    Calibration + speed benchmark (needs recordings)"
	@echo "  make test     Run pytest"
	@echo "  make lint     Run ruff"
	@echo "  make doctor   Check Python, key, connectivity, model list, budget"
	@echo "  make budget-status  Show spend vs cap"
	@echo "  make clean    Remove caches"
	@echo ""
	@echo "Windows (no make): use 'uv run ...' equivalents, e.g."
	@echo "  uv run streamlit run $(APP)"

setup: ## Install everything with uv.
	$(UV) sync --extra dev
	@test -f .env || cp .env.example .env
	@echo "Done. Edit .env to add TYPESAFE_API_KEY for live mode."

run: ## Launch app (demo mode if no key).
	$(UV) run streamlit run $(APP)

run-live: ## Launch app hitting the real API (requires key).
	@test -n "$$TYPESAFE_API_KEY" || (echo "Set TYPESAFE_API_KEY in .env first." && exit 1)
	$(UV) run streamlit run $(APP)

record: ## Re-record demo responses from live API (RECORD_ARGS="--force --where home" for full re-record).
	$(UV) run python scripts/record.py $(RECORD_ARGS)

cli: ## Terminal demo.
	$(UV) run python scripts/cli.py

bench: ## Benchmark.
	$(UV) run python scripts/bench.py

doctor: ## Environment + connectivity check.
	$(UV) run python scripts/doctor.py

budget-status: ## Show spend vs cap.
	$(UV) run python scripts/budget.py

test: ## Run tests.
	$(UV) run pytest -q

lint: ## Lint.
	$(UV) run ruff check .

clean: ## Remove caches.
	rm -rf .pytest_cache __pycache__ **/__pycache__ .ruff_cache
