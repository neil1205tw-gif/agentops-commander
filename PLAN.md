# PLAN

產品規格：[SPEC.md](SPEC.md)　決策紀錄：[DECISIONS.md](DECISIONS.md)

執行流程：CEO 撰寫 task spec（`team/specs/`）→ Coder 實作並 commit → Codex 審核（`team/reviews/`）→ 通過後標記完成。每個 Phase 結束後與老闆確認才進入下一個 Phase（D-003）。

狀態：`todo` / `spec` (spec 已寫、待派工) / `doing` / `review` / `done` / `blocked`

---

## Phase 0：骨架與規範

驗收：本機三服務（frontend、backend、postgres）以 `docker compose up --build` 啟動；CI 綠燈。

| Task | 內容 | 依賴 | Spec | 狀態 |
|---|---|---|---|---|
| T1 | Backend 骨架：FastAPI、config、structlog + redaction、DB 連線、`/health/live`、`/health/ready`、ruff/mypy/pytest、Dockerfile | — | [t1](team/specs/2026-10-03-t1-backend-skeleton.md) | done（review r1 退回 1 次，r2 通過）|
| T2 | Frontend 骨架：Vite/React/TS strict、Tailwind、Router、TanStack Query、ESLint、Vitest、冷啟動 readiness 輪詢、Landing | — | [t2](team/specs/2026-10-03-t2-frontend-skeleton.md) | done（review r1 僅 1 則 P2，經 CEO 判斷為誤判，詳見回報）|
| T3 | docker-compose、Makefile、`.env.example`、`.gitignore`、CI workflow、Dependabot、LICENSE、README 快速啟動 | T1, T2 | [t3](team/specs/2026-10-03-t3-compose-ci.md) | done（review r1 僅 1 則 P2 README 指令路徑，已由 CEO 修正）|

外部前置：老闆啟動 Docker Desktop。GitHub repo：https://github.com/neil1205tw-gif/agentops-commander

## Phase 1：資料、情境與身分

驗收：登入 dev 帳號後建立 incident，可在 UI 清單與詳情頁查看；Viewer 無法建立。

| Task | 內容 | 依賴 | Spec | 狀態 |
|---|---|---|---|---|
| T4 | Alembic、三張核心表（profiles / incidents / incident_events）、RLS 全拒、async repositories、compose `migrate` 服務、CI Postgres service | T3 | [t4](team/specs/2026-10-03-t4-db-schema.md) | done（review r1 無問題）|
| T5 | Scenario registry（metadata）、JWT 驗證（Supabase JWKS + dev HS256）、RBAC、`/auth/*`、`/me`、`/scenarios`、`set_role` 腳本 | T4 | [t5](team/specs/2026-10-03-t5-auth-scenarios.md) | done（review r1 無問題）|
| T6 | Incident CRUD API（可見性規則、軟刪除、events、visibility）| T5 | [t6](team/specs/2026-10-03-t6-incident-api.md) | done（review r1 無問題）|
| T7 | 前端：登入（dev 按鈕）、受保護路由、incidents 清單 / 建立 / 詳情 | T6 | [t7](team/specs/2026-10-03-t7-frontend-incidents.md) | done（review r1 兩個 P2 已修正，r2 通過；瀏覽器端流程已實測）|

## Phase 2：工具與 Timeline

驗收：可手動觸發 read-only tool 並看到 audit event 出現在 Timeline。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T8 | 全部工具（read-only / low / high，含 scenario 的 metrics / logs / deployments 資料）、Pydantic I/O、risk level、allowlist、`tool_executions` audit、idempotency | T7 | todo |
| T9 | Timeline 與 Evidence Panel UI | T8 | todo |

## Phase 3：LangGraph

驗收：FakeLLM 可完整跑三個 scenario（高風險步驟此階段先以 policy 停在 `awaiting_approval` 狀態）。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T10 | `IncidentAgentState`、graph、各 node、routing 規則、bounded retries / step limit、`LLMProvider`（Gemini、Anthropic、Fake）、run API | T8 | todo |

## Phase 4：RAG 與記憶

驗收：Runbook 回應有可點擊來源；重啟 backend 後可恢復 thread。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T11 | pgvector、≥6 份 Runbook、chunking、ingestion、retrieval（filter + vector）、citation、最低分數門檻、長期記憶（相似 incident） | T10 | todo |
| T12 | `AsyncPostgresSaver` checkpointer、setup 流程、thread 恢復 | T10 | todo |

## Phase 5：HITL

驗收：restart/rollback 未批准前絕不執行；批准後不重跑前置節點。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T13 | deterministic risk policy、`interrupt()` / `Command(resume=...)`、approval API（approve/reject/edit）、Approval Card UI、`/approvals` 頁 | T12 | todo |
| T14 | SSE 串流（event types、heartbeat、Last-Event-ID 補回）、前端即時 Timeline 與斷線重連 | T13 | todo |

## Phase 6：Auth、安全與評測

驗收：100% 攔截 high-risk；越權 approval 回 403。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T15 | Supabase Auth 前端串接、RLS policy tests、rate limit、prompt injection 防護測試、15 個 evaluation cases、`/evaluations` 頁 | T14 | todo |

## Phase 7：部署與文件包裝

驗收：公開網域可完成至少一個 scenario；另有錄影備援。

| Task | 內容 | 依賴 | 狀態 |
|---|---|---|---|
| T16 | `render.yaml`、`wrangler.jsonc`、deploy-frontend workflow、`make migrate-prod`、smoke test、README / docs / demo script | T15 | todo |

外部前置（老闆手動）：Render 帳號、Supabase project、Cloudflare Worker custom domain 與 DNS、各平台 secrets。

---

## 已降級為 P2（D-007）

- Playwright E2E
- OpenAIProvider
