import { act, render, screen } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { routes } from './routes'

const fetchMock = vi.fn<typeof fetch>()

async function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<App router={router} />)
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(new Response(JSON.stringify({ status: 'ready' }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Landing', () => {
  it('渲染標題與三個情境卡片', async () => {
    await renderAt('/')

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'AgentOps Commander — AI Multi-Agent Incident Response Platform',
      }),
    ).toBeInTheDocument()

    for (const [title, service] of [
      ['CPU Spike After Deployment', 'checkout-api'],
      ['Database Pool Exhaustion', 'student-portal-api'],
      ['Duplicate Alert Storm', 'notification-worker'],
    ] as const) {
      expect(screen.getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
      expect(screen.getByText(service)).toBeInTheDocument()
    }
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('提供進入事故列表的連結', async () => {
    await renderAt('/')
    expect(screen.getByRole('link', { name: '進入事故列表' })).toHaveAttribute('href', '/incidents')
  })

  it('layout 顯示後端狀態 banner', async () => {
    await renderAt('/')
    expect(screen.getByText('已就緒')).toBeInTheDocument()
  })
})

describe('404', () => {
  it('未知路徑渲染 404 頁並提供回首頁連結', async () => {
    await renderAt('/no-such-page')

    expect(screen.getByRole('heading', { name: '找不到這個頁面' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '回首頁' })).toHaveAttribute('href', '/')
  })
})
