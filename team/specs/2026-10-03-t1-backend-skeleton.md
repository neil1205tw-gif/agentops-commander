# T1：Backend 骨架

- Phase：0
- 依賴：無
- 相關文件：`SPEC.md` §4.2、§5.1、§12.1、§14.1、§16.3、§18.2；`DECISIONS.md` D-008、D-009

## 背景 / 動機

建立 Python 後端的最小可執行骨架，後續所有 Phase 都在此基礎上擴充。這一步要先把設定管理、結構化 log（含敏感欄位遮罩）、資料庫連線、健康檢查與品質工具（lint / type check / test / Docker build）一次建好，讓之後每個 task 都能用同一套檢查。

## 具體需求

### 1. 專案與工具設定（`backend/pyproject.toml`）

- 使用 `uv` 管理，`requires-python = "==3.12.*"`，產生並 commit `uv.lock`。
- Runtime 相依（只加這些，不要預先加入 LangGraph、Alembic 等後續才用到的套件）：
  - `fastapi`、`uvicorn[standard]`、`pydantic>=2`、`pydantic-settings`、`structlog`、`sqlalchemy[asyncio]>=2`、`psycopg[binary,pool]>=3`
- Dev 相依：`ruff`、`mypy`、`pytest`、`pytest-asyncio`、`pytest-cov`、`httpx`（測試用 ASGI client）
- Ruff：`line-length = 100`，`target-version = "py312"`，lint rules 至少啟用 `E, F, W, I, B, UP, S, ASYNC`；tests 目錄可忽略 `S101`（assert）。
- mypy：`strict = true`，檢查 `app` 與 `tests`。
- pytest：`asyncio_mode = "auto"`；coverage 來源為 `app`，`fail_under = 80`。

### 2. 設定（`backend/app/config.py`）

- 以 `pydantic-settings` 定義 `Settings`，從環境變數讀取（亦可讀 `.env`，但檔案不存在時不得報錯）。
- 欄位對應 `SPEC.md` §17.2 的 `.env.example`，此 task 至少需要：
  - `APP_ENV`（`development | test | production`，預設 `development`）
  - `LOG_LEVEL`（預設 `INFO`）
  - `DATABASE_URL`（必填，`SecretStr`）
  - `CORS_ORIGINS`（逗號分隔字串，解析為 `list[str]`；預設 `http://localhost:5173`）
  - `PORT`（預設 `10000`，僅供參考，實際由 uvicorn 參數決定）
- 所有 key / secret / URL 含帳密的欄位一律使用 `SecretStr`，`repr()` 不得洩漏值。
- 提供 `get_settings()`（`lru_cache`）供 dependency injection 使用。

### 3. 結構化 log（`backend/app/logging.py`）

- 使用 `structlog`：`APP_ENV=production` 輸出 JSON，其他環境輸出易讀的 console 格式。
- 實作 redaction processor：event dict 中（含巢狀 dict）key 名稱符合下列任一者時，值替換為 `"[REDACTED]"`，比對不分大小寫：
  - `authorization`、`cookie`、`set-cookie`、`password`、`secret`、`token`、`api_key`、`apikey`、`database_url`、以及任何以 `_key`、`_secret`、`_token` 結尾的 key。
- 另外對字串值中出現的 `postgresql://user:password@...` / `postgresql+psycopg://...` 形式的連線字串，將帳密部分遮罩。
- 提供 `configure_logging(settings)`，在 app 啟動時呼叫。

### 4. 資料庫連線（`backend/app/db.py`）

- 使用 SQLAlchemy 2 async engine（driver：`postgresql+psycopg`），於 FastAPI lifespan 建立、關閉時 dispose。
- 提供 `check_database(engine) -> bool`：執行 `SELECT 1`，總時限 2 秒，逾時或任何例外回傳 `False`，並以 log 記錄錯誤類別（不可把連線字串寫進 log）。

### 5. App 與 health endpoints（`backend/app/main.py`、`backend/app/api/health.py`）

- `create_app() -> FastAPI` factory；模組層級 `app = create_app()` 供 uvicorn 使用。
- CORS middleware：`allow_origins` 只使用 `Settings.CORS_ORIGINS`，不得使用 `*`。
- Health endpoints 掛在根路徑（D-009），不加 `/api/v1`：
  - `GET /health/live` → `200 {"status": "ok"}`，不碰資料庫。
  - `GET /health/ready`：
    - DB 正常 → `200 {"status": "ready", "checks": {"app": "ok", "database": "ok"}}`
    - DB 失敗 → `503 {"status": "not_ready", "checks": {"app": "ok", "database": "error"}}`
    - 回應不得包含例外訊息、連線字串或任何內部細節。
    - 不得呼叫任何 LLM。
- 預留 `/api/v1` router（`app/api/router.py`），此 task 不在其下放任何 endpoint。

### 6. Dockerfile（`backend/Dockerfile`）

- Multi-stage：builder 階段用 `uv sync --frozen --no-dev` 安裝相依；runtime 階段基於 `python:3.12-slim`。
- 以非 root 使用者執行。
- 不得把 `.env` 或任何秘密複製進 image；建立 `backend/.dockerignore`（至少排除 `.env*`、`.venv`、`__pycache__`、`.pytest_cache`、`.mypy_cache`、`tests`）。
- `CMD` 與 SPEC §18.2 一致：
  `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]`

### 7. 測試（`backend/tests/`）

至少包含：

- `test_health.py`：
  - `/health/live` 回 200。
  - `/health/ready` 在 DB check 成功時回 200 與正確 body（以 dependency override 或 monkeypatch 替換，不需資料庫連線）。
  - `/health/ready` 在 DB check 失敗時回 503，且 body 不含例外訊息。
- `test_logging.py`：各類敏感 key（含巢狀、大小寫變化）與連線字串會被遮罩；一般欄位不受影響。
- `test_config.py`：`CORS_ORIGINS` 逗號分隔解析；`SecretStr` 欄位的 `repr` 不含原值。
- `test_db.py`：`check_database` 在 engine 拋例外或逾時時回傳 `False`。

## 驗收標準

在 `backend/` 目錄下全部通過：

1. `uv sync` 成功，`uv.lock` 已 commit。
2. `uv run ruff check .` 無錯誤。
3. `uv run ruff format --check .` 無差異。
4. `uv run mypy app tests` 無錯誤（strict）。
5. `uv run pytest --cov` 全數通過，coverage ≥ 80%。
6. `DATABASE_URL=postgresql+psycopg://x:y@127.0.0.1:1/none uv run uvicorn app.main:app --port 8000` 可啟動；`/health/live` 回 200、`/health/ready` 回 503（因為 DB 連不到），且 log 中不出現 `x:y`。
7. `docker build -t agentops-api ./backend` 成功（需 Docker daemon；若本機 daemon 未啟動，在回報中註明未驗證，不可宣稱成功）。

## 明確排除的範圍

- 不做 Alembic、資料表、models、repositories。
- 不做 JWT / Auth / RBAC。
- 不做 LangGraph、LLM adapter、任何 Agent 相關程式。
- 不做 `/api/v1` 下的任何業務 endpoint。
- 不做 docker-compose、Makefile、`.env.example`、CI（屬於 T3）。
- 不做前端。
