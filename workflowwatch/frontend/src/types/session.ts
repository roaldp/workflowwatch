export interface SessionEventRef {
  aw_bucket_id: string
  aw_event_id: number
}

export interface SessionCreate {
  workflow_id: string
  date: string
  title?: string | null
  notes?: string | null
  events: SessionEventRef[]
}

export interface Session {
  id: string
  workflow_id: string
  title: string | null
  started_at: string
  ended_at: string
  duration: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface SessionEventSnapshot {
  aw_bucket_id: string
  aw_event_id: number
  event_timestamp: string
  event_duration: number
  event_data: { app?: string; title?: string; url?: string; [k: string]: unknown } | null
}

export interface SessionWithEvents extends Session {
  events: SessionEventSnapshot[]
}

export function eventKey(aw_bucket_id: string, aw_event_id: number): string {
  return `${aw_bucket_id}:${aw_event_id}`
}

export interface SuggestionEventRef {
  aw_bucket_id: string
  aw_event_id: number
}

export interface Suggestion {
  type: string
  workflow_id: string
  event_refs: SuggestionEventRef[]
  score: number
  matched_indicators?: string[]
}
