# T2：Frontend 骨架與冷啟動狀態

- Phase：0
- 依賴：無（後端 API 只需要 `GET /health/ready`，介面見 T1）
- 相關文件：`SPEC.md` §3.4、§5.2、§13.1、§13.3、§22 AC-06；`DECISIONS.md` D-008

## 背景 / 動機

前端最終部署在 Cloudflare 靜態資產，後端在 Render Free（閒置會休眠，冷啟動 30–90 秒）。前端骨架除了建立工具鏈之外，要先把「後端尚未 ready」的處理做好：輪詢 `/health/ready`、顯示暖機狀態與倒數、ready 後自動恢復，不顯示 generic network error，也不需要使用者重新整理頁面（AC-06）。

## 具體需求

### 1. 專案與工具鏈（`frontend/`）

- Vite + React 19 + TypeScript，`tsconfig` 開啟 `strict: true`，並開啟 `noUncheckedIndexedAccess`。
- npm 管理，commit `package-lock.json`。
- 相依：`react-router`（v7，library/SPA 模式即可）、`@tanstack/react-query`、`tailwindcss` v4（`@tailwindcss/vite`）。
- 不要加入 Supabase JS、shadcn/ui 或其他目前用不到的套件。
- ESLint flat config：`typescript-eslint`（type-aware 規則）、`eslint-plugin-react-hooks`、`eslint-plugin-react-refresh`。
- Vitest + `@testing-library/react` + `@testing-library/user-event` + `jsdom`。
- `package.json` scripts（名稱固定，CI 會使用）：
  - `dev`、`build`（`tsc -b && vite build`）、`preview`
  - `lint`（`eslint .`，有 warning 也視為失敗：`--max-warnings 0`）
  - `typecheck`（`tsc -b --noEmit` 或等效）
  - `test`（`vitest run`）

### 2. 設定（`frontend/src/lib/config.ts`）

- 從 `import.meta.env.VITE_API_BASE_URL` 讀取 API base URL；未設定時預設 `http://localhost:8000`。去除結尾斜線。
- 建立 `frontend/.env.example`，只含 `VITE_API_BASE_URL=http://localhost:8000`。
- 前端程式碼不得出現任何 secret 或 server-only 環境變數名稱。

### 3. 後端 readiness（`frontend/src/features/backend-status/`）

實作 `useBackendReadiness()` hook 與 `BackendStatusBanner` 元件：

- 頁面載入後立即呼叫 `GET {API_BASE_URL}/health/ready`。
- 狀態機：
  - `checking`：第一次請求進行中。
  - `ready`：收到 200 且 body `status === "ready"`。
  - `warming`：收到非 200、網路錯誤或逾時（單次請求逾時 10 秒）。每 5 秒重試一次。
  - `unavailable`：從第一次失敗起累計超過 180 秒仍未 ready。停止自動重試，提供「重新檢查」按鈕；按下後回到 `checking` 並重新開始計時。
- 進入 `ready` 後停止輪詢。
- `BackendStatusBanner` 文案：
  - `checking`：「正在連線 Agent 執行環境…」
  - `warming`：「Agent 執行環境正在啟動，可能需要 30–90 秒」，並顯示「X 秒後重試」倒數（每秒更新）與已嘗試次數。
  - `ready`：簡短的「已就緒」狀態。
  - `unavailable`：「Agent 執行環境暫時無法連線」加上「重新檢查」按鈕。
  - 任何狀態都不顯示原始錯誤訊息（例如 `TypeError: Failed to fetch`）。
- 提供 `isReady` 給其他元件使用，用來決定可否啟用需要後端的操作按鈕。

### 4. App 結構與頁面

- `src/app/`：Router、`QueryClientProvider`、layout（頂部導覽列加上 `BackendStatusBanner`）。
- 路由：
  - `/` Landing：
    - 一句話定位：「AgentOps Commander — AI Multi-Agent Incident Response Platform」與 2–3 句說明（內容取自 SPEC §2.2）。
    - 三個情境卡片：CPU Spike After Deployment、Database Pool Exhaustion、Duplicate Alert Storm，各附服務名稱與一句描述（取自 SPEC §9）。
    - 明確標示「所有基礎設施操作皆為模擬（SIMULATION）」。
  - 未知路徑 → 404 頁，附回首頁連結。
- 不要建立指向尚未存在頁面的按鈕或連結（例如 `/incidents/new`），這些在 Phase 1 才加入。
- 視覺：深色科技風，可讀性優先；不使用打字動畫。1440px desktop 為主要版型，375px 寬度下內容不得水平捲動。

### 5. 測試（`frontend/tests/` 或 colocated `*.test.tsx`）

以 mock `fetch`（或 MSW 以外的輕量 mock，不要額外引入 MSW）與 fake timers 測試：

- 後端第一次就 ready → 顯示已就緒，且不再發出請求。
- 後端前兩次失敗、第三次 ready → 依序顯示 warming（含倒數與次數）→ ready，過程中不 remount 頁面（對應 AC-06）。
- 失敗持續超過 180 秒 → 顯示 unavailable 與「重新檢查」按鈕；按下後重新請求。
- 網路錯誤時畫面不出現原始錯誤字串。
- Landing 頁渲染三個情境卡片與 SIMULATION 聲明。
- 未知路徑渲染 404 頁。

## 驗收標準

在 `frontend/` 目錄下全部通過：

1. `npm ci` 成功。
2. `npm run lint` 無錯誤、無警告。
3. `npm run typecheck` 無錯誤。
4. `npm run test` 全數通過。
5. `npm run build` 成功，輸出至 `frontend/dist`。
6. `npm run dev` 時，若後端未啟動：banner 顯示 warming 與倒數；之後啟動 T1 後端（不需 DB 正常則會一直是 warming，此為預期）。若後端 ready，畫面在不重新整理的情況下切換為已就緒。
7. `dist/` 內容中搜尋不到 `SECRET`、`SERVICE_ROLE`、`API_KEY` 等字樣。

## 明確排除的範圍

- 不做登入、Supabase JS、任何 Auth。
- 不做 incidents、approvals、runbooks、evaluations、architecture 等頁面（後續 Phase）。
- 不做 `wrangler.jsonc` 與部署設定（T12）。
- 不做 frontend Dockerfile、docker-compose、CI（T3）。
- 不做 Playwright（D-007）。
