import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from '../features/auth'
import type { Role } from '../features/auth'
import { useBackendStatus } from '../features/backend-status'
import { apiFetch } from '../lib/api'
import { describeApiError } from '../lib/errors'

interface AuthConfig {
  dev_login_enabled: boolean
}

const DEV_ROLES: { role: Role; label: string }[] = [
  { role: 'viewer', label: '以 Viewer 登入（開發模式）' },
  { role: 'operator', label: '以 Operator 登入（開發模式）' },
  { role: 'admin', label: '以 Admin 登入（開發模式）' },
]

/** 登入後回跳的目標；只接受站內路徑。 */
function redirectTarget(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from
  if (
    typeof from === 'string' &&
    from.startsWith('/') &&
    !from.startsWith('//') &&
    !from.startsWith('/login')
  ) {
    return from
  }
  return '/incidents'
}

export function LoginPage() {
  const { status, loginAsDev } = useAuth()
  const { isReady } = useBackendStatus()
  const location = useLocation()
  const [pendingRole, setPendingRole] = useState<Role | null>(null)
  const [error, setError] = useState<string | null>(null)

  // key 含 isReady：後端從 warming 轉為 ready 時自動重新取得，不需要重新整理頁面。
  const config = useQuery({
    queryKey: ['auth-config', isReady],
    queryFn: ({ signal }) => apiFetch<AuthConfig>('/api/v1/auth/config', { signal }),
  })

  if (status === 'authenticated') {
    return <Navigate to={redirectTarget(location.state)} replace />
  }
  if (status === 'loading') {
    return (
      <p role="status" className="text-sm text-slate-300">
        正在確認登入狀態…
      </p>
    )
  }

  const devEnabled = config.data?.dev_login_enabled
  const handleLogin = (role: Role) => {
    setError(null)
    setPendingRole(role)
    loginAsDev(role)
      .catch((cause: unknown) => {
        setError(describeApiError(cause, '登入失敗，請稍後再試。'))
      })
      .finally(() => {
        setPendingRole(null)
      })
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-white sm:text-3xl">登入</h1>
        <p className="text-sm text-slate-300">登入後即可查看與建立事故。</p>
      </div>

      {devEnabled === false ? (
        <section
          aria-label="登入方式"
          className="rounded-lg border border-slate-800 bg-slate-900/60 p-5"
        >
          <p className="font-medium text-white">此環境的正式登入尚未啟用</p>
          <p className="mt-2 text-sm text-slate-300">請稍後再試，或聯絡管理員。</p>
        </section>
      ) : config.isError && isReady ? (
        <section role="alert" className="space-y-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-5">
          <p className="text-sm text-rose-200">無法取得登入方式，請重試。</p>
          <button
            type="button"
            onClick={() => {
              void config.refetch()
            }}
            className="rounded border border-rose-400/50 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20"
          >
            重試
          </button>
        </section>
      ) : (
        <section
          aria-label="登入方式"
          className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-5"
        >
          <p className="text-sm text-amber-200">
            這是本機開發用的登入入口，只在開發模式提供，不代表正式登入方式。
          </p>
          <div className="flex flex-col gap-3">
            {DEV_ROLES.map(({ role, label }) => (
              <button
                key={role}
                type="button"
                disabled={!isReady || devEnabled !== true || pendingRole !== null}
                onClick={() => {
                  handleLogin(role)
                }}
                className="rounded border border-cyan-500/50 px-4 py-2 text-left text-sm font-medium text-cyan-100 hover:bg-cyan-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
              >
                {pendingRole === role ? '登入中…' : label}
              </button>
            ))}
          </div>
          {!isReady ? (
            <p className="text-xs text-slate-400">Agent 執行環境尚未就緒，就緒後即可登入。</p>
          ) : devEnabled === undefined ? (
            <p className="text-xs text-slate-400">正在確認登入方式…</p>
          ) : null}
          {error !== null ? (
            <p role="alert" className="text-sm text-rose-300">
              {error}
            </p>
          ) : null}
        </section>
      )}
    </div>
  )
}
