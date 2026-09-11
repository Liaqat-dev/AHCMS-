# Native (non-Docker) task runner for macOS/Linux. On Windows use the
# equivalent PowerShell scripts in scripts\ (setup.ps1, dev.ps1, ...).
.DEFAULT_GOAL := help

# Backend commands run through the project virtualenv. To drive them with uv
# instead:  make PY="uv run python" test
PY ?= .venv/bin/python

# The two independent Angular workspaces.
STAFF  := frontend-staff
PORTAL := frontend-portal

.PHONY: help setup backend staff portal dev migrate revision seed lint test format build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and both frontend dependency sets
	cd backend && uv sync
	cd $(STAFF) && npm ci
	cd $(PORTAL) && npm ci

backend: ## Run the API on :8000 (migrations first, then reload server)
	cd backend && $(PY) -m alembic upgrade head
	cd backend && $(PY) -m app.cli.seed_superadmin
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000

staff: ## Run the staff app on :4200 (proxies /api to :8000)
	cd $(STAFF) && npm run start

portal: ## Run the student portal on :4300 (proxies /api to :8000)
	cd $(PORTAL) && npm run start

dev: ## Run the backend and both apps concurrently
	$(MAKE) -j3 backend staff portal

migrate: ## Apply database migrations
	cd backend && $(PY) -m alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add students"
	cd backend && $(PY) -m alembic revision --autogenerate -m "$(m)"

seed: ## Create/refresh the super-admin from SUPERADMIN_* in backend/.env
	cd backend && $(PY) -m app.cli.seed_superadmin

lint: ## Lint backend (ruff + mypy) and both frontends (eslint)
	cd backend && $(PY) -m ruff check . && $(PY) -m mypy app
	cd $(STAFF) && npm run lint
	cd $(PORTAL) && npm run lint

format: ## Format backend (ruff) and both frontends (prettier)
	cd backend && $(PY) -m ruff format .
	cd $(STAFF) && npm run format
	cd $(PORTAL) && npm run format

test: ## Disabled by project policy (see CLAUDE.md); tests are kept but not collected
	@echo "Tests are disabled by project policy (see CLAUDE.md). Nothing run."

build: ## Production build of both frontends
	cd $(STAFF) && npm run build
	cd $(PORTAL) && npm run build
