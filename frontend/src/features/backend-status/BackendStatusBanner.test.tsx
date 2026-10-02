import { act, fireEvent, render, screen } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useBackendStatus } from './BackendReadinessContext'
import { BackendReadinessProvider } from './BackendReadinessProvider'
import { BackendStatusBanner } from './BackendStatusBanner'

const fetchMock = vi.fn<typeof fetch>()

function readyResponse() {
  return new Response(JSON.stringify({ status: 'ready' }), { status: 200 })
}

function networkError() {
  return Promise.reject(new TypeError('Failed to fetch'))
}

/** 以 5 秒為單位推進假時間，讓每一段的 React 更新都能在 act 內完整套用。 */
async function advance(ms: number) {
  let remaining = ms
  do {
    const step = Math.min(remaining, 5_000)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(step)
    })
    remaining -= step
  } while (remaining > 0)
}

/** 記錄自己被 mount 的次數，用來確認狀態切換過程中頁面沒有 remount。 */
function MountProbe({ onMount }: { onMount: () => void }) {
  const callback = useRef(onMount)
  useEffect(() => {
    callback.current()
  }, [])
  return <p>probe</p>
}

function ReadyConsumer() {
  const { isReady } = useBackendStatus()
  return <button disabled={!isReady}>Run</button>
}

function renderBanner(extra?: ReactNode) {
  return render(
    <BackendReadinessProvider>
      <BackendStatusBanner />
      {extra}
    </BackendReadinessProvider>,
  )
}

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('BackendStatusBanner', () => {
  it('第一次請求完成前顯示 checking', () => {
    fetchMock.mockReturnValue(new Promise(() => undefined))
    renderBanner()
    expect(screen.getByText('正在連線 Agent 執行環境…')).toBeInTheDocument()
  })

  it('後端第一次就 ready：顯示已就緒且不再發出請求', async () => {
    fetchMock.mockResolvedValue(readyResponse())
    renderBanner()
    await advance(0)

    expect(screen.getByText('已就緒')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/health/ready', expect.anything())

    await advance(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('前兩次失敗、第三次 ready：warming（含倒數與次數）後自動恢復，且不 remount', async () => {
    fetchMock
      .mockImplementationOnce(networkError)
      .mockImplementationOnce(networkError)
      .mockResolvedValueOnce(readyResponse())
    const onMount = vi.fn()
    renderBanner(<MountProbe onMount={onMount} />)
    await advance(0)

    expect(screen.getByText('Agent 執行環境正在啟動，可能需要 30–90 秒')).toBeInTheDocument()
    expect(screen.getByText(/5 秒後重試/)).toBeInTheDocument()
    expect(screen.getByText(/已嘗試 1 次/)).toBeInTheDocument()

    await advance(2_000)
    expect(screen.getByText(/3 秒後重試/)).toBeInTheDocument()

    await advance(3_000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.getByText(/已嘗試 2 次/)).toBeInTheDocument()
    expect(screen.getByText(/5 秒後重試/)).toBeInTheDocument()

    await advance(5_000)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(screen.getByText('已就緒')).toBeInTheDocument()
    expect(screen.queryByText(/秒後重試/)).not.toBeInTheDocument()

    await advance(30_000)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(onMount).toHaveBeenCalledTimes(1)
  })

  it('非 200 或 body 非 ready 都視為 warming', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response('{}', { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'not_ready' }), { status: 200 }))
      .mockResolvedValueOnce(new Response('<html>oops</html>', { status: 200 }))
    renderBanner()
    await advance(0)
    expect(screen.getByText(/已嘗試 1 次/)).toBeInTheDocument()
    await advance(5_000)
    expect(screen.getByText(/已嘗試 2 次/)).toBeInTheDocument()
    await advance(5_000)
    expect(screen.getByText(/已嘗試 3 次/)).toBeInTheDocument()
    expect(screen.queryByText('已就緒')).not.toBeInTheDocument()
  })

  it('單次請求 10 秒逾時後進入 warming', async () => {
    fetchMock.mockImplementation(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted.', 'AbortError'))
          })
        }),
    )
    renderBanner()
    await advance(9_000)
    expect(screen.getByText('正在連線 Agent 執行環境…')).toBeInTheDocument()

    await advance(1_000)
    expect(screen.getByText(/已嘗試 1 次/)).toBeInTheDocument()
    expect(screen.queryByText(/AbortError|aborted/)).not.toBeInTheDocument()
  })

  it('失敗持續超過 180 秒：顯示 unavailable，按下重新檢查後重新請求', async () => {
    fetchMock.mockImplementation(networkError)
    renderBanner()
    await advance(0)

    await advance(180_000)
    expect(screen.getByText(/已嘗試 37 次/)).toBeInTheDocument()

    await advance(5_000)
    expect(screen.getByText('Agent 執行環境暫時無法連線')).toBeInTheDocument()
    const callsWhenUnavailable = fetchMock.mock.calls.length

    await advance(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(callsWhenUnavailable)

    fetchMock.mockReset()
    fetchMock.mockResolvedValue(readyResponse())
    fireEvent.click(screen.getByRole('button', { name: '重新檢查' }))
    expect(screen.getByText('正在連線 Agent 執行環境…')).toBeInTheDocument()
    await advance(0)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByText('已就緒')).toBeInTheDocument()
  })

  it('重新檢查會重新開始 180 秒計時', async () => {
    fetchMock.mockImplementation(networkError)
    renderBanner()
    await advance(185_000)
    expect(screen.getByRole('button', { name: '重新檢查' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '重新檢查' }))
    await advance(100_000)
    expect(screen.queryByRole('button', { name: '重新檢查' })).not.toBeInTheDocument()
    expect(screen.getByText(/秒後重試/)).toBeInTheDocument()
  })

  it('網路錯誤時任何狀態都不顯示原始錯誤字串', async () => {
    fetchMock.mockImplementation(networkError)
    const { container } = renderBanner()

    for (const elapsed of [0, 5_000, 200_000]) {
      await advance(elapsed)
      expect(container.textContent).not.toMatch(/TypeError|Failed to fetch/)
    }
    expect(screen.getByText('Agent 執行環境暫時無法連線')).toBeInTheDocument()
  })

  it('isReady 讓其他元件決定是否啟用操作按鈕', async () => {
    fetchMock.mockImplementationOnce(networkError).mockResolvedValueOnce(readyResponse())
    renderBanner(<ReadyConsumer />)
    await advance(0)
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()

    await advance(5_000)
    expect(screen.getByRole('button', { name: 'Run' })).toBeEnabled()
  })
})
