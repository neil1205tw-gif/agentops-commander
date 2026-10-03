import { createContext, useContext } from 'react'

import type { AuthStatus, AuthUser, Role } from './types'

export interface AuthContextValue {
  token: string | null
  user: AuthUser | null
  status: AuthStatus
  /** 開發模式登入：呼叫 dev-login 後以 /me 取得使用者；失敗時拋出 ApiError。 */
  loginAsDev: (role: Role) => Promise<void>
  /** 清除 token 與 TanStack Query cache。 */
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return value
}
