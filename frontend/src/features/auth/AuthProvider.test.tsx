import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../lib/api'
import { readToken, writeToken } from '../../lib/tokenStore'
import { USERS, callsTo, jsonResponse, settle, stubApi } from '../../test/utils'
import { useAuth } from './AuthContext'
import { AuthProvider } from './AuthProvider'
import type { Role } from './types'

function Probe() {
  const { status, user, token, loginAsDev, logout } = useAuth()
  const cached = useQuery({
    queryKey: ['probe'],
    queryFn: () => Promise.resolve('cached-value'),
    enabled: status === 'authenticated',
  })
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="email">{user?.email ?? '-'}</p>
      <p data-testid="role">{user?.role ?? '-'}</p>
      <p data-testid="token">{token ?? '-'}</p>
      <p data-testid="cache">{cached.data ?? '-'}</p>
      <button
        onClick={() => {
          loginAsDev('operator').catch(() => undefined)
        }}
      >
        login-operator
      </button>
      <button onClick={logout}>logout</button>
      <button
        onClick={() => {
          apiFetch('/api/v1/me').catch(() => undefined)
        }}
      >
        call-api
      </button>
    </div>
  )
}

let queryClient: QueryClient

async function renderProbe() {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
  await settle()
}

const devLogin = (role: Role) => () =>
  jsonResponse({ access_token: `token-${role}`, token_type: 'bearer', expires_in: 28800 })

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('AuthProvider', () => {
  it('沒有 token：直接是 anonymous，不呼叫 /me', async () => {
    const stub = stubApi({})
    await renderProbe()
    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(stub).not.toHaveBeenCalled()
  })

  it('dev 登入：呼叫 dev-login 再呼叫 /me，token 存入 sessionStorage', async () => {
    stubApi({
      'POST /api/v1/auth/dev-login': (request) => {
        expect(request.body).toEqual({ role: 'operator' })
        return devLogin('operator')()
      },
      'GET /api/v1/me': (request) => {
        expect(request.headers.get('Authorization')).toBe('Bearer token-operator')
        return jsonResponse(USERS.operator)
      },
    })
    await renderProbe()

    fireEvent.click(screen.getByRole('button', { name: 'login-operator' }))
    await settle()

    expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    expect(screen.getByTestId('email')).toHaveTextContent('operator@demo.local')
    expect(screen.getByTestId('role')).toHaveTextContent('operator')
    expect(screen.getByTestId('token')).toHaveTextContent('token-operator')
    expect(sessionStorage.getItem('agentops.access_token')).toBe('token-operator')
  })

  it('dev 登入的 /me 失敗：不留下 token，狀態維持 anonymous', async () => {
    stubApi({
      'POST /api/v1/auth/dev-login': devLogin('operator'),
      'GET /api/v1/me': () => jsonResponse({ detail: 'boom' }, 500),
    })
    await renderProbe()

    fireEvent.click(screen.getByRole('button', { name: 'login-operator' }))
    await settle()

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(readToken()).toBeNull()
  })

  it('重新整理還原：有 token 時以 /me 還原，先顯示 loading', async () => {
    writeToken('token-admin')
    let resolveMe: (response: Response) => void = () => undefined
    stubApi({
      'GET /api/v1/me': () =>
        new Promise<Response>((resolve) => {
          resolveMe = resolve
        }),
    })
    await renderProbe()
    expect(screen.getByTestId('status')).toHaveTextContent('loading')

    resolveMe(jsonResponse(USERS.admin))
    await settle()

    expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    expect(screen.getByTestId('role')).toHaveTextContent('admin')
    expect(callsTo('GET /api/v1/me')[0]?.headers.get('Authorization')).toBe('Bearer token-admin')
  })

  it('重新整理還原失敗：清除 token 並成為 anonymous', async () => {
    writeToken('expired')
    stubApi({ 'GET /api/v1/me': () => jsonResponse({ detail: 'Invalid token' }, 401) })
    await renderProbe()

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(readToken()).toBeNull()
    expect(sessionStorage.getItem('agentops.access_token')).toBeNull()
  })

  it('重新整理還原遇到網路錯誤也清除 token', async () => {
    writeToken('token-viewer')
    stubApi({ 'GET /api/v1/me': () => Promise.reject(new TypeError('Failed to fetch')) })
    await renderProbe()
    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(readToken()).toBeNull()
  })

  it('登出：清除 token 與 Query cache', async () => {
    writeToken('token-operator')
    stubApi({ 'GET /api/v1/me': () => jsonResponse(USERS.operator) })
    await renderProbe()
    expect(screen.getByTestId('cache')).toHaveTextContent('cached-value')
    expect(queryClient.getQueryCache().getAll()).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'logout' }))
    await settle()

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(readToken()).toBeNull()
    expect(sessionStorage.getItem('agentops.access_token')).toBeNull()
    expect(queryClient.getQueryData(['probe'])).toBeUndefined()
  })

  it('任何 API 回 401：清除登入狀態', async () => {
    writeToken('token-operator')
    let meCalls = 0
    stubApi({
      'GET /api/v1/me': () => {
        meCalls += 1
        return meCalls === 1 ? jsonResponse(USERS.operator) : jsonResponse({ detail: 'expired' }, 401)
      },
    })
    await renderProbe()
    expect(screen.getByTestId('status')).toHaveTextContent('authenticated')

    fireEvent.click(screen.getByRole('button', { name: 'call-api' }))
    await settle()

    expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
    expect(readToken()).toBeNull()
  })

  describe('sessionStorage 不可用', () => {
    beforeEach(() => {
      const fail = () => {
        throw new DOMException('denied', 'SecurityError')
      }
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(fail)
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(fail)
      vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(fail)
    })

    it('退回記憶體：仍可登入、呼叫 API 並登出，且不拋錯', async () => {
      stubApi({
        'POST /api/v1/auth/dev-login': devLogin('operator'),
        'GET /api/v1/me': () => jsonResponse(USERS.operator),
      })
      await renderProbe()
      expect(screen.getByTestId('status')).toHaveTextContent('anonymous')

      fireEvent.click(screen.getByRole('button', { name: 'login-operator' }))
      await settle()
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
      expect(readToken()).toBe('token-operator')
      expect(callsTo('GET /api/v1/me')[0]?.headers.get('Authorization')).toBe('Bearer token-operator')

      fireEvent.click(screen.getByRole('button', { name: 'logout' }))
      await settle()
      expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
      expect(readToken()).toBeNull()
    })
  })
})
