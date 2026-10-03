# DECISIONS

記錄 SPEC.md 未明示、或與 SPEC.md 原文不同的實作決策。格式：編號、日期、決策、理由、影響範圍。

---

## D-001 執行流程以團隊流程為準（2026-10-03）

- **決策**：SPEC.md 僅作為產品需求與驗收依據。SPEC §1.1「不要停下詢問」與 §25 啟動 Prompt 不採用；實際執行走 CLAUDE.md 的 CEO → Coder → Codex Reviewer 流程，每張 task spec 存於 `team/specs/`，審核報告存於 `team/reviews/`。
- **理由**：專案採多 Agent 團隊分工與交叉審核。
- **影響**：PLAN.md 以 task（T1–T12）為單位追蹤。

## D-002 Repository 根目錄即專案根目錄（2026-10-03）

- **決策**：不建立 SPEC §6 的外層 `agentops-commander/` 資料夾；`backend/`、`frontend/`、`docs/` 等直接放在 repo 根目錄。
- **理由**：repo 本身即為此專案，多一層目錄無意義。

## D-003 每個 Phase 完成後停下與老闆確認（2026-10-03）

- **決策**：每個 Phase 的所有 task 通過審核後，CEO 回報老闆並等待確認，才進入下一個 Phase。
- **影響**：Phase 間不自動推進。

## D-004 JWT 驗證與 RBAC 提前到 Phase 1（2026-10-03）

- **決策**：
  - 後端同時支援兩種 JWT 驗證來源：
    1. Supabase Auth（JWKS 非對稱簽章驗證，正式環境）。
    2. 本機自簽 HS256（僅 `APP_ENV=development` 啟用），提供 dev-login endpoint 與 seed 的 demo 帳號（viewer / operator / admin）。
  - `APP_ENV=production` 時，本機簽發與 dev-login 必須完全停用。
  - Phase 1（T4）即實作 JWT 驗證、角色與 ownership；Phase 6 僅補 Supabase 正式串接、RLS policy tests、rate limit。
- **理由**：Phase 1 起所有 API 都需要 `owner_id` 與角色；本機 docker compose 沒有 Supabase Auth。這是可運作的驗證機制而非 placeholder。

## D-005 Alembic 為唯一 schema 來源；RLS 預設全拒（2026-10-03）

- **決策**：
  - 所有 application schema 由 `backend/alembic` 管理；`supabase/` 目錄只放 `config.toml` 與 RLS policy tests，不放 schema migrations。
  - 所有 public tables 啟用 RLS，且不對 `anon` / `authenticated` 建立任何允許 policy（預設全拒）。若這些 role 存在（Supabase 環境），一併 revoke 其 table 權限。
  - 前端只使用 Supabase Auth，不直接查詢資料表；資料存取權限（含「Viewer 只讀公開 demo incidents」）由後端 RBAC + ownership 檢查強制執行。
- **理由**：避免 Alembic 與 Supabase migrations 雙軌衝突；本機 pgvector image 無 `auth.uid()` 與 Supabase roles。
- **取捨**：SPEC §11.3 的細緻 row-level 規則改由後端強制，而非 DB policy。

## D-006 向量維度 768（2026-10-03）

- **決策**：`runbook_chunks.embedding` 與 `historical_incidents.embedding` 使用 `vector(768)`。Gemini embedding 指定輸出 768 維；FakeLLM 使用確定性 hashing embedding，同樣輸出 768 維。

## D-007 範圍調整（2026-10-03）

- **決策**：以下項目從 P1 降為 P2（有餘力再做）：
  - Playwright E2E（前端改以 Vitest + RTL 覆蓋 SPEC §16.2 項目）。
  - `OpenAIProvider`（保留 `LLMProvider` Protocol 擴充性，只實作 Gemini、Anthropic、Fake）。

## D-008 工具鏈（2026-10-03）

- **決策**：
  - Backend：Python 3.12（由 `uv` 管理，不使用系統 Python）、`uv.lock` 作為 dependency pinning。
  - Frontend：Node 24 LTS、npm、`package-lock.json`。
  - 交付 Makefile（SPEC 要求、CI 在 Linux 上可用）；Windows 本機需自行安裝 make（例如 `winget install ezwinports.make`）。
- **理由**：uv 可在不影響系統 Python 3.14 的情況下固定 3.12。

## D-009 Health endpoints 不加 `/api/v1` 前綴（2026-10-03）

- **決策**：`GET /health/live`、`GET /health/ready` 掛在根路徑；其他業務 API 一律在 `/api/v1` 下。
- **理由**：SPEC §18.2 的 Render `healthCheckPath: /health/ready` 為根路徑。

## D-010 本機 Postgres image（2026-10-03）

- **決策**：docker compose 使用 `pgvector/pgvector:pg17`。
- **理由**：Supabase 新專案為 Postgres 17，本機版本對齊以減少差異。

