# T5：情境 registry、JWT 驗證與 RBAC

- Phase：1
- 依賴：T4
- 相關文件：`SPEC.md` §2.5、§9、§12.2、§14.1；`DECISIONS.md` D-004、D-016、D-017、D-019

## 背景 / 動機

所有業務 API 都需要知道「誰在呼叫、是什麼角色」。這一步建立可驗證的身分機制（D-004）：正式環境驗證 Supabase 簽發的 JWT，本機開發則提供受限的 dev 登入。同時建立三個 demo 情境的 metadata registry，供建立 incident 使用。

## 具體需求

### 1. 設定（`app/config.py`）

新增欄位（皆對應 `.env.example` 既有或新增的 key）：
- `SUPABASE_URL: str = ""`
- `JWT_ISSUER: str = ""`、`JWT_AUDIENCE: str = "authenticated"`
- `DEV_AUTH_SECRET: SecretStr`：`development` 與 `test` 環境預設為固定開發用字串（長度 ≥ 32，註明僅供本機）；`production` 環境**不使用**此值。
- `DEV_JWT_TTL_SECONDS: int = 28800`（8 小時）

驗證規則（Settings validator）：
- `APP_ENV=production` 時，`SUPABASE_URL` 與 `JWT_ISSUER` 必須非空，否則啟動失敗，錯誤訊息只說明缺少哪個欄位名稱。
- 派生屬性 `dev_auth_enabled: bool`：僅當 `APP_ENV in {development, test}` 為 True。
- 同步更新根目錄 `.env.example`：補上 `DEV_AUTH_SECRET=`（空白，說明 development 會使用內建預設）、`DEV_JWT_TTL_SECONDS=28800`。

### 2. Token 驗證（`app/auth/`）

使用 `pyjwt[crypto]`。提供：

- `TokenVerifier`：`verify(token: str) -> AuthClaims`，`AuthClaims` 含 `sub: UUID`、`email: str | None`、`source: "supabase" | "dev"`。
- **Supabase 路徑**：
  - 只接受非對稱演算法（`RS256`、`ES256`），從 header 取 `kid`，經 `JWKSProvider` 取得公鑰。
  - `JWKSProvider` 為可替換介面；預設實作自 `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` 取得 JWKS，快取（TTL 10 分鐘，遇到未知 `kid` 時最多重新抓取一次，且有最短間隔避免被濫用打爆）。逾時 5 秒。
  - 驗證 `iss == JWT_ISSUER`、`aud == JWT_AUDIENCE`、`exp`（必須存在）、`sub` 為合法 UUID。
- **Dev 路徑**（僅 `dev_auth_enabled` 時啟用）：
  - 只接受 `HS256`，用 `DEV_AUTH_SECRET` 驗證，`iss == "agentops-dev"`，`aud == JWT_AUDIENCE`，`exp` 必須存在。
- 決定走哪條路徑時，**只依** header 的 `alg` 與設定，不得依 token 內容自行宣告的其他欄位放寬規則。明確拒絕：`alg=none`、HS* 簽的 token 走 Supabase 路徑（防止 algorithm confusion）、dev 路徑被關閉時的 HS256 token。
- 任何驗證失敗一律回傳統一的 401（`{"detail": "Invalid or expired token"}`），含 `WWW-Authenticate: Bearer` header；不得在回應或 log 中洩漏 token 內容或失敗細節以外的資訊（log 只記錄失敗類別，例如 `expired`、`bad_signature`、`bad_audience`）。

### 3. Current user 與 RBAC

- Dependency `get_current_user`：解析 `Authorization: Bearer ...` → 驗證 → 以 `sub` 查 `profiles`；**不存在則自動建立**（role=`viewer`，`email` 取自 claim，`display_name` 為空）。角色**只**以資料庫 `profiles.role` 為準，絕不讀取 JWT 中的任何 role claim。
- 併發首次登入的 profile 建立必須安全（`INSERT ... ON CONFLICT DO NOTHING` 後重新讀取）。
- `CurrentUser` 模型：`id`、`email`、`display_name`、`role`。
- `require_role(*roles)` dependency factory，角色階層 `admin ⊃ operator ⊃ viewer`（`require_role("operator")` 允許 operator 與 admin）。角色不足回 `403 {"detail": "Insufficient role"}`；未帶 token 或 token 無效回 401。
- `dev_auth_enabled` 為 False 時，任何以 dev 路徑簽發的 token 一律 401。

### 4. Endpoints（`/api/v1`）

