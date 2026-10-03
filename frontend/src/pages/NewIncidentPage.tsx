import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { SyntheticEvent } from 'react'
import { useNavigate } from 'react-router'

import { canCreateIncident, useAuth } from '../features/auth'
import { useBackendStatus } from '../features/backend-status'
import { TITLE_MAX_LENGTH, createIncident, fetchScenarios, incidentKeys } from '../features/incidents'
import { describeApiError } from '../lib/errors'

function validateTitle(title: string): string | null {
  const length = [...title.trim()].length
  if (length < 1) {
    return '標題不可為空'
  }
  if (length > TITLE_MAX_LENGTH) {
    return `標題最多 ${String(TITLE_MAX_LENGTH)} 字`
  }
  return null
}

export function NewIncidentPage() {
  const { user } = useAuth()
  const { isReady } = useBackendStatus()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const allowed = user !== null && canCreateIncident(user.role)

  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  // null 表示使用者尚未手動編輯，標題跟著所選情境的預設值。
  const [editedTitle, setEditedTitle] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  const scenarios = useQuery({
    queryKey: incidentKeys.scenarios,
    queryFn: ({ signal }) => fetchScenarios(signal),
    enabled: allowed,
  })

  const create = useMutation({
    mutationFn: ({ scenarioKey, title }: { scenarioKey: string; title: string }) =>
      createIncident(scenarioKey, title),
    onSuccess: (incident) => {
      void queryClient.invalidateQueries({ queryKey: incidentKeys.all })
      void navigate(`/incidents/${incident.id}`)
    },
  })

  if (!allowed) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold text-white sm:text-3xl">New Incident</h1>
        <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-5">
          <p className="font-medium text-amber-100">需要 Operator 權限</p>
          <p className="mt-1 text-sm text-amber-200/80">
            目前的角色無法建立事故，請以 Operator 或 Admin 身分登入。
          </p>
        </div>
      </div>
    )
  }

  const selected = scenarios.data?.find((scenario) => scenario.key === selectedKey) ?? null
  const title = editedTitle ?? selected?.default_title ?? ''

  const handleSubmit = (event: SyntheticEvent) => {
    event.preventDefault()
    if (create.isPending || !isReady) {
      return
    }
    if (selected === null) {
      setValidationError('請先選擇一個情境')
      return
    }
    const error = validateTitle(title)
    if (error !== null) {
      setValidationError(error)
      return
    }
    setValidationError(null)
    create.mutate({ scenarioKey: selected.key, title: title.trim() })
  }

  const renderScenarios = () => {
    if (scenarios.isError) {
      return (
        <div role="alert" className="space-y-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-5">
          <p className="text-sm text-rose-200">無法載入情境，請重試。</p>
          <button
            type="button"
            onClick={() => {
              void scenarios.refetch()
            }}
            className="rounded border border-rose-400/50 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/20"
          >
            重試
          </button>
        </div>
      )
    }
    if (scenarios.data === undefined) {
      return (
        <p role="status" className="text-sm text-slate-300">
          正在載入情境…
        </p>
      )
    }
    return (
      <fieldset className="space-y-3">
        <legend className="mb-3 text-sm font-medium text-slate-200">選擇情境</legend>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {scenarios.data.map((scenario) => {
            const checked = scenario.key === selectedKey
            return (
              <label
                key={scenario.key}
                className={`block cursor-pointer rounded-lg border p-5 transition-colors ${
                  checked
                    ? 'border-cyan-400 bg-cyan-500/10'
                    : 'border-slate-800 bg-slate-900/60 hover:border-cyan-500/50'
                }`}
              >
                <span className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="scenario"
                    value={scenario.key}
                    checked={checked}
                    onChange={() => {
                      setSelectedKey(scenario.key)
                      setValidationError(null)
                    }}
                    className="mt-1 accent-cyan-400"
                  />
                  <span className="min-w-0 space-y-1">
                    <span className="block text-base font-semibold text-white">{scenario.name}</span>
                    <span className="block break-all font-mono text-xs text-cyan-300">
                      {scenario.affected_services.join(', ')}
                    </span>
                    <span className="block text-sm leading-relaxed text-slate-300">
                      {scenario.description}
                    </span>
                  </span>
                </span>
              </label>
            )
          })}
        </div>
      </fieldset>
    )
  }

  const submitDisabled = create.isPending || !isReady
  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <h1 className="text-2xl font-bold text-white sm:text-3xl">New Incident</h1>
      {renderScenarios()}

      <div className="space-y-2">
        <label htmlFor="incident-title" className="block text-sm font-medium text-slate-200">
          標題
        </label>
        <input
          id="incident-title"
          type="text"
          value={title}
          placeholder={selected?.default_title ?? ''}
          disabled={create.isPending}
          onChange={(event) => {
            setEditedTitle(event.target.value)
            setValidationError(null)
          }}
          aria-invalid={validationError !== null}
          className="w-full rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
        />
        <p className="text-xs text-slate-400">1–{TITLE_MAX_LENGTH} 字；選擇情境後會帶入預設標題，可自行修改。</p>
      </div>

      {validationError !== null ? (
        <p role="alert" className="text-sm text-rose-300">
          {validationError}
        </p>
      ) : null}
      {create.isError ? (
        <p role="alert" className="text-sm text-rose-300">
          {describeApiError(create.error, '建立事故失敗，請稍後再試。')}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={submitDisabled}
          className="rounded border border-cyan-500/60 bg-cyan-500/10 px-5 py-2 text-sm font-medium text-cyan-100 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-cyan-500/10"
        >
          {create.isPending ? '建立中…' : '建立事故'}
        </button>
        {!isReady ? <p className="text-xs text-slate-400">Agent 執行環境尚未就緒，就緒後即可送出。</p> : null}
      </div>
    </form>
  )
}