## D-011 授權條款（2026-10-03）

- **決策**：LICENSE 採 MIT。

## D-012 網域與 GitHub repo（2026-10-03）

- **決策**：
  - 正式網域為 `gameteacafe.com`（與 SPEC §3.5 一致）。
  - GitHub repo：`neil1205tw-gif/agentops-commander`（public）。
  - Commit email 使用 GitHub noreply（`295154177+neil1205tw-gif@users.noreply.github.com`），不公開個人 email；設定於本 repo 的 local git config。

## D-013 Phase 1 只建三張資料表（2026-10-03）

- **決策**：Phase 1 的 Alembic migration 只建立 `profiles`、`incidents`、`incident_events`。其餘 SPEC §11.1 的資料表，在用到它們的 Phase 才各自加入 migration。
- **理由**：一次建 12 張表，其中多數在好幾個 Phase 內都是空的，等同 placeholder。
- **同時**：Phase 1 拆為 T4（資料庫）、T5（身分與情境）、T6（Incident API）、T7（前端），後續任務編號順延（見 PLAN.md）。

## D-014 以 text + CHECK 取代 PostgreSQL enum；profiles.email 可為 null（2026-10-03）

- **決策**：role、status、severity 等列舉欄位使用 `text` + CHECK constraint。`profiles.email` 允許 null（部分 JWT 不帶 email），非 null 時以 `lower(email)` 唯一。
- **理由**：PostgreSQL enum 在 Alembic 中新增值需要額外處理，不利後續 Phase 迭代。

## D-015 Incident 可見性規則（2026-10-03）

- **決策**：
  - viewer 只能讀取 `is_public` 的 incident；operator 讀取自己的加上公開的；admin 讀取全部；已軟刪除的對所有人不可見。
  - 對不存在與無權限的 incident 一律回 404，不以 403 洩漏存在性。
  - `is_public` 預設 false，只有 admin 可修改。公開範例等 Phase 3 能完整執行 Agent 流程後，以完整流程產生再公開，Phase 1 不預先塞入資料；Viewer 在 Phase 1 看到空清單屬預期。
- **理由**：落實 SPEC §2.5、§11.3，並因 RLS 預設全拒（D-005）而由後端強制。

## D-016 Scenario fixtures 在 Phase 1 只含 metadata（2026-10-03）

- **決策**：情境 JSON 只有 key、名稱、描述、預設 title、服務、告警摘要與症狀。metrics / logs / deployments 在 Phase 2 實作工具時與工具 schema 一併設計。
- **理由**：避免工具資料格式改兩次。

## D-017 身分與角色的實作細節（2026-10-03）

- **決策**：
  - 角色只以資料庫 `profiles.role` 為準，不讀 JWT 內任何 role claim。
  - 首次帶有效 JWT 呼叫 API 的使用者自動建立 profile，預設角色 viewer；升級用 `scripts/set_role.py`。
  - 本機登入為 `POST /api/v1/auth/dev-login`（僅 development / test 註冊路由），由前端以三顆按鈕觸發；它會以固定 UUID upsert 三個 demo profile，因此不另做 seed script。
  - Supabase 路徑只接受非對稱簽章（RS256 / ES256）；dev 路徑只接受 HS256 且 issuer 為 `agentops-dev`；兩條路徑不互通（防 algorithm confusion）。
  - JWKS 驗證以測試內產生的金鑰對測試，不依賴線上的 Supabase 專案（Phase 6 才串接）。
  - Production 啟動必須有 `SUPABASE_URL` 與 `JWT_ISSUER`，且完全不接受 dev token。
  - dev JWT 預設有效 8 小時；`DEV_AUTH_SECRET` 在 development / test 有內建預設，不用於 production。

## D-018 Migration 執行方式（2026-10-03）

- **決策**：本機 compose 新增一次性 `migrate` 服務（`alembic upgrade head`），backend 等它成功結束才啟動。正式環境照 SPEC 用手動的 `make migrate-prod`（Phase 7 實作），app 啟動時不自動 migration。
- DB 測試使用 `TEST_DATABASE_URL`，每次建立隨機名稱的暫時資料庫並執行 migration；本機未設定時 skip，CI（`CI=true`）未設定則視為失敗。CI 的 backend job 以 Postgres service container 執行。

## D-019 Incident 行為細節（2026-10-03）

- **決策**：
  - incident 建立時 `status=open`、`severity=null`（由 Phase 3 triage 填入）。
  - 刪除為軟刪除（`deleted_at`），相關 `incident_events` 保留；`incident_events` 以 DB trigger 禁止 UPDATE / DELETE（append-only）。
  - 每個寫入操作與其事件在同一交易內完成。
  - 建立 incident 的 `title` 省略時使用情境的 `default_title`。
