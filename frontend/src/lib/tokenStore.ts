const TOKEN_KEY = 'agentops.access_token'

/** sessionStorage 不可用（被停用、隱私模式、配額）時退回的記憶體備援。 */
let memoryToken: string | null = null

export function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return memoryToken
  }
}

export function writeToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
    memoryToken = null
  } catch {
    memoryToken = token
  }
}

export function clearToken(): void {
  memoryToken = null
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage 不可用時，記憶體備援已清除，無其他需要處理的狀態。
  }
}
