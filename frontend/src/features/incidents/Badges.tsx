import type { IncidentSeverity, IncidentStatus } from './types'

const BASE = 'inline-block rounded border px-2 py-0.5 font-mono text-xs'

const SEVERITY_STYLES: Record<IncidentSeverity, string> = {
  P1: 'border-rose-500/60 bg-rose-500/10 text-rose-200',
  P2: 'border-orange-500/60 bg-orange-500/10 text-orange-200',
  P3: 'border-amber-500/60 bg-amber-500/10 text-amber-200',
  P4: 'border-sky-500/60 bg-sky-500/10 text-sky-200',
}

export function SeverityBadge({ severity }: { severity: IncidentSeverity | null }) {
  if (severity === null) {
    return <span className={`${BASE} border-slate-600 bg-slate-800/60 text-slate-300`}>待分類</span>
  }
  return <span className={`${BASE} ${SEVERITY_STYLES[severity]}`}>{severity}</span>
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return <span className={`${BASE} border-cyan-500/40 bg-cyan-500/10 text-cyan-200`}>{status}</span>
}

export function PublicBadge({ isPublic }: { isPublic: boolean }) {
  return isPublic ? (
    <span className={`${BASE} border-emerald-500/50 bg-emerald-500/10 text-emerald-200`}>公開</span>
  ) : (
    <span className={`${BASE} border-slate-600 bg-slate-800/60 text-slate-300`}>私有</span>
  )
}
