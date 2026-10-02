import { useBackendStatus } from './BackendReadinessContext'
import { useSecondsUntil } from './useSecondsUntil'

const BASE = 'border-b px-4 py-2 text-sm'

function WarmingStatus({ attempts, nextRetryAt }: { attempts: number; nextRetryAt: number | null }) {
  const seconds = useSecondsUntil(nextRetryAt)
  return (
    <div
      role="status"
      className={`${BASE} border-amber-500/30 bg-amber-500/10 text-amber-200`}
      data-status="warming"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-medium">Agent 執行環境正在啟動，可能需要 30–90 秒</span>
        <span className="font-mono text-xs text-amber-300/80">
          {seconds === null || seconds === 0 ? '正在重試…' : `${seconds} 秒後重試`}
          {' · '}已嘗試 {attempts} 次
        </span>
      </div>
    </div>
  )
}

export function BackendStatusBanner() {
  const { status, attempts, nextRetryAt, recheck } = useBackendStatus()

  switch (status) {
    case 'checking':
      return (
        <div
          role="status"
          className={`${BASE} border-slate-700 bg-slate-900 text-slate-300`}
          data-status="checking"
        >
          <div className="mx-auto max-w-6xl">正在連線 Agent 執行環境…</div>
        </div>
      )
    case 'warming':
      return <WarmingStatus attempts={attempts} nextRetryAt={nextRetryAt} />
    case 'ready':
      return (
        <div
          role="status"
          className={`${BASE} border-emerald-500/30 bg-emerald-500/10 text-emerald-200`}
          data-status="ready"
        >
          <div className="mx-auto max-w-6xl">已就緒</div>
        </div>
      )
    case 'unavailable':
      return (
        <div
          role="alert"
          className={`${BASE} border-rose-500/30 bg-rose-500/10 text-rose-200`}
          data-status="unavailable"
        >
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2">
            <span className="font-medium">Agent 執行環境暫時無法連線</span>
            <button
              type="button"
              onClick={recheck}
              className="rounded border border-rose-400/50 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
            >
              重新檢查
            </button>
          </div>
        </div>
      )
  }
}
