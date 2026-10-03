import { fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  SCENARIOS,
  callsTo,
  jsonResponse,
  makeDetail,
  makeEvent,
  renderApp,
  settle,
  signedInHandlers,
  stubApi,
} from '../test/utils'
import type { StubHandler } from '../test/utils'

const CREATED_ID = '33333333-3333-4333-8333-333333333333'

function handlers(role: 'viewer' | 'operator' | 'admin', create?: StubHandler) {
  return {
    ...signedInHandlers(role),
    'GET /api/v1/scenarios': () => jsonResponse(SCENARIOS),
    'POST /api/v1/incidents':
      create ??
      ((request) =>
        jsonResponse(
          makeDetail({ id: CREATED_ID, title: (request.body as { title: string }).title }),
          201,
        )),
    [`GET /api/v1/incidents/${CREATED_ID}`]: () => jsonResponse(makeDetail({ id: CREATED_ID })),
    [`GET /api/v1/incidents/${CREATED_ID}/events`]: () => jsonResponse({ items: [makeEvent()] }),
    'GET /api/v1/incidents': () => jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
  }
}

const titleInput = () => screen.getByLabelText('標題')

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('/incidents/new', () => {
  it('viewer：顯示需要 Operator 權限，沒有表單，也不載入情境', async () => {
    stubApi(handlers('viewer'))
    await renderApp('/incidents/new')

    expect(screen.getByText('需要 Operator 權限')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '建立事故' })).not.toBeInTheDocument()
    expect(callsTo('GET /api/v1/scenarios')).toHaveLength(0)
  })

  it('operator：以卡片單選顯示三個情境（名稱、服務、描述）', async () => {
    stubApi(handlers('operator'))
    await renderApp('/incidents/new')

    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(3)
    for (const scenario of SCENARIOS) {
      expect(screen.getByText(scenario.name)).toBeInTheDocument()
      expect(screen.getByText(scenario.affected_services.join(', '))).toBeInTheDocument()
      expect(screen.getByText(scenario.description)).toBeInTheDocument()
    }
    expect(radios.every((radio) => !(radio as HTMLInputElement).checked)).toBe(true)

    fireEvent.click(screen.getByRole('radio', { name: /Database Pool Exhaustion/ }))
    expect(screen.getByRole('radio', { name: /Database Pool Exhaustion/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /CPU Spike After Deployment/ })).not.toBeChecked()
  })

  it('選擇情境後 title 預設為 default_title（placeholder 同），可編輯', async () => {
    stubApi(handlers('operator'))
    await renderApp('/incidents/new')
    expect(titleInput()).toHaveValue('')

    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    expect(titleInput()).toHaveValue('checkout-api CPU spike after deployment')
    expect(titleInput()).toHaveAttribute('placeholder', 'checkout-api CPU spike after deployment')

    fireEvent.change(titleInput(), { target: { value: '我的自訂標題' } })
    expect(titleInput()).toHaveValue('我的自訂標題')
  })

  it('未編輯 title 時切換情境，title 跟著新情境的預設值', async () => {
    stubApi(handlers('operator'))
    await renderApp('/incidents/new')

    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    fireEvent.click(screen.getByRole('radio', { name: /Duplicate Alert Storm/ }))
    expect(titleInput()).toHaveValue('notification-worker duplicate alert storm')
  })

  it('驗證：未選情境、空白標題、超過 200 字都不送出', async () => {
    stubApi(handlers('operator'))
    await renderApp('/incidents/new')

    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    expect(screen.getByText('請先選擇一個情境')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    fireEvent.change(titleInput(), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    expect(screen.getByText('標題不可為空')).toBeInTheDocument()

    fireEvent.change(titleInput(), { target: { value: 'x'.repeat(201) } })
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    expect(screen.getByText('標題最多 200 字')).toBeInTheDocument()

    await settle()
    expect(callsTo('POST /api/v1/incidents')).toHaveLength(0)
  })

  it('邊界：1 字與 200 字可以送出', async () => {
    stubApi(handlers('operator'))
    await renderApp('/incidents/new')
    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))

    fireEvent.change(titleInput(), { target: { value: 'x'.repeat(200) } })
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    await settle()
    expect(callsTo('POST /api/v1/incidents')).toHaveLength(1)
  })

  it('送出成功：以 scenario_key 與 title 呼叫 API，導向 /incidents/{id} 並顯示詳情', async () => {
    stubApi(handlers('operator'))
    const { router } = await renderApp('/incidents/new')
    fireEvent.click(screen.getByRole('radio', { name: /Database Pool Exhaustion/ }))
    fireEvent.change(titleInput(), { target: { value: '  連線池耗盡  ' } })

    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    await settle()

    const request = callsTo('POST /api/v1/incidents')[0]
    expect(request?.body).toEqual({ scenario_key: 'db_pool_exhaustion', title: '連線池耗盡' })
    expect(request?.headers.get('Authorization')).toBe('Bearer token-operator')
    expect(router.state.location.pathname).toBe(`/incidents/${CREATED_ID}`)
    expect(screen.getByRole('heading', { level: 1, name: makeDetail().title })).toBeInTheDocument()
  })

  it('送出中停用按鈕，避免重複送出', async () => {
    let resolve: (response: Response) => void = () => undefined
    stubApi(
      handlers(
        'operator',
        () =>
          new Promise<Response>((done) => {
            resolve = done
          }),
      ),
    )
    await renderApp('/incidents/new')
    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    await settle()

    expect(screen.getByRole('button', { name: '建立中…' })).toBeDisabled()
    fireEvent.submit(titleInput().closest('form') ?? document.body)
    await settle()
    expect(callsTo('POST /api/v1/incidents')).toHaveLength(1)

    resolve(jsonResponse(makeDetail({ id: CREATED_ID }), 201))
    await settle()
  })

  it('失敗：顯示友善訊息，不顯示原始 detail，留在本頁可再送', async () => {
    stubApi(handlers('operator', () => jsonResponse({ detail: 'Unknown scenario_key' }, 422)))
    const { router } = await renderApp('/incidents/new')
    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    await settle()

    expect(screen.getByText('找不到所選情境，請重新整理頁面後再試。')).toBeInTheDocument()
    expect(screen.queryByText(/Unknown scenario_key/)).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/incidents/new')
    expect(screen.getByRole('button', { name: '建立事故' })).toBeEnabled()
  })

  it('伺服器錯誤：不顯示原始錯誤內容', async () => {
    stubApi(handlers('operator', () => jsonResponse({ detail: 'sqlalchemy.exc.IntegrityError' }, 500)))
    const { container } = await renderApp('/incidents/new')
    fireEvent.click(screen.getByRole('radio', { name: /CPU Spike After Deployment/ }))
    fireEvent.click(screen.getByRole('button', { name: '建立事故' }))
    await settle()

    expect(screen.getByText('伺服器暫時發生問題，請稍後再試。')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/sqlalchemy|IntegrityError/)
  })

  it('isReady 為 false 時停用送出並提示', async () => {
    stubApi({
      ...handlers('operator'),
      'GET /health/ready': () => jsonResponse({}, 503),
    })
    await renderApp('/incidents/new')

    expect(screen.getByRole('button', { name: '建立事故' })).toBeDisabled()
    expect(screen.getByText('Agent 執行環境尚未就緒，就緒後即可送出。')).toBeInTheDocument()
  })

  it('情境載入失敗：友善訊息與重試', async () => {
    let fail = true
    stubApi({
      ...handlers('operator'),
      'GET /api/v1/scenarios': () => (fail ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(SCENARIOS)),
    })
    await renderApp('/incidents/new')
    expect(screen.getByText('無法載入情境，請重試。')).toBeInTheDocument()

    fail = false
    fireEvent.click(screen.getByRole('button', { name: '重試' }))
    await settle()
    expect(screen.getAllByRole('radio')).toHaveLength(3)
  })
})
