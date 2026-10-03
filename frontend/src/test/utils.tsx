import { act, render } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { vi } from 'vitest'

import { App } from '../app/App'
import { routes } from '../app/routes'
import type { AuthUser, Role } from '../features/auth'
import type { IncidentDetail, IncidentEvent, IncidentSummary, Scenario } from '../features/incidents'
import { writeToken } from '../lib/tokenStore'

export interface StubRequest {
  url: URL
  method: string
  headers: Headers
  body: unknown
}

export type StubHandler = (request: StubRequest) => Response | Promise<Response>

/**
 * 只實作 apiFetch 與 readiness 探測會用到的 Response 成員（ok、status、json）。
 * 不用真正的 Response 串流，避免 fake timers 下讀取 body 需要真實事件迴圈而讓測試不穩定。
 */
export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

export const fetchStub = vi.fn<typeof fetch>()

/**
 * 以 "METHOD /path" 為鍵註冊 fetch stub；/health/ready 預設回 ready。
 * 沒有對應 handler 的請求會 reject，讓測試直接失敗而不是默默通過。
 */
export function stubApi(handlers: Record<string, StubHandler>): typeof fetchStub {
  const table: Record<string, StubHandler> = {
    'GET /health/ready': () => jsonResponse({ status: 'ready' }),
    ...handlers,
  }
  fetchStub.mockReset()
  fetchStub.mockImplementation((input, init) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url)
    const method = init?.method ?? 'GET'
    const handler = table[`${method} ${url.pathname}`]
    if (handler === undefined) {
      return Promise.reject(new Error(`Unhandled stub request: ${method} ${url.pathname}`))
    }
    const rawBody = init?.body
    return Promise.resolve(
      handler({
        url,
        method,
        headers: new Headers(init?.headers),
        body: typeof rawBody === 'string' ? (JSON.parse(rawBody) as unknown) : undefined,
      }),
    )
  })
  vi.stubGlobal('fetch', fetchStub)
  return fetchStub
}

export function callsTo(key: string): StubRequest[] {
  const [method = '', path = ''] = key.split(' ')
  return fetchStub.mock.calls
    .filter(([input, init]) => {
      const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url)
      return (init?.method ?? 'GET') === method && url.pathname === path
    })
    .map(([input, init]) => ({
      url: new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url),
      method,
      headers: new Headers(init?.headers),
      body: typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined,
    }))
}

/** 讓 fake timers 下的 promise、react-query 通知與 React 更新都跑完。 */
export async function settle(): Promise<void> {
  for (let i = 0; i < 6; i += 1) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10)
    })
  }
}

export async function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const result = render(<App router={router} />)
  await settle()
  return { router, ...result }
}

export const USERS: Record<Role, AuthUser> = {
  viewer: { id: '00000000-0000-4000-8000-000000000001', email: 'viewer@demo.local', display_name: 'Demo Viewer', role: 'viewer' },
  operator: { id: '00000000-0000-4000-8000-000000000002', email: 'operator@demo.local', display_name: 'Demo Operator', role: 'operator' },
  admin: { id: '00000000-0000-4000-8000-000000000003', email: 'admin@demo.local', display_name: 'Demo Admin', role: 'admin' },
}

/** 預先寫入 token 並讓 /me 回傳指定角色，代表已登入。 */
export function signedInHandlers(role: Role): Record<string, StubHandler> {
  writeToken(`token-${role}`)
  return { 'GET /api/v1/me': () => jsonResponse(USERS[role]) }
}

export function makeIncident(overrides: Partial<IncidentSummary> = {}): IncidentSummary {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    title: 'checkout-api CPU spike after deployment',
    scenario_key: 'cpu_spike_after_deploy',
    severity: null,
    status: 'open',
    affected_services: ['checkout-api'],
    is_public: false,
    owner_id: USERS.operator.id,
    created_at: '2026-10-03T08:00:00Z',
    updated_at: '2026-10-03T08:30:00Z',
    ...overrides,
  }
}

export function makeDetail(overrides: Partial<IncidentDetail> = {}): IncidentDetail {
  return {
    ...makeIncident(),
    resolved_at: null,
    alert: {
      summary: 'checkout-api CPU at 95%, p95 latency and HTTP 5xx rate rising',
      source: 'metrics-alerting',
      fired_at_offset_minutes: -5,
      symptoms: ['CPU utilization at 95%', 'p95 latency increasing'],
    },
    ...overrides,
  }
}

export function makeEvent(overrides: Partial<IncidentEvent> = {}): IncidentEvent {
  return {
    id: '22222222-2222-4222-8222-222222222222',
    event_type: 'incident.created',
    agent_name: null,
    summary: 'Incident created from scenario cpu_spike_after_deploy',
    payload: {},
    created_at: '2026-10-03T08:00:00Z',
    ...overrides,
  }
}

export const SCENARIOS: Scenario[] = [
  {
    key: 'cpu_spike_after_deploy',
    name: 'CPU Spike After Deployment',
    description: 'A new release of checkout-api was deployed shortly before CPU usage climbed.',
    default_title: 'checkout-api CPU spike after deployment',
    affected_services: ['checkout-api'],
    alert: { summary: 'cpu', source: 'metrics-alerting', fired_at_offset_minutes: -5, symptoms: ['cpu'] },
  },
  {
    key: 'db_pool_exhaustion',
    name: 'Database Pool Exhaustion',
    description: 'Connection pool exhausted.',
    default_title: 'student-portal-api database pool exhaustion',
    affected_services: ['student-portal-api'],
    alert: { summary: 'db', source: 'log-alerting', fired_at_offset_minutes: -3, symptoms: ['db'] },
  },
  {
    key: 'duplicate_alert_storm',
    name: 'Duplicate Alert Storm',
    description: 'Duplicate incidents created.',
    default_title: 'notification-worker duplicate alert storm',
    affected_services: ['notification-worker'],
    alert: { summary: 'dup', source: 'incident-bot', fired_at_offset_minutes: -1, symptoms: ['dup'] },
  },
]
