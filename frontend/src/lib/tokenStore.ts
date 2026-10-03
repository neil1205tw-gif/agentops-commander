const TOKEN_KEY = 'agentops.access_token'

/** sessionStorage 無法寫入（被停用、隱私模式、配額已滿）時改存記憶體；有值時優先於 storage。 */
let memoryToken: string | null = null

/** 清除時 storage 的 removeItem 失敗，storage 內可能殘留舊值；在下一次成功寫入前一律忽略 storage。 */
let ignoreStorage = false

export function readToken(): string | null {
  if (memoryToken !== null) {
    return memoryToken
  }
  if (ignoreStorage) {
    return null
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function writeToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
    memoryToken = null
    ignoreStorage = false
  } catch {
    // storage 寫不進去：改存記憶體；storage 內若有舊值，盡力移除，移除不了也由記憶體值優先。
    memoryToken = token
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      // 無法移除；readToken 以 memoryToken 優先，不會讀到舊值。
    }
  }
}

export function clearToken(): void {
  memoryToken = null
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    ignoreStorage = false
  } catch {
    // 移除失敗時 storage 可能仍有舊值，標記為忽略，避免登出後又讀回舊 token。
    ignoreStorage = true
  }
}
