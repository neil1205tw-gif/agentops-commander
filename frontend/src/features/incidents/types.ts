export const INCIDENT_STATUSES = [
  'open',
  'investigating',
  'awaiting_approval',
  'executing',
  'verifying',
  'resolved',
  'mitigated',
  'escalated',
  'failed',
] as const

export type IncidentStatus = (typeof INCIDENT_STATUSES)[number]
export type IncidentSeverity = 'P1' | 'P2' | 'P3' | 'P4'

export interface IncidentSummary {
  id: string
  title: string
  scenario_key: string
  severity: IncidentSeverity | null
  status: IncidentStatus
  affected_services: string[]
  is_public: boolean
  owner_id: string
  created_at: string
  updated_at: string
}

export interface ScenarioAlert {
  summary: string
  source: string
  fired_at_offset_minutes: number
  symptoms: string[]
}

export interface IncidentDetail extends IncidentSummary {
  resolved_at: string | null
  alert: ScenarioAlert | null
}

export interface IncidentList {
  items: IncidentSummary[]
  total: number
  limit: number
  offset: number
}

export interface IncidentEvent {
  id: string
  event_type: string
  agent_name: string | null
  summary: string
  payload: Record<string, unknown>
  created_at: string
}

export interface Scenario {
  key: string
  name: string
  description: string
  default_title: string
  affected_services: string[]
  alert: ScenarioAlert
}

export const TITLE_MAX_LENGTH = 200
