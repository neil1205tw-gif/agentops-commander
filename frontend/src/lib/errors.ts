import { ApiError } from './api'

/** 把 API 錯誤轉成給使用者看的友善文字；絕不輸出原始例外字串。 */
export function describeApiError(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) {
    return fallback
  }
  switch (error.status) {
    case 0:
      return '無法連線到伺服器，請稍後再試。'
    case 401:
      return '登入已失效，請重新登入。'
    case 403:
      return '你的角色沒有權限執行此操作。'
    case 404:
      return '找不到此事故或沒有權限。'
    case 422:
      return error.detail === 'Unknown scenario_key'
        ? '找不到所選情境，請重新整理頁面後再試。'
        : '輸入內容不符合規定，請檢查後再試。'
    case 429:
      return '操作太頻繁，請稍後再試。'
    default:
      return error.status >= 500 ? '伺服器暫時發生問題，請稍後再試。' : fallback
  }
}
