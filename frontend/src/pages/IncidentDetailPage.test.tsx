import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Role } from '../features/auth'
import type { IncidentDetail } from '../features/incidents'
import {
  USERS,
  callsTo,
  jsonResponse,
  makeDetail,
  makeEvent,
  makeIncident,
  renderApp,
  settle,
  signedInHandlers,
  stubApi,
} from '../test/utils'
import type { StubHandler } from '../test/utils'

const ID = '11111111-1111-4111-8111-111111111111'
const PATH = `/incidents/${ID}`

const EVENTS = [
  makeEvent({
    id: 'e-2',
    event_type: 'incident.visibility_changed',
    summary: 'Incident visibility changed to public',
    created_at: '2026-10-03T09:00:00Z',
  }),
  makeEvent({ id: 'e-1', created_at: '2026-10-03T08:00:00Z' }),
]

function handlers(
  role: Role,
  incident: IncidentDetail = makeDetail(),
  extra: Record<string, StubHandler> = {},
): Record<string, StubHandler> {
  return {
    ...signedInHandlers(role),
    [`GET /api/v1/incidents/${ID}`]: () => jsonResponse(incident),
    [`GET /api/v1/incidents/${ID}/events`]: () => jsonResponse({ items: EVENTS }),
    'GET /api/v1/incidents': () => jsonResponse({ items: [makeIncident()], total: 1, limit: 20, offset: 0 }),
    ...extra,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('/incidents/:id', () => {
  it('渲染 header、告警區塊與依時間排序的事件列表', async () => {
    stubApi(handlers('operator', makeDetail({ severity: 'P2', status: 'investigating', is_public: true })))
    await renderApp(PATH)

    expect(screen.getByRole('heading', { level: 1, name: 'checkout-api CPU spike after deployment' })).toBeInTheDocument()
    expect(screen.getByText('P2')).toBeInTheDocument()
    expect(screen.getByText('investigating')).toBeInTheDocument()
    expect(screen.getByText('公開')).toBeInTheDocument()
    expect(screen.getByText('checkout-api')).toBeInTheDocument()
    expect(screen.getByText('建立時間')).toBeInTheDocument()
    expect(screen.getByText('擁有者')).toBeInTheDocument()

    const alert = within(screen.getByRole('region', { name: '告警' }))
    expect(alert.getByText('checkout-api CPU at 95%, p95 latency and HTTP 5xx rate rising')).toBeInTheDocument()
    expect(alert.getByText('metrics-alerting')).toBeInTheDocument()
    expect(alert.getByText('CPU utilization at 95%')).toBeInTheDocument()
    expect(alert.getByText('p95 latency increasing')).toBeInTheDocument()

    const events = within(screen.getByRole('region', { name: '事件列表' }))
    const items = events.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0] ?? document.body).getByText('incident.created')).toBeInTheDocument()
    expect(within(items[0] ?? document.body).getByText('Incident created from scenario cpu_spike_after_deploy')).toBeInTheDocument()
    expect(within(items[1] ?? document.body).getByText('incident.visibility_changed')).toBeInTheDocument()
  })

  it('severity 為 null 顯示待分類；alert 為 null 顯示不可用說明', async () => {
    stubApi(handlers('operator', makeDetail({ severity: null, alert: null })))
    await renderApp(PATH)

    expect(screen.getByText('待分類')).toBeInTheDocument()
    expect(screen.getByText('此事故的告警資料已不可用。')).toBeInTheDocument()
  })

  it('擁有者顯示「你」；其他人顯示縮短的 id', async () => {
    stubApi(handlers('operator'))
    const { unmount } = await renderApp(PATH)
    expect(screen.getByText('你')).toBeInTheDocument()
    unmount()

    stubApi(handlers('admin'))
    await renderApp(PATH)
    expect(screen.queryByText('你')).not.toBeInTheDocument()
    expect(screen.getByText(`其他使用者（${USERS.operator.id.slice(0, 8)}）`)).toBeInTheDocument()
  })

  it('使用者輸入的 title 以文字渲染，不解析 HTML', async () => {
    stubApi(handlers('operator', makeDetail({ title: '<img src=x onerror=alert(1)> <b>bold</b>' })))
    await renderApp(PATH)

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('<img src=x onerror=alert(1)> <b>bold</b>')
    expect(document.querySelector('main img')).toBeNull()
    expect(document.querySelector('main b')).toBeNull()
  })

  it('擁有者（operator）可刪除、看不到公開切換', async () => {
    stubApi(handlers('operator'))
    await renderApp(PATH)

    expect(screen.getByRole('button', { name: '刪除' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /設為公開|設為私有/ })).not.toBeInTheDocument()
  })

  it('非擁有者的 operator：沒有刪除也沒有公開切換', async () => {
    stubApi(handlers('operator', makeDetail({ owner_id: USERS.admin.id, is_public: true })))
    await renderApp(PATH)

    expect(screen.queryByRole('button', { name: '刪除' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /設為公開|設為私有/ })).not.toBeInTheDocument()
  })

  it('viewer：看到公開的 incident，但沒有任何操作控制項', async () => {
    stubApi(handlers('viewer', makeDetail({ is_public: true })))
    await renderApp(PATH)

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '刪除' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /設為公開|設為私有/ })).not.toBeInTheDocument()
  })

  it('admin：可刪除並可切換公開', async () => {
    stubApi(handlers('admin'))
    await renderApp(PATH)

    expect(screen.getByRole('button', { name: '刪除' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '設為公開' })).toBeInTheDocument()
  })

  it('admin 切換公開：PATCH visibility、更新標記與按鈕文字、重新取得事件', async () => {
    let current = makeDetail({ is_public: false })
    stubApi(
      handlers('admin', current, {
        [`GET /api/v1/incidents/${ID}`]: () => jsonResponse(current),
        [`PATCH /api/v1/incidents/${ID}/visibility`]: (request) => {
          current = makeDetail({ is_public: (request.body as { is_public: boolean }).is_public })
          return jsonResponse(current)
        },
      }),
    )
    await renderApp(PATH)
    expect(screen.getByText('私有')).toBeInTheDocument()
    const eventCallsBefore = callsTo(`GET /api/v1/incidents/${ID}/events`).length

    fireEvent.click(screen.getByRole('button', { name: '設為公開' }))
    await settle()

    expect(callsTo(`PATCH /api/v1/incidents/${ID}/visibility`)[0]?.body).toEqual({ is_public: true })
    expect(screen.getByText('公開')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '設為私有' })).toBeInTheDocument()
    expect(callsTo(`GET /api/v1/incidents/${ID}/events`).length).toBeGreaterThan(eventCallsBefore)

    fireEvent.click(screen.getByRole('button', { name: '設為私有' }))
    await settle()
    expect(callsTo(`PATCH /api/v1/incidents/${ID}/visibility`)[1]?.body).toEqual({ is_public: false })
    expect(screen.getByRole('button', { name: '設為公開' })).toBeInTheDocument()
  })

  it('切換公開失敗：顯示友善訊息', async () => {
    stubApi(
      handlers('admin', makeDetail(), {
        [`PATCH /api/v1/incidents/${ID}/visibility`]: () => jsonResponse({ detail: 'Insufficient role' }, 403),
      }),
    )
    const { container } = await renderApp(PATH)

    fireEvent.click(screen.getByRole('button', { name: '設為公開' }))
    await settle()

    expect(screen.getByText('你的角色沒有權限執行此操作。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/Insufficient role/)
  })

  it('刪除需二次確認：取消不會呼叫 API', async () => {
    stubApi(handlers('operator'))
    await renderApp(PATH)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('確定要刪除這筆事故？')).toBeInTheDocument()
    expect(callsTo(`DELETE /api/v1/incidents/${ID}`)).toHaveLength(0)

    fireEvent.click(within(dialog).getByRole('button', { name: '取消' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(callsTo(`DELETE /api/v1/incidents/${ID}`)).toHaveLength(0)
  })

  it('Escape 關閉確認對話框', async () => {
    stubApi(handlers('operator'))
    await renderApp(PATH)
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('確認刪除：呼叫 DELETE、回到 /incidents 且列表重新取得', async () => {
    let deleted = false
    stubApi(
      handlers('operator', makeDetail(), {
        [`DELETE /api/v1/incidents/${ID}`]: () => {
          deleted = true
          return jsonResponse(null, 204)
        },
        'GET /api/v1/incidents': () =>
          jsonResponse(
            deleted
              ? { items: [], total: 0, limit: 20, offset: 0 }
              : { items: [makeIncident()], total: 1, limit: 20, offset: 0 },
          ),
      }),
    )
    const { router } = await renderApp(PATH)

    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '確認刪除' }))
    await settle()

    expect(callsTo(`DELETE /api/v1/incidents/${ID}`)).toHaveLength(1)
    expect(router.state.location.pathname).toBe('/incidents')
    expect(screen.getByRole('link', { name: '尚無事故，建立第一筆' })).toBeInTheDocument()
  })

  it('刪除失敗：對話框內顯示友善訊息並保持開啟', async () => {
    stubApi(
      handlers('operator', makeDetail(), {
        [`DELETE /api/v1/incidents/${ID}`]: () => jsonResponse({ detail: 'db exploded' }, 500),
      }),
    )
    const { router, container } = await renderApp(PATH)

    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '確認刪除' }))
    await settle()

    expect(router.state.location.pathname).toBe(PATH)
    expect(within(screen.getByRole('dialog')).getByText('伺服器暫時發生問題，請稍後再試。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/db exploded/)
  })

  it('404：顯示「找不到此事故或沒有權限」，沒有操作控制項', async () => {
    stubApi({
      ...signedInHandlers('admin'),
      [`GET /api/v1/incidents/${ID}`]: () => jsonResponse({ detail: 'Incident not found' }, 404),
      [`GET /api/v1/incidents/${ID}/events`]: () => jsonResponse({ detail: 'Incident not found' }, 404),
    })
    await renderApp(PATH)

    expect(screen.getByText('找不到此事故或沒有權限')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '刪除' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← 返回事故列表' })).toHaveAttribute('href', '/incidents')
  })

  it('id 格式錯誤（422）也顯示同樣的找不到文案', async () => {
    stubApi({
      ...signedInHandlers('operator'),
      'GET /api/v1/incidents/not-a-uuid': () => jsonResponse({ detail: [{ msg: 'bad uuid' }] }, 422),
    })
    const { container } = await renderApp('/incidents/not-a-uuid')
    expect(screen.getByText('找不到此事故或沒有權限')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/bad uuid/)
  })

  it('伺服器錯誤：友善訊息與重試', async () => {
    let fail = true
    stubApi(
      handlers('operator', makeDetail(), {
        [`GET /api/v1/incidents/${ID}`]: () => (fail ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(makeDetail())),
      }),
    )
    await renderApp(PATH)
    expect(screen.getByText('伺服器暫時發生問題，請稍後再試。')).toBeInTheDocument()

    fail = false
    fireEvent.click(screen.getByRole('button', { name: '重試' }))
    await settle()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  it('事件載入失敗不影響 header：事件區塊顯示錯誤與重試', async () => {
    stubApi(
      handlers('operator', makeDetail(), {
        [`GET /api/v1/incidents/${ID}/events`]: () => jsonResponse({ detail: 'boom' }, 500),
      }),
    )
    await renderApp(PATH)

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByText('無法載入事件列表。')).toBeInTheDocument()
  })
})
