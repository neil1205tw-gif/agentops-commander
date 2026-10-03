import type { Role } from './types'

const STYLES: Record<Role, string> = {
  viewer: 'border-slate-500/50 bg-slate-500/10 text-slate-200',
  operator: 'border-cyan-500/50 bg-cyan-500/10 text-cyan-200',
  admin: 'border-amber-500/50 bg-amber-500/10 text-amber-200',
}

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={`rounded border px-2 py-0.5 font-mono text-xs uppercase ${STYLES[role]}`}
      data-role={role}
    >
      {role}
    </span>
  )
}
