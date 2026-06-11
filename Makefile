.PHONY: help \
	setup \
	dev dev-fe dev-be \
	install install-fe install-be \
	build lint test \
	lint-fe lint-be \
	test-be typecheck-fe typecheck-be \
	db-migrate db-upgrade db-reset seed seed-reset seed-offline fresh \
	import-historical \
	vectordb-reset vectordb-audit vectordb-prune \
	modules-extract modules-approve pii-filter \
	evals evals-baseline \
	clean

VENV := backend/.venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

# ── default ──────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── install ───────────────────────────────────────────────────────────────────

setup: ## First-time setup: venv + all deps + spaCy model
	@echo "Python: $$(python3 --version) | expected 3.11.14 (use pyenv)"
	@echo "Node:   $$(node --version)   | expected 22.17.0 (use nvm)"
	cd backend && python3 -m venv .venv && \
		. .venv/bin/activate && \
		pip install --upgrade pip && \
		pip install -r requirements-dev.txt && \
		python3 -m spacy download en_core_web_sm
	cd frontend && npm install
	@echo "Setup complete. Activate venv: source backend/.venv/bin/activate"

install: install-fe install-be ## Install all dependencies

install-fe: ## Install frontend dependencies
	cd frontend && npm install

install-be: ## Install backend dependencies
	$(PIP) install -r backend/requirements-dev.txt
	$(PY) -m spacy download en_core_web_sm

# ── dev servers ───────────────────────────────────────────────────────────────

dev: ## Start both servers concurrently (requires: npm i -g concurrently)
	concurrently \
		--names "fe,be" \
		--prefix-colors "cyan,green" \
		"make dev-fe" "make dev-be"

dev-fe: ## Start Next.js dev server (http://localhost:3000)
	cd frontend && npm run dev

dev-be: ## Start FastAPI dev server (http://localhost:8000)
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# ── build ─────────────────────────────────────────────────────────────────────

build: ## Build frontend for production
	cd frontend && npm run build

# ── lint ──────────────────────────────────────────────────────────────────────

lint: lint-fe lint-be ## Lint everything

lint-fe: ## ESLint on frontend
	cd frontend && npm run lint

lint-be: ## Ruff on backend
	cd backend && .venv/bin/ruff check app tests

# ── typecheck ─────────────────────────────────────────────────────────────────

typecheck-fe: ## TypeScript type check (no emit)
	cd frontend && npx tsc --noEmit

typecheck-be: ## Mypy on backend
	cd backend && .venv/bin/mypy app

# ── test ──────────────────────────────────────────────────────────────────────

test: test-be typecheck-fe ## Run all tests

test-be: ## Pytest on backend
	cd backend && .venv/bin/pytest -v

test-be-fast: ## Pytest, stop on first failure
	cd backend && .venv/bin/pytest -x -v

# ── database ──────────────────────────────────────────────────────────────────

db-migrate: ## Generate a new Alembic migration (MSG="description")
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## Apply pending Alembic migrations
	cd backend && .venv/bin/alembic upgrade head

db-reset: ## **DESTRUCTIVE** drop app.db + vector store + checkpointer, reapply migrations
	@echo "WARNING: This deletes backend/app.db, chroma_db/, and project_state.db"; \
	read -p "Continue? [y/N] " ans; \
	[ "$$ans" = "y" ] && cd backend && \
		rm -f app.db app.db-shm app.db-wal && \
		rm -rf chroma_db && \
		rm -f project_state.db project_state.db-shm project_state.db-wal && \
		.venv/bin/alembic upgrade head || echo "Aborted."

# ── vector store ──────────────────────────────────────────────────────────────

vectordb-reset: ## **DESTRUCTIVE** wipe chroma_db + checkpointer (stop server first)
	@echo "WARNING: This deletes backend/chroma_db/ and project_state.db"; \
	read -p "Continue? [y/N] " ans; \
	[ "$$ans" = "y" ] && cd backend && \
		rm -rf chroma_db && \
		rm -f project_state.db project_state.db-shm project_state.db-wal && \
		echo "Vector store + checkpointer wiped." || echo "Aborted."

