import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { useAuth } from '../features/auth'
import {
  PublicBadge,
  SeverityBadge,
  StatusBadge,
  deleteIncident,
  fetchIncident,
  fetchIncidentEvents,
  incidentKeys,
  setIncidentVisibility,
} from '../features/incidents'
import type { IncidentDetail, IncidentEvent } from '../features/incidents'
import { ApiError } from '../lib/api'
import { describeApiError } from '../lib/errors'
import { formatDateTime } from '../lib/format'

const BUTTON =
  'rounded border px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50'

function ConfirmDeleteDialog({
  title,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  title: string
  pending: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    cancelRef.current?.focus()
  }, [])

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/70 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        onKeyDown={(event) => {
          if (event.key === 'Escape' && !pending) {
            onCancel()
          }
        }}
        className="w-full max-w-md space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-6"
      >
        <h2 id="delete-dialog-title" className="text-lg font-semibold text-white">
          確定要刪除這筆事故？
        </h2>
        <p className="break-words text-sm text-slate-300">「{title}」刪除後將從列表中消失。</p>
        {error !== null ? (
          <p role="alert" className="text-sm text-rose-300">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-3">
          <button
            ref={cancelRef}
            type="button"
            disabled={pending}
            onClick={onCancel}
            className={`${BUTTON} border-slate-600 text-slate-100 hover:bg-slate-800 focus-visible:ring-slate-300`}
          >
            取消
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={onConfirm}
            className={`${BUTTON} border-rose-500/60 text-rose-100 hover:bg-rose-500/20 focus-visible:ring-rose-300`}
          >
            {pending ? '刪除中…' : '確認刪除'}
          </button>
        </div>
      </div>
    </div>
  )
}

