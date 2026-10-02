# T3：Docker Compose、Makefile、CI

- Phase：0
- 依賴：T1（backend）、T2（frontend）已完成並 commit
- 相關文件：`SPEC.md` §1.2、§14.1、§16.3、§17、§19.1；`DECISIONS.md` D-008、D-010、D-011

## 背景 / 動機

把 T1、T2 串成一個指令就能在本機啟動的開發環境，並建立 GitHub Actions CI，讓之後每個 PR / push 都自動跑完 SPEC §16.3 的檢查項目。這是 Phase 0「本機三服務啟動、CI 綠燈」的最後一步。

## 具體需求

### 1. 環境變數範本（根目錄 `.env.example`）

- 內容與 SPEC §17.2 完全一致（同樣的 key、同樣的預設值、順序相同），所有秘密值留空。
- 不得建立或 commit 真正的 `.env`。

### 2. `.gitignore`（根目錄）

至少涵蓋：`.env`、`.env.*`（但保留 `!.env.example`、`!frontend/.env.example`）、Python（`.venv/`、`__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.coverage`、`htmlcov/`）、Node（`node_modules/`、`dist/`）、OS / IDE 雜檔。

### 3. `docker-compose.yml`（根目錄）

三個服務：

| 服務 | 來源 | Port | 重點 |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg17` | 5432 | `POSTGRES_USER=postgres`、`POSTGRES_PASSWORD=postgres`、`POSTGRES_DB=agentops`；named volume 持久化；`pg_isready` healthcheck |
| `backend` | build `./backend`（T1 的 Dockerfile） | 8000 | `PORT=8000`；`DATABASE_URL` 指向 `postgres` 服務；`depends_on: postgres: condition: service_healthy` |
| `frontend` | build `./frontend`，使用新增的 `frontend/Dockerfile.dev` | 5173 | 執行 Vite dev server，listen `0.0.0.0`；`VITE_API_BASE_URL=http://localhost:8000`（瀏覽器端存取，所以是 localhost） |

- 根目錄 `.env` 以 `env_file` 載入且標記為非必要（`required: false`），讓沒有 `.env` 時 `docker compose up --build` 仍可直接啟動。
- compose 內只能出現本機開發用的帳密（`postgres/postgres`），不得出現任何正式環境的秘密。
- `frontend/Dockerfile.dev`：基於 `node:24-slim`，`npm ci` 後執行 `npm run dev -- --host 0.0.0.0 --port 5173`。另建 `frontend/.dockerignore`（排除 `node_modules`、`dist`、`.env*`）。

### 4. `Makefile`（根目錄）

Targets（皆須可在 Linux / Git Bash + make 下執行）：

| Target | 行為 |
|---|---|
| `help` | 預設 target，列出所有 targets 與說明 |
| `up` | `docker compose up --build` |
| `down` | `docker compose down` |
| `backend-check` | 在 `backend/` 依序執行 ruff check、ruff format --check、mypy、pytest --cov |
| `frontend-check` | 在 `frontend/` 依序執行 lint、typecheck、test、build |
| `docker-build` | `docker build -t agentops-api ./backend` |
| `check` | `backend-check` + `frontend-check` + `docker-build` |
| `fmt` | backend `ruff format` + `ruff check --fix` |

不要加入後續 Phase 才有意義的 target（migrate、seed、smoke 等）。

### 5. CI（`.github/workflows/ci.yml`）

- 觸發：`pull_request`（任何 branch）與 `push` 到 `main`。
- `permissions: contents: read`；設定 `concurrency` 讓同一 ref 的舊 run 被取消。
- Jobs（可平行）：
  - `backend`：checkout → `astral-sh/setup-uv`（啟用 cache）→ 安裝 Python 3.12 → `uv sync --frozen` → ruff check → ruff format --check → mypy → pytest --cov。
  - `frontend`：checkout → `actions/setup-node`（Node 24，npm cache）→ `npm ci` → lint → typecheck → test → build。
  - `docker`：`docker build ./backend`（不 push）。
  - `secret-scan`：使用 gitleaks 掃描（`gitleaks/gitleaks-action@v2`，需要完整 git history：`fetch-depth: 0`）。
- 不使用任何 repository secret；此 workflow 不部署任何東西。
- 所有第三方 action 固定到 major version tag（例如 `@v4`）。

### 6. Dependabot（`.github/dependabot.yml`）

每週檢查：`uv`（directory `/backend`）、`npm`（directory `/frontend`）、`github-actions`（directory `/`）、`docker`（directory `/backend`）。

### 7. LICENSE 與 README

- `LICENSE`：MIT，著作權人 `new888`，年份 2026。
- `README.md`：此 task 只需包含：
  - 一句話產品定位。
  - 本機快速啟動（`docker compose up --build`，以及各服務網址）。
  - 不使用 make 時的等效指令（給 Windows 使用者）。
  - 品質檢查指令。
  - 指向 `SPEC.md`、`PLAN.md`、`DECISIONS.md`。
  - 不要寫尚未存在的功能、Demo 連結或部署說明。

## 驗收標準

1. `docker compose config` 在沒有 `.env` 的情況下成功。
2. `docker compose up --build` 啟動三個服務；`curl http://localhost:8000/health/ready` 回 `200` 且 `database: ok`；瀏覽器開 `http://localhost:5173` 顯示已就緒。
3. `docker compose down` 後再 `up`，postgres 資料 volume 仍存在。
4. `make check`（或 README 列出的等效指令）在本機全部通過。
5. `.github/workflows/ci.yml` 通過 YAML 語法檢查；push 至 GitHub 後四個 jobs 全綠（若 repo 尚未建立，回報中註明「CI 未在 GitHub 上實際執行」，不可宣稱綠燈）。
6. `git ls-files` 中沒有 `.env`（`.env.example` 除外）或任何含秘密的檔案。

驗收項 2、3、4 中需要 Docker 的部分，若 Docker daemon 未啟動，須在回報中註明未驗證項目，不可宣稱成功。

## 明確排除的範圍

- 不做 `render.yaml`、`wrangler.jsonc`、`deploy-frontend.yml`（T12）。
- 不做 migration 驗證、Alembic、seed（Phase 1 起）。
- 不修改 T1 / T2 的應用程式碼；如發現 T1 / T2 的問題導致無法驗收，在回報中列為「需要澄清的問題」。
- 不建立 GitHub repo、不 push（由 CEO 處理）。