vectordb-audit: ## Report orphan chroma collections (no matching project row)
	cd backend && .venv/bin/python scripts/vectordb_audit.py

vectordb-prune: ## Delete orphan chroma collections + their checkpointer threads
	cd backend && .venv/bin/python scripts/vectordb_audit.py --prune

# ── seed ──────────────────────────────────────────────────────────────────────

seed: ## Seed all factory data via API (backend must be running)
	curl -s -X POST http://localhost:8000/api/v1/factory/seed-all | python3 -m json.tool

seed-reset: ## Reset DB then reseed (backend must be running)
	curl -s -X DELETE http://localhost:8000/api/v1/factory/reset-db | python3 -m json.tool
	curl -s -X POST  http://localhost:8000/api/v1/factory/seed-all  | python3 -m json.tool

seed-offline: ## Seed reference data directly via DB session (no server needed)
	cd backend && .venv/bin/python scripts/seed_offline.py

import-historical: ## Import real historical projects from CSV (CSV=path [REPLACE=1])
	@[ -n "$(CSV)" ] || (echo "Usage: make import-historical CSV=path/to/projects.csv [REPLACE=1]" && exit 1)
	cd backend && .venv/bin/python scripts/import_historical.py "$(CSV)" $(if $(REPLACE),--replace,)

fresh: ## **DESTRUCTIVE** full wipe + migrate + seed, no server needed (stop server first)
	@echo "WARNING: This deletes backend/app.db, chroma_db/, and project_state.db, then reseeds"; \
	read -p "Continue? [y/N] " ans; \
	[ "$$ans" = "y" ] || { echo "Aborted."; exit 0; }; \
	cd backend && \
		rm -f app.db app.db-shm app.db-wal && \
		rm -rf chroma_db && \
		rm -f project_state.db project_state.db-shm project_state.db-wal && \
		.venv/bin/alembic upgrade head && \
		.venv/bin/python scripts/seed_offline.py && \
		echo "Fresh DB ready. Start servers: make dev"

# ── project phase helpers (backend must be running) ───────────────────────────

modules-extract: ## LLM-extract work modules from proposal (ID=<project_id>)
	@[ -n "$(ID)" ] || (echo "Usage: make modules-extract ID=<project_id>" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/projects/$(ID)/modules | python3 -m json.tool

modules-approve: ## Approve modules and advance phase to techstack (ID=<project_id>)
	@[ -n "$(ID)" ] || (echo "Usage: make modules-approve ID=<project_id>" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/projects/$(ID)/modules/approve | python3 -m json.tool

pii-filter: ## Run LLM quality filter on NER PII detections (ID=<project_id>)
	@[ -n "$(ID)" ] || (echo "Usage: make pii-filter ID=<project_id>" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/projects/$(ID)/pii-llm-filter | python3 -m json.tool

proposal-approve: ## Approve proposal and advance phase to modules (ID=<project_id>)
	@[ -n "$(ID)" ] || (echo "Usage: make proposal-approve ID=<project_id>" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/projects/$(ID)/proposal/approve | python3 -m json.tool

doc-status: ## Poll document ingestion status (ID=<project_id>)
	@[ -n "$(ID)" ] || (echo "Usage: make doc-status ID=<project_id>" && exit 1)
	curl -s http://localhost:8000/api/v1/projects/$(ID)/document-status | python3 -m json.tool

# ── evals ─────────────────────────────────────────────────────────────────────

evals: ## Run eval suite (CI gate at 90%)
	$(PY) eval_suite.py --threshold 0.90

evals-baseline: ## Run baseline eval (save as results/baseline_eval_run_001.json)
	$(PY) eval_suite.py --threshold 0.0 --output results/baseline_eval_run_001.json

# ── clean ─────────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
