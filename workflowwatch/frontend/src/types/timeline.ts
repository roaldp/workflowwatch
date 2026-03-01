export interface TimelineEvent {
  aw_bucket_id: string
  aw_event_id: number
  timestamp: string
  duration: number
  data: { app?: string; title?: string; url?: string; [k: string]: unknown }
  session_id: string | null
  workflow_name: string | null
  workflow_color: string | null
  // WP-7: auto-label suggestion fields (present when fetched with auto_label=true)
  suggested_workflow_id: string | null
  suggested_workflow_name: string | null
  suggested_workflow_color: string | null
  suggestion_confidence: 'high' | 'medium' | null
  suggestion_source: 'cache' | 'embedding' | null
  suggestion_explanation: string | null
}

export function todayISO(): string {
  const d = new Date()
  return d.toISOString().slice(0, 10)
}

export function addDays(iso: string, delta: number): string {
  const d = new Date(iso + 'T12:00:00')
  d.setDate(d.getDate() + delta)
  return d.toISOString().slice(0, 10)
}

export function formatTime(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const min = m % 60
  return min > 0 ? `${h}h ${min}m` : `${h}h`
}

const APP_PALETTE = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#06B6D4', '#84CC16',
]

export function appColor(app: string | undefined): string {
  if (!app) return '#94a3b8'
  let h = 0
  for (let i = 0; i < app.length; i++) h = (h << 5) - h + app.charCodeAt(i)
  return APP_PALETTE[Math.abs(h) % APP_PALETTE.length] ?? '#94a3b8'
}
