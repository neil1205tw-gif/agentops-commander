import { Link, NavLink, Outlet } from 'react-router'

import { RoleBadge, canCreateIncident, useAuth } from '../features/auth'
import { BackendStatusBanner } from '../features/backend-status'

const NAV_LINK = 'text-sm text-slate-300 hover:text-white aria-[current=page]:text-cyan-300'

export function Layout() {
  const { status, user, logout } = useAuth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <nav
          aria-label="主要導覽"
          className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3"
        >
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Link
              to="/"
              className="font-mono text-sm font-semibold tracking-wide text-cyan-300 hover:text-cyan-200"
            >
              AgentOps Commander
            </Link>
            {status === 'authenticated' && user !== null ? (
              <>
                <NavLink to="/incidents" end className={NAV_LINK}>
                  Incidents
                </NavLink>
                {canCreateIncident(user.role) ? (
                  <NavLink to="/incidents/new" className={NAV_LINK}>
                    New Incident
                  </NavLink>
                ) : null}
              </>
            ) : null}
          </div>
          {status === 'authenticated' && user !== null ? (
            <div className="flex min-w-0 flex-wrap items-center gap-3">
              <span className="min-w-0 break-all text-xs text-slate-300">
                {user.email ?? user.display_name ?? user.id}
              </span>
              <RoleBadge role={user.role} />
              <button
                type="button"
                onClick={logout}
                className="rounded border border-slate-600 px-3 py-1 text-xs font-medium text-slate-100 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
              >
                登出
              </button>
            </div>
          ) : status === 'anonymous' ? (
            <NavLink to="/login" className={NAV_LINK}>
              登入
            </NavLink>
          ) : null}
        </nav>
        <BackendStatusBanner />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:py-16">
        <Outlet />
      </main>
    </div>
  )
}