function EventList({ incidentId }: { incidentId: string }) {
  const events = useQuery({
    queryKey: incidentKeys.events(incidentId),
    queryFn: ({ signal }) => fetchIncidentEvents(incidentId, signal),
  })

  let body
  if (events.isError) {
    body = (
      <div role="alert" className="space-y-3 text-sm text-rose-200">
        <p>無法載入事件列表。</p>
        <button
          type="button"
          onClick={() => {
            void events.refetch()
          }}
          className="rounded border border-rose-400/50 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20"
        >
          重試
        </button>
      </div>
    )
  } else if (events.data === undefined) {
    body = (
      <p role="status" className="text-sm text-slate-300">
        正在載入事件…
      </p>
    )
  } else if (events.data.length === 0) {
    body = <p className="text-sm text-slate-300">尚無事件。</p>
  } else {
    const sorted: IncidentEvent[] = [...events.data].sort(
      (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
    )
    body = (
      <ol className="space-y-2">
        {sorted.map((event) => (
          <li
            key={event.id}
            className="rounded border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm"
          >
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
              <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
              <span className="font-mono text-cyan-300">{event.event_type}</span>
              {event.agent_name !== null ? <span className="font-mono">{event.agent_name}</span> : null}
            </div>
            <p className="mt-1 break-words text-slate-100">{event.summary}</p>
          </li>
        ))}
      </ol>
    )
  }

  return (
    <section aria-labelledby="events-heading" className="space-y-3">
      <h2 id="events-heading" className="text-lg font-semibold text-white">
        事件列表
      </h2>
      {body}
    </section>
  )
}

function IncidentView({ incident }: { incident: IncidentDetail }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)

  const isOwner = user !== null && user.id === incident.owner_id
  const isAdmin = user?.role === 'admin'
  const canDelete = user !== null && user.role !== 'viewer' && (isOwner || isAdmin)

  const remove = useMutation({
    mutationFn: () => deleteIncident(incident.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: incidentKeys.all })
      void navigate('/incidents')
      queryClient.removeQueries({ queryKey: incidentKeys.detail(incident.id) })
    },
  })

  const toggle = useMutation({
    mutationFn: (isPublic: boolean) => setIncidentVisibility(incident.id, isPublic),
    onSuccess: (updated) => {
      queryClient.setQueryData(incidentKeys.detail(incident.id), updated)
      void queryClient.invalidateQueries({ queryKey: incidentKeys.all })
      void queryClient.invalidateQueries({ queryKey: incidentKeys.events(incident.id) })
    },
  })

  return (
    <div className="space-y-8">
      <Link to="/incidents" className="text-sm text-cyan-300 hover:text-cyan-200 hover:underline">
        ← 返回事故列表
      </Link>

      <header className="space-y-4">
        <h1 className="break-words text-2xl font-bold text-white sm:text-3xl">{incident.title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
          <PublicBadge isPublic={incident.is_public} />
        </div>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-400">服務</dt>
            <dd className="break-all font-mono text-slate-100">
              {incident.affected_services.join(', ')}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">建立時間</dt>
            <dd className="text-slate-100">
              <time dateTime={incident.created_at}>{formatDateTime(incident.created_at)}</time>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">擁有者</dt>
            <dd className="text-slate-100">
              {isOwner ? '你' : `其他使用者（${incident.owner_id.slice(0, 8)}）`}
            </dd>
          </div>
        </dl>

        {isAdmin || canDelete ? (
          <div className="flex flex-wrap gap-3">
            {isAdmin ? (
              <button
                type="button"
                disabled={toggle.isPending}
                onClick={() => {
                  toggle.mutate(!incident.is_public)
                }}
                className={`${BUTTON} border-emerald-500/50 text-emerald-100 hover:bg-emerald-500/10 focus-visible:ring-emerald-300`}
              >
                {incident.is_public ? '設為私有' : '設為公開'}
              </button>
            ) : null}
            {canDelete ? (
              <button
                type="button"
                onClick={() => {
                  remove.reset()
                  setConfirming(true)
                }}
                className={`${BUTTON} border-rose-500/50 text-rose-100 hover:bg-rose-500/10 focus-visible:ring-rose-300`}
              >
                刪除
              </button>
            ) : null}
          </div>
        ) : null}
        {toggle.isError ? (
          <p role="alert" className="text-sm text-rose-300">
            {describeApiError(toggle.error, '更新公開狀態失敗，請稍後再試。')}
          </p>
        ) : null}
      </header>

      <section aria-labelledby="alert-heading" className="space-y-3">
        <h2 id="alert-heading" className="text-lg font-semibold text-white">
          告警
        </h2>
        {incident.alert === null ? (
          <p className="text-sm text-slate-300">此事故的告警資料已不可用。</p>
        ) : (
          <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-5">
            <p className="break-words text-slate-100">{incident.alert.summary}</p>
            <p className="text-xs text-slate-400">
              來源 <span className="font-mono text-cyan-300">{incident.alert.source}</span>
            </p>
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
              {incident.alert.symptoms.map((symptom) => (
                <li key={symptom} className="break-words">
                  {symptom}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <EventList incidentId={incident.id} />

      {confirming ? (
        <ConfirmDeleteDialog
          title={incident.title}
          pending={remove.isPending}
          error={remove.isError ? describeApiError(remove.error, '刪除失敗，請稍後再試。') : null}
          onConfirm={() => {
            remove.mutate()
          }}
          onCancel={() => {
            setConfirming(false)
          }}
        />
      ) : null}
    </div>
  )
}

export function IncidentDetailPage() {
  const { id = '' } = useParams()
  const query = useQuery({
    queryKey: incidentKeys.detail(id),
    queryFn: ({ signal }) => fetchIncident(id, signal),
  })

  if (query.isError) {
    // 後端對不存在與無權限一律回 404；畸形 id（422）也以同樣文案呈現。
    const notFound =
      query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 422)
    return (
      <div className="space-y-4">
        <div role="alert" className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-6">
          <p className="font-medium text-white">
            {notFound ? '找不到此事故或沒有權限' : describeApiError(query.error, '無法載入此事故。')}
          </p>
          {notFound ? null : (
            <button
              type="button"
              onClick={() => {
                void query.refetch()
              }}
              className="rounded border border-slate-500 px-3 py-1 text-xs font-medium text-slate-100 hover:bg-slate-800"
            >
              重試
            </button>
          )}
        </div>
        <Link to="/incidents" className="text-sm text-cyan-300 hover:text-cyan-200 hover:underline">
          ← 返回事故列表
        </Link>
      </div>
    )
  }
  if (query.data === undefined) {
    return (
      <p role="status" className="text-sm text-slate-300">
        正在載入事故…
      </p>
    )
  }
  return <IncidentView incident={query.data} />
}
