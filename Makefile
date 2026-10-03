.PHONY: help up down migrate backend-check frontend-check docker-build check fmt

.DEFAULT_GOAL := help

# DB 測試用的管理連線（本機 compose 的 postgres）；可用環境變數覆寫。需先 docker compose up -d postgres
TEST_DATABASE_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/postgres

help: ## 列出所有 targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-16s %s\n", $$1, $$2}'

up: ## 啟動 docker compose（含 build）
	docker compose up --build

down: ## 停止 docker compose
	docker compose down

migrate: ## 對本機 compose 的資料庫執行 alembic upgrade head
	docker compose run --rm migrate

backend-check: ## backend：ruff、mypy、pytest --cov（需先 docker compose up -d postgres）
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run mypy
	cd backend && TEST_DATABASE_URL='$(TEST_DATABASE_URL)' uv run pytest --cov

frontend-check: ## frontend：lint、typecheck、test、build
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run test
	cd frontend && npm run build

docker-build: ## 建置 backend image
	docker build -t agentops-api ./backend

check: backend-check frontend-check docker-build ## 執行全部品質檢查

fmt: ## backend 格式化與自動修正
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .
