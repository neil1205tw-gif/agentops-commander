import { useCallback, useEffect, useState } from 'react'

import { API_BASE_URL } from '../../lib/config'
import { REQUEST_TIMEOUT_MS, RETRY_INTERVAL_MS, UNAVAILABLE_AFTER_MS } from './constants'

export type ReadinessStatus = 'checking' | 'warming' | 'ready' | 'unavailable'

export interface BackendReadiness {
  status: ReadinessStatus
  isReady: boolean
  /** 已失敗的嘗試次數。 */
  attempts: number
  /** 下次自動重試的時間（epoch ms），僅在 warming 時有值。 */
  nextRetryAt: number | null
  /** 重新開始檢查（回到 checking 並重新計時）。 */
  recheck: () => void
}

interface MachineState {
  status: ReadinessStatus
  attempts: number
  nextRetryAt: number | null
}

const INITIAL_STATE: MachineState = { status: 'checking', attempts: 0, nextRetryAt: null }

async function probeReady(signal: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health/ready`, { signal, cache: 'no-store' })
    if (response.status !== 200) {
      return false
    }
    const body = (await response.json()) as { status?: unknown } | null
    return body?.status === 'ready'
  } catch {
    // 網路錯誤、逾時、非 JSON：一律視為尚未就緒，不對外暴露原始錯誤。
    return false
  }
}

export function useBackendReadiness(): BackendReadiness {
  const [state, setState] = useState<MachineState>(INITIAL_STATE)
  const [runId, setRunId] = useState(0)

  useEffect(() => {
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined
    let attempts = 0
    let firstFailureAt: number | null = null

    const attempt = async () => {
      const current = new AbortController()
      controller = current
      const timeoutTimer = setTimeout(() => {
        current.abort()
      }, REQUEST_TIMEOUT_MS)
      const ok = await probeReady(current.signal)
      clearTimeout(timeoutTimer)
      if (cancelled) {
        return
      }

      if (ok) {
        setState({ status: 'ready', attempts, nextRetryAt: null })
        return
      }

      attempts += 1
      const now = Date.now()
      firstFailureAt ??= now
      if (now - firstFailureAt > UNAVAILABLE_AFTER_MS) {
        setState({ status: 'unavailable', attempts, nextRetryAt: null })
        return
      }

      setState({ status: 'warming', attempts, nextRetryAt: now + RETRY_INTERVAL_MS })
      retryTimer = setTimeout(() => {
        void attempt()
      }, RETRY_INTERVAL_MS)
    }

    void attempt()

    return () => {
      cancelled = true
      clearTimeout(retryTimer)
      controller?.abort()
    }
  }, [runId])

  const recheck = useCallback(() => {
    setState(INITIAL_STATE)
    setRunId((id) => id + 1)
  }, [])

  return {
    status: state.status,
    isReady: state.status === 'ready',
    attempts: state.attempts,
    nextRetryAt: state.nextRetryAt,
    recheck,
  }
}
