.PHONY: help \
	dev dev-fe dev-be \
	install install-fe install-be \
	build lint test \
	lint-fe lint-be \
	test-be typecheck-fe typecheck-be \
	db-migrate db-upgrade db-reset seed \
	evals \
	clean

# ── default ──────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── install ───────────────────────────────────────────────────────────────────

install: install-fe install-be ## Install all dependencies

install-fe: ## Install frontend dependencies
	cd frontend && npm install

install-be: ## Install backend dependencies
	pip install -r backend/requirements-dev.txt

# ── dev servers ───────────────────────────────────────────────────────────────

dev: ## Start both servers concurrently (requires: npm i -g concurrently)
	concurrently \
		--names "fe,be" \
		--prefix-colors "cyan,green" \
		"make dev-fe" "make dev-be"

dev-fe: ## Start Next.js dev server (http://localhost:3000)
	cd frontend && npm run dev

dev-be: ## Start FastAPI dev server (http://localhost:8000)
	cd backend && uvicorn app.main:app --reload --port 8000

# ── build ─────────────────────────────────────────────────────────────────────

build: ## Build frontend for production
	cd frontend && npm run build

# ── lint ──────────────────────────────────────────────────────────────────────

lint: lint-fe lint-be ## Lint everything

lint-fe: ## ESLint on frontend
	cd frontend && npm run lint

lint-be: ## Ruff on backend
	cd backend && ruff check app tests

# ── typecheck ─────────────────────────────────────────────────────────────────

typecheck-fe: ## TypeScript type check (no emit)
	cd frontend && npx tsc --noEmit

typecheck-be: ## Mypy on backend
	cd backend && mypy app

# ── test ──────────────────────────────────────────────────────────────────────

test: test-be typecheck-fe ## Run all tests

test-be: ## Pytest on backend
	cd backend && pytest -v

test-be-fast: ## Pytest, stop on first failure
	cd backend && pytest -x -v

# ── database ──────────────────────────────────────────────────────────────────

db-migrate: ## Generate a new Alembic migration (MSG="description")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## Apply pending Alembic migrations
	cd backend && alembic upgrade head

db-reset: ## **DESTRUCTIVE** drop app.db and reapply all migrations
	@echo "WARNING: This will delete backend/app.db"; \
	read -p "Continue? [y/N] " ans; \
	[ "$$ans" = "y" ] && cd backend && rm -f app.db && alembic upgrade head || echo "Aborted."

# ── seed ──────────────────────────────────────────────────────────────────────

seed: ## Seed all factory data via API (backend must be running)
	curl -s -X POST http://localhost:8000/api/v1/factory/seed-all | python3 -m json.tool

seed-reset: ## Reset DB then reseed
	curl -s -X DELETE http://localhost:8000/api/v1/factory/reset-db | python3 -m json.tool
	curl -s -X POST  http://localhost:8000/api/v1/factory/seed-all  | python3 -m json.tool

# ── evals ─────────────────────────────────────────────────────────────────────

evals: ## Run eval suite (CI gate at 90%)
	python eval_suite.py --threshold 0.90

evals-baseline: ## Run baseline eval (save as results/baseline_eval_run_001.json)
	python eval_suite.py --threshold 0.0 --output results/baseline_eval_run_001.json

# ── clean ─────────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
