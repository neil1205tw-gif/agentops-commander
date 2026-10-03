# T7：前端登入與 Incidents 頁面

- Phase：1
- 依賴：T6
- 相關文件：`SPEC.md` §13.1、§13.2（本階段只做 Incident Header 與基本事件列表）、§13.3；`DECISIONS.md` D-016、D-017、D-018、D-019

## 背景 / 動機

讓使用者在瀏覽器完成 Phase 1 的驗收流程：登入 → 建立 incident → 在清單與詳情頁查看。正式環境的 Supabase 登入留到 Phase 6，本階段登入入口只有 development 模式下的 dev 登入（D-017）。

## 具體需求

### 1. API client 與身分狀態（`frontend/src/lib/`、`frontend/src/features/auth/`）

- `apiFetch(path, options)`：以 `API_BASE_URL` 組成 URL，自動帶 `Authorization: Bearer <token>`；JSON 序列化；非 2xx 轉為帶 `status` 與 `detail` 的錯誤物件。收到 `401` 時清除登入狀態並導向 `/login`。不得把 token 寫入 console 或 URL。
- `AuthProvider` / `useAuth()`：
  - 狀態：`token`、`user`（`id`、`email`、`display_name`、`role`）、`status`（`loading | authenticated | anonymous`）。
  - token 保存在 `sessionStorage`（所有讀寫包 try/catch，storage 不可用時退回記憶體；頁面重新整理後若有 token 則呼叫 `GET /me` 還原狀態，失敗則清除）。
  - `loginAsDev(role)`：呼叫 `POST /api/v1/auth/dev-login` 後再呼叫 `/me`。
  - `logout()`：清除 token 與 TanStack Query cache。
- 受保護路由元件 `RequireAuth`：未登入導向 `/login`（保留原目標以便登入後回跳）；`RequireRole`（或在頁面中以 `useAuth().user.role` 判斷）用於限制操作。

### 2. 頁面與路由

所有需登入頁面都使用既有 layout（頂部導覽 + backend status banner）。導覽列顯示：Incidents、（operator/admin）New Incident、目前使用者的 email 與角色徽章、登出按鈕。Landing 頁新增一個「進入事故列表」連結（只有現在才有此頁面可連）。

- **`/login`**
  - 載入時呼叫 `GET /api/v1/auth/config`。
  - `dev_login_enabled = true`：顯示三顆按鈕「以 Viewer / Operator / Admin 登入（開發模式）」，並標示此為本機開發用入口。
  - `dev_login_enabled = false`：顯示明確說明「此環境的正式登入尚未啟用」，不顯示任何可點擊的登入控制項。
  - 後端尚未 ready 時（`isReady` 為 false）按鈕停用並提示等待。登入成功回跳原目標或 `/incidents`。已登入者進入 `/login` 直接導向 `/incidents`。
- **`/incidents`**
  - 以 TanStack Query 取得清單（`limit` 20，上一頁 / 下一頁，狀態 filter 下拉選單）。
  - 表格欄位：標題（連到詳情）、severity（null 顯示「待分類」）、status、服務、更新時間（相對時間或本地時間格式）、公開標記。
  - 空狀態：viewer 顯示「目前沒有公開範例」；operator / admin 顯示「尚無事故，建立第一筆」並連到 `/incidents/new`。
  - 載入中與錯誤狀態有明確 UI（錯誤不顯示原始例外字串，提供重試）。
- **`/incidents/new`**
  - 僅 operator / admin；viewer 看到「需要 Operator 權限」說明（不顯示表單）。
  - 從 `GET /api/v1/scenarios` 載入三個情境，以卡片單選，顯示名稱、服務、描述；選擇後可編輯 title（預設為情境的 `default_title`，placeholder 同）。
  - 送出前表單驗證（title 1–200 字）；送出中停用按鈕；成功導向 `/incidents/{id}`；失敗顯示後端回傳的 `detail` 的友善文字。`isReady` 為 false 時停用送出。
- **`/incidents/:id`**
  - Header：標題、severity、status、服務、建立時間、擁有者（顯示自己時標示「你」）、公開標記。
  - 告警區塊：顯示 `alert`（summary、source、symptoms）。
  - 事件列表：依時間顯示 `incident_events`（時間、類型、摘要），這是 Phase 2 完整 Timeline 的前身；此處只做簡單清單，不要實作 Agent Timeline 的進階功能。
  - 操作：擁有者或 admin 顯示「刪除」（需二次確認對話框，成功後回 `/incidents`）；admin 顯示「設為公開 / 設為私有」切換。其他角色看不到這些控制項。
  - 找不到（404）顯示「找不到此事故或沒有權限」。
- 使用者輸入（title 等）一律以 React 預設的文字渲染，不使用 `dangerouslySetInnerHTML`。
- 版面維持既有深色風格，1440px 為主，375px 不水平捲動。

### 3. 測試（Vitest + Testing Library，沿用既有 fake fetch 方式）

- `apiFetch`：帶 token、401 處理、錯誤物件、不洩漏 token。
- `AuthProvider`：dev 登入流程、重新整理還原（`/me` 成功與失敗）、登出清除、sessionStorage 不可用時的行為。
- `/login`：dev 模式顯示三顆按鈕；非 dev 模式顯示說明且沒有登入按鈕；backend 未 ready 時停用。
- 路由保護：未登入導向 `/login` 並於登入後回跳。
- `/incidents`：清單渲染、分頁、filter、viewer 空狀態與 operator 空狀態文字、錯誤與重試。
- `/incidents/new`：viewer 看到無權限說明；operator 選情境、預設 title、驗證、送出成功導向、失敗訊息。
- `/incidents/:id`：渲染 header / alert / events；擁有者與 admin 才有刪除；admin 才有公開切換；404 狀態；刪除確認流程。
- 測試之間不得共用全域狀態（每個測試重設 sessionStorage 與 fetch stub）。

## 驗收標準

1. `frontend/` 下 `npm run lint`（0 warning）、`typecheck`、`test`、`build` 全數通過；`dist/` 內搜尋不到 `SECRET`、`SERVICE_ROLE`、`API_KEY`、`DEV_AUTH_SECRET`。
2. `docker compose up --build` 後，在瀏覽器中（可使用 Playwright 或內建瀏覽器工具做一次性手動驗證，**不要**把 Playwright 加進專案相依，D-007）完成並於回報中附截圖路徑或逐步結果：
   - Operator 登入 → 建立三種情境各一筆 → 清單看得到 → 詳情頁看得到告警與「incident created」事件。
   - Viewer 登入 → 清單為空並顯示「目前沒有公開範例」→ 進入 `/incidents/new` 看到無權限說明。
   - Admin 登入 → 把 operator 的 incident 設為公開 → 重新以 Viewer 登入可看到該筆。
   - 擁有者刪除 incident 後從清單消失。
   - 在 375px 與 1440px 寬度各檢查一次主要頁面無水平捲動。
3. 後端未啟動時，登入頁顯示既有的 warming 狀態，按鈕停用；後端就緒後不需重新整理即可操作。

## 明確排除的範圍

- 不做 Supabase JS、Supabase 登入表單（Phase 6）。
- 不做完整 Agent Timeline、Evidence Panel、Plan Panel、Approval Card（後續 Phase）。
- 不做 `/approvals`、`/runbooks`、`/evaluations`、`/architecture` 頁面。
- 不做 incident 的編輯與搜尋。
- 不引入 Playwright 或其他新的 E2E 相依；不引入 UI 元件庫。
