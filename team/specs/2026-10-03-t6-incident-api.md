# T6：Incident CRUD API

- Phase：1
- 依賴：T5
- 相關文件：`SPEC.md` §2.5、§11.3、§12.3；`DECISIONS.md` D-015、D-018、D-019

## 背景 / 動機

提供建立、查詢、軟刪除 incident 的後端 API，並在後端強制執行角色與 ownership 規則（因為 RLS 預設全拒，所有資料存取授權都由後端負責，D-005）。

## 具體需求

所有 endpoint 位於 `/api/v1`，需登入（401 / 403 語意同 T5）。

### 1. 可見性規則（集中成單一函式，所有 endpoint 共用）

| 角色 | 可讀取的 incident（且 `deleted_at is null`） |
|---|---|
| viewer | 僅 `is_public = true` |
| operator | 自己擁有的，加上 `is_public = true` |
| admin | 全部 |

- 對「不存在」與「存在但看不到」的 incident，一律回 `404`，不得以 403 洩漏其存在。

### 2. Endpoints

**`POST /incidents`**（operator、admin；viewer 回 403）
- body：`{"scenario_key": str, "title": str | null}`。
- `scenario_key` 必須存在於 registry，否則 `422`。`title` 省略或空白時使用 scenario 的 `default_title`；長度 1–200，去除前後空白。
- 建立 incident：`owner_id` 為目前使用者、`status=open`、`severity=null`、`affected_services` 取自 scenario、`is_public=false`。
- 同一個資料庫交易內寫入一筆 `incident_events`：`event_type="incident.created"`、`agent_name=null`、`summary="Incident created from scenario <key>"`、`payload` 包含 `scenario_key` 與 `created_by`（user id）。
- 回 `201` 與 incident 詳細內容。

**`GET /incidents`**
- Query：`status`（選填，須為合法 status，否則 422）、`limit`（預設 20，範圍 1–100）、`offset`（預設 0，≥ 0）。
- 依可見性規則過濾，`created_at desc, id desc` 排序。
- 回 `{"items": [...], "total": int, "limit": int, "offset": int}`；`items` 為列表摘要（`id`、`title`、`scenario_key`、`severity`、`status`、`affected_services`、`is_public`、`owner_id`、`created_at`、`updated_at`）。

**`GET /incidents/{incident_id}`**
- 回詳細內容：列表摘要欄位加 `resolved_at`，以及 `alert`（取自 scenario registry 的 `alert` 內容，若 scenario 已不存在則為 `null`）。
- `incident_id` 非合法 UUID → `422`（FastAPI 預設）。

**`GET /incidents/{incident_id}/events`**
- 同可見性規則；回 `{"items": [{id, event_type, agent_name, summary, payload, created_at}]}`，依 `created_at asc, id asc`。

**`DELETE /incidents/{incident_id}`**
- 軟刪除（設定 `deleted_at`）。擁有者本人或 admin 可執行；operator 刪除他人 incident 時，若該 incident 對他可見（公開）回 `403`，不可見回 `404`；viewer 一律 `403`。
- 成功回 `204`；已被刪除的 incident 再刪回 `404`。
- 刪除時同一交易寫入 `incident_events`（`incident.deleted`）。事件資料保留，不刪除。

**`PATCH /incidents/{incident_id}/visibility`**（僅 admin；其他角色 `403`，不存在 `404`）
- body：`{"is_public": bool}`；更新並寫入 `incident_events`（`incident.visibility_changed`，payload 含新舊值與操作者）；回更新後的詳細內容。

### 3. 實作要求

- 授權判斷集中在 service 層（例如 `app/services/incidents.py`），router 只負責解析與回應；repositories 不含授權邏輯。
- 所有輸入以 Pydantic schema 驗證（`app/schemas/`）；回應使用明確的 response model，不得直接回傳 ORM 物件。
- 每次寫入操作與其 `incident_events` 必須在同一交易內，失敗則一併 rollback。
- `title` 等使用者輸入原樣儲存（不做 HTML 轉義，轉義由前端渲染層負責），但不得被串接進任何 SQL 或 log 的格式字串。
- 在 `app/api/router.py` 掛載新的 router，路徑與方法完全依上列。

### 4. 測試

使用 T4 的測試資料庫 fixture 與 T5 的 dev-token 輔助方法。至少涵蓋：
- 每個 endpoint 對 viewer / operator / admin / 未登入的權限矩陣（含 401、403、404 的區分）。
- 可見性：viewer 看不到私有 incident（回 404）；operator 看不到他人私有 incident，但看得到他人公開的；admin 看得到全部；soft-deleted 對所有人（含 admin 的 list / get）不可見。
- 建立：預設 title、自訂 title、空白 title、過長 title、未知 scenario、`created` 事件確實寫入、`affected_services` 來自 scenario。
- 分頁：`limit` / `offset` / `total`、排序穩定性、非法參數 422。
- `status` filter。
- 刪除：擁有者、admin、他人、viewer、重複刪除；事件保留。
- `PATCH visibility`：僅 admin；事件寫入；viewer 在設為公開後能看到、設回私有後看不到。
- 交易一致性：寫入事件失敗時 incident 不會殘留（可用 monkeypatch 讓 `IncidentEventRepository.append` 拋例外）。
- 覆蓋率：整體 ≥ 80%，`app/services/incidents.py` 與 incidents router ≥ 90%。

## 驗收標準

1. `backend/` 下 ruff、format、mypy、pytest --cov 全數通過。
2. `docker compose up --build` 後以 `curl` 完成以下流程並附輸出摘要：
   - dev-login 取得 operator token → `POST /incidents`（三個 scenario 各建一筆）→ `GET /incidents` 看到三筆 → `GET /incidents/{id}` 與 `/events` 正確。
   - dev-login 取得 viewer token → `GET /incidents` 回空清單、`POST /incidents` 回 403、直接 GET operator 的 incident id 回 404。
   - dev-login 取得 admin token → `PATCH visibility` 設為公開 → viewer 現在可見。
   - operator `DELETE` 自己的 incident 回 204，之後 GET 回 404。
3. 瀏覽器 origin `http://localhost:5173` 呼叫上述需要 `Authorization` header 的 endpoint（含 DELETE / PATCH）的 CORS preflight 回應正確。

## 明確排除的範圍

- 不做前端（T7）。
- 不做 run / agent / tool 相關 API（後續 Phase）。
- 不做 `severity` 與 `status` 的自動轉移（Phase 3 由 agent 流程更新）。
- 不做 rate limit。
- 不做 incident 的編輯（title 修改等）。
