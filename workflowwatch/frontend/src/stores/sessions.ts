import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/client'
import type { Session, SessionWithEvents } from '../types/session'
import { addDays, todayISO } from '../types/timeline'

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<Session[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const start = ref(addDays(todayISO(), -7))
  const end = ref(todayISO())
  const workflowId = ref<string | null>(null)

  async function fetchSessions() {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      params.set('start', start.value)
      params.set('end', end.value)
      if (workflowId.value) params.set('workflow_id', workflowId.value)
      sessions.value = await api.get<Session[]>(
        `/api/v1/sessions?${params.toString()}`
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load sessions'
      sessions.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchSession(id: string): Promise<SessionWithEvents | null> {
    try {
      return await api.get<SessionWithEvents>(`/api/v1/sessions/${id}`)
    } catch {
      return null
    }
  }

  async function updateSession(
    id: string,
    payload: { title?: string | null; notes?: string | null }
  ) {
    error.value = null
    const s = await api.put<Session>(`/api/v1/sessions/${id}`, payload)
    const i = sessions.value.findIndex((x) => x.id === id)
    if (i >= 0) sessions.value[i] = s
    return s
  }

  async function deleteSession(id: string) {
    error.value = null
    await api.delete(`/api/v1/sessions/${id}`)
    sessions.value = sessions.value.filter((x) => x.id !== id)
  }

  async function removeEventsFromSession(
    sessionId: string,
    eventRefs: { aw_bucket_id: string; aw_event_id: number }[]
  ): Promise<Session | null> {
    const res = await api.deleteWithBody<Session | void>(
      `/api/v1/sessions/${sessionId}/events`,
      { events: eventRefs }
    )
    if (res === undefined) {
      sessions.value = sessions.value.filter((x) => x.id !== sessionId)
      return null
    }
    const i = sessions.value.findIndex((x) => x.id === sessionId)
    if (i >= 0) sessions.value[i] = res
    return res
  }

  const sessionsByDay = computed(() => {
    const byDay = new Map<string, Session[]>()
    for (const s of sessions.value) {
      const day = s.started_at.slice(0, 10)
      if (!byDay.has(day)) byDay.set(day, [])
      byDay.get(day)!.push(s)
    }
    const days = [...byDay.keys()].sort().reverse()
    return days.map((day) => ({ day, sessions: byDay.get(day)! }))
  })

  return {
    sessions,
    loading,
    error,
    start,
    end,
    workflowId,
    sessionsByDay,
    fetchSessions,
    fetchSession,
    updateSession,
    deleteSession,
    removeEventsFromSession,
  }
})
