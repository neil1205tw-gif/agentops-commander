import { apiFetch } from '../../lib/api'
import type {
  IncidentDetail,
  IncidentEvent,
  IncidentList,
  IncidentStatus,
  Scenario,
} from './types'

export const PAGE_SIZE = 20

export const incidentKeys = {
  all: ['incidents'] as const,
  list: (status: IncidentStatus | null, offset: number) =>
    ['incidents', { status, offset }] as const,
  detail: (id: string) => ['incident', id] as const,
  events: (id: string) => ['incident', id, 'events'] as const,
  scenarios: ['scenarios'] as const,
}

export function fetchIncidents(
  status: IncidentStatus | null,
  offset: number,
  signal?: AbortSignal,
): Promise<IncidentList> {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
  if (status !== null) {
    params.set('status', status)
  }
  return apiFetch<IncidentList>(`/api/v1/incidents?${params.toString()}`, { signal })
}

export function fetchIncident(id: string, signal?: AbortSignal): Promise<IncidentDetail> {
  return apiFetch<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}`, { signal })
}

export async function fetchIncidentEvents(
  id: string,
  signal?: AbortSignal,
): Promise<IncidentEvent[]> {
  const result = await apiFetch<{ items: IncidentEvent[] }>(
    `/api/v1/incidents/${encodeURIComponent(id)}/events`,
    { signal },
  )
  return result.items
}

export function fetchScenarios(signal?: AbortSignal): Promise<Scenario[]> {
  return apiFetch<Scenario[]>('/api/v1/scenarios', { signal })
}

export function createIncident(scenarioKey: string, title: string): Promise<IncidentDetail> {
  return apiFetch<IncidentDetail>('/api/v1/incidents', {
    method: 'POST',
    body: { scenario_key: scenarioKey, title },
  })
}

export function deleteIncident(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/incidents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function setIncidentVisibility(id: string, isPublic: boolean): Promise<IncidentDetail> {
  return apiFetch<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}/visibility`, {
    method: 'PATCH',
    body: { is_public: isPublic },
  })
}
