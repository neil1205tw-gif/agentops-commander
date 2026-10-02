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
