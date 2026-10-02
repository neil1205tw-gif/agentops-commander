# AGENTS.md

給參與本專案的 AI agent（特別是 Codex Reviewer）閱讀的專案慣例。

## 專案

AgentOps Commander — Python multi-agent incident response 專案。產品規格見 `SPEC.md`，與規格不同或規格未明示的決策見 `DECISIONS.md`（DECISIONS 優先於 SPEC），進度見 `PLAN.md`。

## 任務規格與審核

- 每個實作任務都有一份 task spec：`team/specs/<YYYY-MM-DD>-<slug>.md`，包含背景、需求、驗收標準、排除範圍。
- 審核 commit 時，請依 commit 訊息或變更內容找出對應的 task spec，以其「驗收標準」與「明確排除的範圍」為主要審查依據；超出 task spec 範圍的建議請標為 Minor / 建議。
- 審核結論請依嚴重度分級：Critical / Major / Minor，並附檔案與行號。

## 不可違反的規則

- 所有基礎設施操作工具（restart、rollback 等）都是 deterministic simulator，不得呼叫真實 shell、Docker socket 或雲端 API。
- 秘密只能透過環境變數注入；不得寫入 repository、Docker image、前端 bundle 或 log。Log 必須 redact authorization、cookie、API key、database URL。
- 不得在 UI、log、API 回應中顯示或儲存 raw chain-of-thought，只有 `decision_summary`。
- 高風險工具未經人工核准不得執行。
- 禁止 `eval()`、任意 shell execution、字串串接 SQL。
- 不得留下 placeholder、TODO、空函式或假資料畫面。
- Agent orchestration 必須是 Python。

## 結構

- `backend/`：Python 3.12、FastAPI、uv 管理（`uv run ...`）。檢查：`ruff check`、`ruff format --check`、`mypy`、`pytest --cov`。
- `frontend/`：React + Vite + TypeScript strict、npm。檢查：`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`。