- `GET /auth/config`（公開）→ `{"dev_login_enabled": bool}`。
- `POST /auth/dev-login`（**僅當 `dev_auth_enabled` 才註冊此路由**；production 下此路徑回 404）：body `{"role": "viewer"|"operator"|"admin"}`。以固定 UUID 對應三個 demo 帳號（`demo-viewer@agentops.local` 等，UUID 以常數定義在程式碼中），使用 `ProfileRepository.upsert_demo` 建立或更新 profile，簽發 dev JWT（`sub` 為該 UUID，`email`、`iss=agentops-dev`、`aud`、`exp = now + DEV_JWT_TTL_SECONDS`），回傳 `{"access_token": "...", "token_type": "bearer", "expires_in": ...}`。
- `GET /me`（需登入）→ `{"id", "email", "display_name", "role"}`。
- `GET /scenarios`（需登入，任何角色）→ 三個情境的 metadata 列表。

### 5. Scenario registry（`app/scenarios/`）

- 三個情境的資料以 JSON fixture 存放於 `app/scenarios/fixtures/`（`cpu_spike_after_deploy.json`、`db_pool_exhaustion.json`、`duplicate_alert_storm.json`），啟動時載入並以 Pydantic model 驗證（`Scenario`）；任何 fixture 格式錯誤則啟動失敗。
- 欄位：`key`、`name`、`description`、`default_title`、`affected_services: list[str]`、`alert: {summary: str, source: str, fired_at_offset_minutes: int, symptoms: list[str]}`。內容依 `SPEC.md` §9 三個情境的服務與告警描述撰寫（服務名稱：`checkout-api`、`student-portal-api`、`notification-worker`）。
- 本 task **只**放 metadata；metrics / logs / deployments 等工具資料留到 Phase 2（D-016）。
- Registry API：`get(key) -> Scenario | None`、`all() -> list[Scenario]`、`service_names()`（所有已註冊服務名稱集合）。key 固定為 `cpu_spike_after_deploy`、`db_pool_exhaustion`、`duplicate_alert_storm`。

### 6. 管理腳本

- `backend/scripts/set_role.py`：`uv run python -m scripts.set_role <email 或 uuid> <viewer|operator|admin>`，使用既有 `DATABASE_URL` 連線更新 `profiles.role`；找不到使用者時以非零 exit code 結束並輸出明確訊息；不得印出連線字串。供正式環境把 demo operator 升級使用。（`scripts/` 需可被 `python -m` 匯入，並納入 mypy / ruff 檢查。）

### 7. 測試

- Token 驗證：以測試內動態產生的 RSA 與 EC key pair 與測試用的 `JWKSProvider` 覆蓋：合法 token、過期、錯誤 issuer、錯誤 audience、缺 `exp`、`sub` 非 UUID、未知 `kid`、`alg=none`、HS256 token 走 Supabase 路徑被拒、dev 路徑關閉時 dev token 被拒。
- JWKS 快取行為（TTL、未知 kid 重新抓取有間隔限制）。
- `get_current_user`：自動建立 profile（預設 viewer）、角色只依 DB（JWT 內塞 `role: admin` claim 無效）、併發首次登入不重複建立。
- `require_role` 階層與 401 / 403 區分。
- Endpoints：`/auth/config`、`/auth/dev-login`（development 可用、production 設定下路由不存在回 404）、`/me`、`/scenarios`。
- Scenario registry 載入與驗證、fixture 損壞時啟動失敗。
- `set_role` 腳本主要流程。
- Production 設定缺 `SUPABASE_URL` / `JWT_ISSUER` 時 Settings 建構失敗。
- 覆蓋率：整體 ≥ 80%，`app/auth/` ≥ 90%。

## 驗收標準

1. `backend/` 下 ruff、format、mypy、pytest --cov 全數通過。
2. `docker compose up --build` 後：
   - `POST /api/v1/auth/dev-login`（role=operator）取得 token，`GET /api/v1/me` 以該 token 回傳 operator；不帶 token 回 401。
   - `GET /api/v1/scenarios` 回三個情境。
3. 以 `APP_ENV=production` 啟動（提供測試用的 `SUPABASE_URL`、`JWT_ISSUER`）：`POST /api/v1/auth/dev-login` 回 404；以 dev 簽法自製的 HS256 token 呼叫 `/me` 回 401。（回報中附實際指令與輸出摘要。）
4. 在 log、API 回應中搜尋，不得出現 token 內容或 `DEV_AUTH_SECRET` 的值。

## 明確排除的範圍

- 不做 incident 相關 endpoint（T6）。
- 不做前端（T7）。
- 不做 Supabase 前端登入串接、不連線 Supabase 專案（Phase 6）。
- 不做 rate limit（Phase 6）。
- 不做 scenario 的 metrics / logs / deployments 資料。
- 不做 seed script（dev-login 會自行建立 demo profile，見 D-017）。
