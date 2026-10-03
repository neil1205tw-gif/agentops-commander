# AgentOps Commander

用於事故處置的多 Agent 指揮中心：由 Agent 分析事故、提出處置方案，並在人工核准後執行。

> **所有基礎設施操作皆為模擬。** 本專案不會對任何真實的雲端、叢集或生產環境執行變更。

## 本機快速啟動

需求：Docker（含 Docker Compose）。

```bash
docker compose up --build
```

不需要 `.env` 即可啟動；如需自訂設定，可複製 `.env.example` 為 `.env`（請勿提交）。

| 服務 | 網址 |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 （健康檢查：`/health/ready`） |
| Postgres（pgvector） | localhost:5432 |

若本機 port 已被佔用，可用環境變數覆寫 host port：`POSTGRES_PORT`、`BACKEND_PORT`、`FRONTEND_PORT`。

停止服務：`docker compose down`（資料保存在 named volume，加上 `-v` 才會刪除）。

## 品質檢查

有 `make` 時：

```bash
make check        # backend-check + frontend-check + docker-build
make help         # 列出所有 targets
```

沒有 `make`（例如 Windows）時的等效指令：

```bash
# 啟動 / 停止
docker compose up --build
docker compose down

# backend
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov
cd ..

# frontend
cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
cd ..

# backend image
docker build -t agentops-api ./backend

# 格式化 backend
cd backend
uv run ruff format .
uv run ruff check --fix .
```

## 文件

- [SPEC.md](SPEC.md)：產品與技術規格
- [PLAN.md](PLAN.md)：實作計畫與任務清單
- [DECISIONS.md](DECISIONS.md)：技術決策紀錄

## 授權

[MIT](LICENSE)
