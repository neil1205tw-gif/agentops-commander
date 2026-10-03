import { act, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { USERS, callsTo, jsonResponse, renderApp, settle, stubApi } from '../test/utils'
import type { StubHandler } from '../test/utils'

const DEV_LABELS = [
  '以 Viewer 登入（開發模式）',
  '以 Operator 登入（開發模式）',
  '以 Admin 登入（開發模式）',
]

const devConfig: StubHandler = () => jsonResponse({ dev_login_enabled: true })

function loginHandlers(): Record<string, StubHandler> {
  return {
    'GET /api/v1/auth/config': devConfig,
    'POST /api/v1/auth/dev-login': (request) => {
      const role = (request.body as { role: 'viewer' | 'operator' | 'admin' }).role
      return jsonResponse({ access_token: `token-${role}`, token_type: 'bearer', expires_in: 28800 })
    },
    'GET /api/v1/me': (request) => {
      const token = request.headers.get('Authorization') ?? ''
      const role = token.replace('Bearer token-', '') as keyof typeof USERS
      return jsonResponse(USERS[role])
    },
    'GET /api/v1/incidents': () => jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
  }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('/login', () => {
  it('dev 模式：顯示三顆登入按鈕與本機開發用說明', async () => {
    stubApi(loginHandlers())
    await renderApp('/login')

    for (const label of DEV_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeEnabled()
    }
    expect(screen.getByText(/本機開發用的登入入口/)).toBeInTheDocument()
  })

  it('非 dev 模式：只顯示說明，沒有任何登入控制項', async () => {
    stubApi({ 'GET /api/v1/auth/config': () => jsonResponse({ dev_login_enabled: false }) })
    await renderApp('/login')

    expect(screen.getByText('此環境的正式登入尚未啟用')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /登入/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    // 導覽列的「登入」只是連到本頁的連結，不是登入控制項。
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('backend 未 ready：按鈕停用並提示；就緒後不需重新整理即可操作', async () => {
    let ready = false
    stubApi({
      ...loginHandlers(),
      'GET /health/ready': () => (ready ? jsonResponse({ status: 'ready' }) : jsonResponse({}, 503)),
    })
    await renderApp('/login')

    for (const label of DEV_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeDisabled()
    }
    expect(screen.getByText('Agent 執行環境尚未就緒，就緒後即可登入。')).toBeInTheDocument()
    expect(screen.getByText(/Agent 執行環境正在啟動/)).toBeInTheDocument()

    ready = true
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })
    await settle()

    for (const label of DEV_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeEnabled()
    }
  })

  it('後端完全連不上：登入頁顯示 warming 與停用的按鈕，恢復後可登入', async () => {
    let up = false
    stubApi({
      ...loginHandlers(),
      'GET /health/ready': () => (up ? jsonResponse({ status: 'ready' }) : Promise.reject(new TypeError('Failed to fetch'))),
      'GET /api/v1/auth/config': () =>
        up ? jsonResponse({ dev_login_enabled: true }) : Promise.reject(new TypeError('Failed to fetch')),
    })
    await renderApp('/login')

    expect(screen.getByText(/Agent 執行環境正在啟動/)).toBeInTheDocument()
    for (const label of DEV_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeDisabled()
    }

    up = true
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })
    await settle()

    for (const label of DEV_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeEnabled()
    }
  })

  it('config 取得失敗（後端已 ready）：顯示友善錯誤與重試，不顯示原始例外', async () => {
    let fail = true
    stubApi({
      'GET /api/v1/auth/config': () =>
        fail ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse({ dev_login_enabled: true }),
    })
    const { container } = await renderApp('/login')

    expect(screen.getByText('無法取得登入方式，請重試。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/boom|ApiError/)

    fail = false
    fireEvent.click(screen.getByRole('button', { name: '重試' }))
    await settle()
    expect(screen.getByRole('button', { name: DEV_LABELS[0] ?? '' })).toBeEnabled()
  })

  it('登入成功：回跳 /incidents 並顯示 email 與角色徽章', async () => {
    stubApi(loginHandlers())
    const { router } = await renderApp('/login')

    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[1] ?? '' }))
    await settle()

    expect(router.state.location.pathname).toBe('/incidents')
    expect(screen.getByText('operator@demo.local')).toBeInTheDocument()
    expect(screen.getByText('operator')).toHaveAttribute('data-role', 'operator')
    expect(callsTo('POST /api/v1/auth/dev-login')[0]?.body).toEqual({ role: 'operator' })
  })

  it('登入失敗：顯示友善訊息、不顯示原始錯誤，按鈕恢復可用', async () => {
    stubApi({
      ...loginHandlers(),
      'POST /api/v1/auth/dev-login': () => jsonResponse({ detail: 'secret internal stack' }, 500),
    })
    const { container, router } = await renderApp('/login')

    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[2] ?? '' }))
    await settle()

    expect(router.state.location.pathname).toBe('/login')
    expect(screen.getByText('伺服器暫時發生問題，請稍後再試。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/secret internal stack/)
    expect(screen.getByRole('button', { name: DEV_LABELS[2] ?? '' })).toBeEnabled()
  })

  it('已登入者進入 /login 直接導向 /incidents', async () => {
    stubApi(loginHandlers())
    const { router } = await renderApp('/login')
    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[0] ?? '' }))
    await settle()

    await act(async () => {
      await router.navigate('/login')
    })
    await settle()
    expect(router.state.location.pathname).toBe('/incidents')
  })
})

describe('路由保護', () => {
  it('未登入造訪受保護頁：導向 /login，登入後回跳原目標', async () => {
    stubApi(loginHandlers())
    const { router } = await renderApp('/incidents/new')

    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.state).toEqual({ from: '/incidents/new' })

    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[1] ?? '' }))
    await settle()

    expect(router.state.location.pathname).toBe('/incidents/new')
  })

  it('登入後回跳只接受站內路徑，其餘回到 /incidents', async () => {
    stubApi(loginHandlers())
    const { router } = await renderApp('/login')
    await act(async () => {
      await router.navigate('/login', { state: { from: '//evil.example/path' } })
    })
    await settle()

    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[0] ?? '' }))
    await settle()
    expect(router.state.location.pathname).toBe('/incidents')
  })

  it('未登入時導覽列不顯示 Incidents，也不呼叫受保護 API', async () => {
    const stub = stubApi(loginHandlers())
    await renderApp('/incidents')

    expect(screen.queryByRole('link', { name: 'Incidents' })).not.toBeInTheDocument()
    expect(callsTo('GET /api/v1/incidents')).toHaveLength(0)
    expect(stub.mock.calls.some(([input]) => typeof input === 'string' && input.includes('/api/v1/me'))).toBe(false)
  })

  it('登出後導向 /login 並清除登入狀態', async () => {
    stubApi(loginHandlers())
    const { router } = await renderApp('/login')
    fireEvent.click(screen.getByRole('button', { name: DEV_LABELS[1] ?? '' }))
    await settle()

    fireEvent.click(screen.getByRole('button', { name: '登出' }))
    await settle()

    expect(router.state.location.pathname).toBe('/login')
    expect(sessionStorage.getItem('agentops.access_token')).toBeNull()
    expect(screen.queryByText('operator@demo.local')).not.toBeInTheDocument()
  })

  it('已有 token 重新整理後以 /me 還原並留在原頁', async () => {
    sessionStorage.setItem('agentops.access_token', 'token-viewer')
    stubApi(loginHandlers())
    const { router } = await renderApp('/incidents')

    expect(router.state.location.pathname).toBe('/incidents')
    expect(screen.getByText('viewer@demo.local')).toBeInTheDocument()
  })
})
