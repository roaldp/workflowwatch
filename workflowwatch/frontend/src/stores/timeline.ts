import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/client'
import type { TimelineEvent } from '../types/timeline'
import { todayISO, addDays } from '../types/timeline'
import { eventKey } from '../types/session'
import type { Suggestion } from '../types/session'

export const useTimelineStore = defineStore('timeline', () => {
  const date = ref(todayISO())
  const events = ref<TimelineEvent[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedIds = ref<Set<string>>(new Set())
  const suggestions = ref<Suggestion[]>([])
  const suggestionsLoading = ref(false)

  const sortedEvents = computed(() => {
    return [...events.value].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
  })

  function eventKeyFor(e: TimelineEvent) {
    return eventKey(e.aw_bucket_id, e.aw_event_id)
  }

  function isSelected(e: TimelineEvent) {
    return selectedIds.value.has(eventKeyFor(e))
  }

  function toggleEvent(e: TimelineEvent) {
    if (e.session_id) return
    const key = eventKeyFor(e)
    const next = new Set(selectedIds.value)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    selectedIds.value = next
  }

  function clearSelection() {
    selectedIds.value = new Set()
  }

  function selectAllUnlabeled() {
    const unlabeled = events.value.filter((e) => !e.session_id)
    selectedIds.value = new Set(unlabeled.map(eventKeyFor))
  }

  const hasSelection = computed(() => selectedIds.value.size > 0)
  const selectedCount = computed(() => selectedIds.value.size)

  async function fetchTimeline() {
    loading.value = true
    error.value = null
    try {
      events.value = await api.get<TimelineEvent[]>(
        `/api/v1/timeline?date=${date.value}`
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load timeline'
      events.value = []
    } finally {
      loading.value = false
      if (!error.value) fetchSuggestions()
    }
  }

  async function fetchSuggestions() {
    suggestionsLoading.value = true
    try {
      const res = await api.get<{ date: string; suggestions: Suggestion[] }>(
        `/api/v1/suggestions?date=${date.value}`
      )
      suggestions.value = res.suggestions ?? []
    } catch {
      suggestions.value = []
    } finally {
      suggestionsLoading.value = false
    }
  }

  function setDate(iso: string) {
    date.value = iso
    fetchTimeline()
  }

  function goToday() {
    setDate(todayISO())
  }

  function goPrev() {
    setDate(addDays(date.value, -1))
  }

  function goNext() {
    setDate(addDays(date.value, 1))
  }

  return {
    date,
    events: sortedEvents,
    loading,
    error,
    selectedIds,
    hasSelection,
    selectedCount,
    suggestions,
    suggestionsLoading,
    isSelected,
    toggleEvent,
    clearSelection,
    selectAllUnlabeled,
    fetchTimeline,
    fetchSuggestions,
    setDate,
    goToday,
    goPrev,
    goNext,
  }
})
