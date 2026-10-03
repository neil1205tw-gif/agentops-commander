import { API_BASE_URL } from './config'
import { clearToken, readToken } from './tokenStore'

/** 非 2xx 回應（或網路失敗，status 為 0）轉成的錯誤；只含狀態碼與後端 detail，不含請求標頭。 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(`API request failed (${String(status)})`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

type UnauthorizedListener = () => void

const unauthorizedListeners = new Set<UnauthorizedListener>()

/** 訂閱「收到 401」事件；回傳取消訂閱函式。 */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener)
  return () => {
    unauthorizedListeners.delete(listener)
  }
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body = (await response.json()) as { detail?: unknown } | null
    return body?.detail ?? null
  } catch {
    return null
  }
}

/**
 * 呼叫後端 API：帶 Bearer token、JSON 序列化、非 2xx 轉為 ApiError。
 * 收到 401 且該請求所用的 token 仍是目前的 token 時，清除 token 並通知訂閱者
 * （AuthProvider 會清掉登入狀態，路由保護導向 /login）；token 已更換則只回傳錯誤給呼叫者。
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = readToken()
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`
  }
  const init: RequestInit = { method: options.method ?? 'GET', headers, signal: options.signal }
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch (error) {
    if (options.signal?.aborted) {
      throw error
    }
    // 網路錯誤：不把原始例外往外傳。
    throw new ApiError(0, null)
  }

  if (!response.ok) {
    const detail = await readDetail(response)
    // 只有「發出請求時用的 token」仍是目前的 token，才代表登入狀態失效；
    // 否則是舊 session 的請求遲到，不能作廢使用者之後重新登入的新 token。
    if (response.status === 401 && readToken() === token) {
      clearToken()
      for (const listener of [...unauthorizedListeners]) {
        listener()
      }
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(response.status, null)
  }
}
