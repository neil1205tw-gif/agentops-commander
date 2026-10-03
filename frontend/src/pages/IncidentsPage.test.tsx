import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  callsTo,
  jsonResponse,
  makeIncident,
  renderApp,
  settle,
  signedInHandlers,
  stubApi,
} from '../test/utils'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function page(total: number, offset: number, count: number) {
  return {
    items: Array.from({ length: count }, (_, index) =>
      makeIncident({
        id: `00000000-0000-4000-8000-${String(offset + index).padStart(12, '0')}`,
        title: `Incident #${String(offset + index + 1)}`,
      }),
    ),
    total,
    limit: 20,
    offset,
  }
}

describe('/incidents', () => {
  it('渲染清單欄位：標題連結、severity 待分類、status、服務、更新時間、公開標記', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': () =>
        jsonResponse({
          items: [
            makeIncident({ id: 'a-1', title: 'Pool <b>exhausted</b>', severity: null, is_public: false }),
            makeIncident({
              id: 'a-2',
              title: 'Second',
              severity: 'P2',
              status: 'investigating',
              affected_services: ['svc-a', 'svc-b'],
              is_public: true,
            }),
          ],
          total: 2,
          limit: 20,
          offset: 0,
        }),
    })
    await renderApp('/incidents')

    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(3)
    for (const header of ['標題', 'severity', 'status', '服務', '更新時間', '公開']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }

    // 使用者輸入以文字渲染，不解析成 HTML。
    const link = screen.getByRole('link', { name: 'Pool <b>exhausted</b>' })
    expect(link).toHaveAttribute('href', '/incidents/a-1')
    expect(document.querySelector('main b')).toBeNull()

    const first = within(rows[1] ?? document.body)
    expect(first.getByText('待分類')).toBeInTheDocument()
    expect(first.getByText('open')).toBeInTheDocument()
    expect(first.getByText('checkout-api')).toBeInTheDocument()
    expect(first.getByText('私有')).toBeInTheDocument()

    const second = within(rows[2] ?? document.body)
    expect(second.getByText('P2')).toBeInTheDocument()
    expect(second.getByText('investigating')).toBeInTheDocument()
    expect(second.getByText('svc-a, svc-b')).toBeInTheDocument()
    expect(second.getByText('公開')).toBeInTheDocument()
    expect(screen.getByText('第 1–2 筆，共 2 筆')).toBeInTheDocument()
  })

  it('以 limit=20 查詢；導覽列對 operator 顯示 New Incident', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': () => jsonResponse(page(1, 0, 1)),
    })
    await renderApp('/incidents')

    const request = callsTo('GET /api/v1/incidents')[0]
    expect(request?.url.searchParams.get('limit')).toBe('20')
    expect(request?.url.searchParams.get('offset')).toBe('0')
    expect(request?.url.searchParams.has('status')).toBe(false)
    expect(request?.headers.get('Authorization')).toBe('Bearer token-operator')
    expect(screen.getByRole('link', { name: 'New Incident' })).toHaveAttribute('href', '/incidents/new')
  })

  it('viewer 導覽列沒有 New Incident', async () => {
    stubApi({
      ...signedInHandlers('viewer'),
      'GET /api/v1/incidents': () => jsonResponse(page(0, 0, 0)),
    })
    await renderApp('/incidents')
    expect(screen.queryByRole('link', { name: 'New Incident' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Incidents' })).toBeInTheDocument()
  })

  it('分頁：上一頁 / 下一頁帶 offset，邊界停用', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': (request) => {
        const offset = Number(request.url.searchParams.get('offset'))
        return jsonResponse(page(45, offset, Math.min(20, 45 - offset)))
      },
    })
    await renderApp('/incidents')

    expect(screen.getByText('第 1–20 筆，共 45 筆')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '上一頁' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下一頁' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: '下一頁' }))
    await settle()
    expect(screen.getByText('第 21–40 筆，共 45 筆')).toBeInTheDocument()
    expect(screen.getByText('Incident #21')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '下一頁' }))
    await settle()
    expect(screen.getByText('第 41–45 筆，共 45 筆')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '下一頁' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: '上一頁' }))
    await settle()
    expect(screen.getByText('第 21–40 筆，共 45 筆')).toBeInTheDocument()
    expect(callsTo('GET /api/v1/incidents').map((call) => call.url.searchParams.get('offset'))).toEqual([
      '0',
      '20',
      '40',
      '20',
    ])
  })

  it('status filter：帶 status 參數並回到第一頁', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': (request) => {
        const status = request.url.searchParams.get('status')
        const offset = Number(request.url.searchParams.get('offset'))
        if (status === 'resolved') {
          return jsonResponse({
            items: [makeIncident({ id: 'r-1', title: 'Resolved one', status: 'resolved' })],
            total: 1,
            limit: 20,
            offset: 0,
          })
        }
        return jsonResponse(page(45, offset, 20))
      },
    })
    await renderApp('/incidents')
    fireEvent.click(screen.getByRole('button', { name: '下一頁' }))
    await settle()

    fireEvent.change(screen.getByLabelText('狀態'), { target: { value: 'resolved' } })
    await settle()

    const last = callsTo('GET /api/v1/incidents').at(-1)
    expect(last?.url.searchParams.get('status')).toBe('resolved')
    expect(last?.url.searchParams.get('offset')).toBe('0')
    expect(screen.getByText('Resolved one')).toBeInTheDocument()
    expect(screen.getByText('第 1–1 筆，共 1 筆')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('狀態'), { target: { value: '' } })
    await settle()
    expect(callsTo('GET /api/v1/incidents').at(-1)?.url.searchParams.has('status')).toBe(false)
  })

  it('filter 沒有結果時顯示篩選專用的空狀態', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': (request) =>
        request.url.searchParams.has('status')
          ? jsonResponse({ items: [], total: 0, limit: 20, offset: 0 })
          : jsonResponse(page(1, 0, 1)),
    })
    await renderApp('/incidents')

    fireEvent.change(screen.getByLabelText('狀態'), { target: { value: 'failed' } })
    await settle()
    expect(screen.getByText('沒有符合此狀態的事故。')).toBeInTheDocument()
  })

  it('viewer 空狀態：目前沒有公開範例', async () => {
    stubApi({
      ...signedInHandlers('viewer'),
      'GET /api/v1/incidents': () => jsonResponse(page(0, 0, 0)),
    })
    await renderApp('/incidents')

    expect(screen.getByText('目前沒有公開範例')).toBeInTheDocument()
    expect(screen.queryByText('尚無事故，建立第一筆')).not.toBeInTheDocument()
  })

  it('operator / admin 空狀態：尚無事故，建立第一筆，連到 /incidents/new', async () => {
    for (const role of ['operator', 'admin'] as const) {
      sessionStorage.clear()
      stubApi({
        ...signedInHandlers(role),
        'GET /api/v1/incidents': () => jsonResponse(page(0, 0, 0)),
      })
      const { unmount } = await renderApp('/incidents')

      expect(screen.getByRole('link', { name: '尚無事故，建立第一筆' })).toHaveAttribute(
        'href',
        '/incidents/new',
      )
      expect(screen.queryByText('目前沒有公開範例')).not.toBeInTheDocument()
      unmount()
    }
  })

  it('載入中顯示狀態，完成後消失', async () => {
    let resolve: (response: Response) => void = () => undefined
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': () =>
        new Promise<Response>((done) => {
          resolve = done
        }),
    })
    await renderApp('/incidents')
    expect(screen.getByText('正在載入事故列表…')).toBeInTheDocument()

    resolve(jsonResponse(page(1, 0, 1)))
    await settle()
    expect(screen.queryByText('正在載入事故列表…')).not.toBeInTheDocument()
    expect(screen.getByText('Incident #1')).toBeInTheDocument()
  })

  it('錯誤：友善訊息（不顯示原始例外）並可重試', async () => {
    let fail = true
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': () =>
        fail ? jsonResponse({ detail: 'psycopg OperationalError: connection refused' }, 500) : jsonResponse(page(1, 0, 1)),
    })
    const { container } = await renderApp('/incidents')

    expect(screen.getByText('無法載入事故列表，請重試。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/psycopg|OperationalError|ApiError/)

    fail = false
    fireEvent.click(screen.getByRole('button', { name: '重試' }))
    await settle()
    expect(screen.getByText('Incident #1')).toBeInTheDocument()
    expect(screen.queryByText('無法載入事故列表，請重試。')).not.toBeInTheDocument()
  })

  it('列表 401：清除登入並導向 /login', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents': () => jsonResponse({ detail: 'Invalid token' }, 401),
    })
    const { router } = await renderApp('/incidents')

    expect(router.state.location.pathname).toBe('/login')
    expect(sessionStorage.getItem('agentops.access_token')).toBeNull()
  })
})
