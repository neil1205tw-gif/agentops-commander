import { Link, Outlet } from 'react-router'

import { BackendStatusBanner } from '../features/backend-status'

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <nav
          aria-label="主要導覽"
          className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3"
        >
          <Link
            to="/"
            className="font-mono text-sm font-semibold tracking-wide text-cyan-300 hover:text-cyan-200"
          >
            AgentOps Commander
          </Link>
          <span className="rounded border border-slate-700 px-2 py-0.5 font-mono text-[11px] uppercase tracking-widest text-slate-400">
            Simulation
          </span>
        </nav>
        <BackendStatusBanner />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:py-16">
        <Outlet />
      </main>
    </div>
  )
}
