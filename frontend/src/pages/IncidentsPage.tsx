import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { canCreateIncident, useAuth } from '../features/auth'
import {
  INCIDENT_STATUSES,
  PAGE_SIZE,
  PublicBadge,
  SeverityBadge,
  StatusBadge,
  fetchIncidents,
  incidentKeys,
} from '../features/incidents'
import type { IncidentList, IncidentStatus } from '../features/incidents'
import { formatDateTime } from '../lib/format'

const CELL = 'block px-3 py-1 before:mr-2 before:text-xs before:text-slate-400 before:content-[attr(data-label)] md:table-cell md:py-3 md:before:hidden'
const BUTTON =
  'rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent'

function IncidentTable({ data }: { data: IncidentList }) {
  return (
    <table className="block w-full text-left text-sm md:table">
      <thead className="sr-only md:not-sr-only md:table-header-group">
        <tr className="border-b border-slate-800 text-xs uppercase text-slate-400 md:table-row">
          <th scope="col" className="px-3 py-2 font-medium">標題</th>
          <th scope="col" className="px-3 py-2 font-medium">severity</th>
          <th scope="col" className="px-3 py-2 font-medium">status</th>
          <th scope="col" className="px-3 py-2 font-medium">服務</th>
          <th scope="col" className="px-3 py-2 font-medium">更新時間</th>
          <th scope="col" className="px-3 py-2 font-medium">公開</th>
        </tr>
      </thead>
      <tbody className="block md:table-row-group">
        {data.items.map((incident) => (
          <tr
            key={incident.id}
            className="mb-3 block rounded-lg border border-slate-800 bg-slate-900/60 py-2 md:mb-0 md:table-row md:rounded-none md:border-0 md:border-b md:bg-transparent md:py-0"
          >
            <td className={CELL}>
              <Link
                to={`/incidents/${incident.id}`}
                className="break-words font-medium text-cyan-300 hover:text-cyan-200 hover:underline"
              >
                {incident.title}
              </Link>
            </td>
            <td className={CELL} data-label="severity">
              <SeverityBadge severity={incident.severity} />
            </td>
            <td className={CELL} data-label="status">
              <StatusBadge status={incident.status} />
            </td>
            <td className={`${CELL} break-all font-mono text-xs text-slate-200`} data-label="服務">
              {incident.affected_services.join(', ')}
            </td>
            <td className={`${CELL} text-slate-300`} data-label="更新時間">
              <time dateTime={incident.updated_at}>{formatDateTime(incident.updated_at)}</time>
            </td>
            <td className={CELL} data-label="公開">
              <PublicBadge isPublic={incident.is_public} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function IncidentsPage() {
  const { user } = useAuth()
  const [status, setStatus] = useState<IncidentStatus | null>(null)
  const [offset, setOffset] = useState(0)

  const query = useQuery({
    queryKey: incidentKeys.list(status, offset),
    queryFn: ({ signal }) => fetchIncidents(status, offset, signal),
    placeholderData: keepPreviousData,
  })

  const canCreate = user !== null && canCreateIncident(user.role)
  const data = query.data

  const renderBody = () => {
    if (query.isError) {
      return (
        <div role="alert" className="space-y-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-5">
          <p className="text-sm text-rose-200">無法載入事故列表，請重試。</p>
          <button
            type="button"
            onClick={() => {
              void query.refetch()
            }}
            className="rounded border border-rose-400/50 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20"
          >
            重試
          </button>
        </div>
      )
    }
    if (data === undefined) {
      return (
        <p role="status" className="text-sm text-slate-300">
          正在載入事故列表…
        </p>
      )
    }
    if (data.items.length === 0) {
      if (offset > 0) {
        return (
          <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-6">
            <p className="text-slate-200">這一頁沒有資料。</p>
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                setOffset(0)
              }}
            >
              回到第一頁
            </button>
          </div>
        )
      }
      if (status !== null) {
        return (
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-slate-200">
            沒有符合此狀態的事故。
          </div>
        )
      }
      return (
        <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-6">
          {canCreate ? (
            <Link
              to="/incidents/new"
              className="inline-block rounded border border-cyan-500/50 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/10"
            >
              尚無事故，建立第一筆
            </Link>
          ) : (
            <p className="text-slate-200">目前沒有公開範例</p>
          )}
        </div>
      )
    }

    const first = data.offset + 1
    const last = data.offset + data.items.length
    return (
      <div className="space-y-4">
        <IncidentTable data={data} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-400">
            第 {first}–{last} 筆，共 {data.total} 筆
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className={BUTTON}
              disabled={offset === 0}
              onClick={() => {
                setOffset(Math.max(0, offset - PAGE_SIZE))
              }}
            >
              上一頁
            </button>
            <button
              type="button"
              className={BUTTON}
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => {
                setOffset(offset + PAGE_SIZE)
              }}
            >
              下一頁
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-bold text-white sm:text-3xl">Incidents</h1>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          狀態
          <select
            value={status ?? ''}
            onChange={(event) => {
              const value = event.target.value
              setStatus(value === '' ? null : (value as IncidentStatus))
              setOffset(0)
            }}
            className="rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          >
            <option value="">全部</option>
            {INCIDENT_STATUSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      {renderBody()}
    </div>
  )
}
