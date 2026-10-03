import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch, onUnauthorized } from './api'
import { readToken, writeToken } from './tokenStore'

const fetchStub = vi.fn<typeof fetch>()

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

beforeEach(() => {
  vi.useFakeTimers()
  fetchStub.mockReset()
  vi.stubGlobal('fetch', fetchStub)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('apiFetch', () => {
  it('以 API_BASE_URL 組成網址並帶 Bearer token', async () => {
    writeToken('abc.def.ghi')
    fetchStub.mockResolvedValue(json({ ok: true }))

    const result = await apiFetch<{ ok: boolean }>('/api/v1/me')

    expect(result).toEqual({ ok: true })
    const [url, init] = fetchStub.mock.calls[0] ?? []
    expect(url).toBe('http://localhost:8000/api/v1/me')
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer abc.def.ghi')
    expect(init?.method).toBe('GET')
  })

  it('沒有 token 時不帶 Authorization', async () => {
    fetchStub.mockResolvedValue(json({}))
    await apiFetch('/api/v1/auth/config')
    const [, init] = fetchStub.mock.calls[0] ?? []
    expect(new Headers(init?.headers).has('Authorization')).toBe(false)
  })

  it('body 以 JSON 序列化並設定 Content-Type', async () => {
    fetchStub.mockResolvedValue(json({}))
    await apiFetch('/api/v1/incidents', { method: 'POST', body: { title: 'x' } })
    const [, init] = fetchStub.mock.calls[0] ?? []
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({ title: 'x' }))
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
  })

  it('204 回傳 undefined', async () => {
    fetchStub.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(apiFetch('/api/v1/incidents/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('非 2xx 轉為帶 status 與 detail 的 ApiError', async () => {
    fetchStub.mockResolvedValue(json({ detail: 'Incident not found' }, 404))

    const error = await apiFetch('/api/v1/incidents/x').catch((cause: unknown) => cause)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, detail: 'Incident not found' })
  })

  it('非 JSON 的錯誤回應 detail 為 null', async () => {
    fetchStub.mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }))
    const error = await apiFetch('/api/v1/me').catch((cause: unknown) => cause)
    expect(error).toMatchObject({ status: 502, detail: null })
  })

  it('網路失敗轉為 status 0 的 ApiError，不外傳原始例外', async () => {
    fetchStub.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = await apiFetch('/api/v1/me').catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0 })
    expect((error as Error).message).not.toMatch(/Failed to fetch/)
  })

  it('401：清除 token 並通知訂閱者，且仍拋出錯誤', async () => {
    writeToken('stale-token')
    const listener = vi.fn()
    const unsubscribe = onUnauthorized(listener)
    fetchStub.mockResolvedValue(json({ detail: 'Invalid token' }, 401))

    await expect(apiFetch('/api/v1/me')).rejects.toMatchObject({ status: 401 })

    expect(readToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    await expect(apiFetch('/api/v1/me')).rejects.toMatchObject({ status: 401 })
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('403 與 404 不會清除 token', async () => {
    writeToken('good-token')
    fetchStub.mockResolvedValueOnce(json({ detail: 'Insufficient role' }, 403))
    fetchStub.mockResolvedValueOnce(json({ detail: 'Incident not found' }, 404))
    await apiFetch('/a').catch(() => undefined)
    await apiFetch('/b').catch(() => undefined)
    expect(readToken()).toBe('good-token')
  })

  it('不把 token 寫入 console、URL 或錯誤物件', async () => {
    const token = 'super-secret-token-value'
    writeToken(token)
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((method) =>
      vi.spyOn(console, method).mockImplementation(() => undefined),
    )
    fetchStub.mockResolvedValue(json({ detail: 'Insufficient role' }, 403))

    const error = await apiFetch('/api/v1/incidents').catch((cause: unknown) => cause)

    const [url] = fetchStub.mock.calls[0] ?? []
    expect(url).toBe('http://localhost:8000/api/v1/incidents')
    expect(JSON.stringify(error)).not.toContain(token)
    expect((error as Error).message).not.toContain(token)
    expect((error as Error).stack ?? '').not.toContain(token)
    for (const spy of spies) {
      expect(spy).not.toHaveBeenCalled()
    }
  })
})
