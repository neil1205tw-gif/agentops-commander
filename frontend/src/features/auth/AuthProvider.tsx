import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { apiFetch, onUnauthorized } from '../../lib/api'
import { clearToken, readToken, writeToken } from '../../lib/tokenStore'
import { AuthContext } from './AuthContext'
import type { AuthContextValue } from './AuthContext'
import type { AuthStatus, AuthUser, Role } from './types'

interface AuthState {
  token: string | null
  user: AuthUser | null
  status: AuthStatus
}

interface DevLoginResponse {
  access_token: string
}

const ANONYMOUS: AuthState = { token: null, user: null, status: 'anonymous' }

function fetchMe(signal?: AbortSignal): Promise<AuthUser> {
  return apiFetch<AuthUser>('/api/v1/me', { signal })
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>(() => {
    const token = readToken()
    return token === null ? ANONYMOUS : { token, user: null, status: 'loading' }
  })

  // 重新整理後以 /me 還原登入狀態；失敗（token 過期、被拒）則清除。
  useEffect(() => {
    const token = readToken()
    if (token === null) {
      return
    }
    const controller = new AbortController()
    fetchMe(controller.signal).then(
      (user) => {
        setState({ token, user, status: 'authenticated' })
      },
      () => {
        if (controller.signal.aborted) {
          return
        }
        clearToken()
        setState(ANONYMOUS)
      },
    )
    return () => {
      controller.abort()
    }
  }, [])

  // 任何 API 回 401：apiFetch 已清除 token，這裡清掉狀態與快取，RequireAuth 會導向 /login。
  useEffect(
    () =>
      onUnauthorized(() => {
        setState(ANONYMOUS)
        queryClient.clear()
      }),
    [queryClient],
  )

  const loginAsDev = useCallback(async (role: Role) => {
    const { access_token: token } = await apiFetch<DevLoginResponse>('/api/v1/auth/dev-login', {
      method: 'POST',
      body: { role },
    })
    writeToken(token)
    try {
      const user = await fetchMe()
      setState({ token, user, status: 'authenticated' })
    } catch (error) {
      clearToken()
      throw error
    }
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setState(ANONYMOUS)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, loginAsDev, logout }),
    [state, loginAsDev, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
