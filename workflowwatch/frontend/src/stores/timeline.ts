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

  // WP-7: track ongoing accept/dismiss operations
  const acceptingAutoLabels = ref(false)

  const sortedEvents = computed(() => {
    return [...events.value].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
  })

  // WP-7: events that have auto-label suggestions
  const autoLabeledEvents = computed(() =>
    sortedEvents.value.filter((e) => !e.session_id && e.suggested_workflow_id)
  )

  const highConfidenceAutoLabels = computed(() =>
    autoLabeledEvents.value.filter((e) => e.suggestion_confidence === 'high')
  )

  const autoLabelCount = computed(() => autoLabeledEvents.value.length)
  const highConfidenceCount = computed(() => highConfidenceAutoLabels.value.length)

  // Group auto-labeled events by suggested workflow for the banner
  const autoLabelsByWorkflow = computed(() => {
    const groups = new Map<string, {
      id: string; name: string; color: string | null
      events: TimelineEvent[]; highCount: number
    }>()
    for (const e of autoLabeledEvents.value) {
      const id = e.suggested_workflow_id!
      if (!groups.has(id)) {
        groups.set(id, {
          id,
          name: e.suggested_workflow_name ?? id,
          color: e.suggested_workflow_color ?? null,
          events: [],
          highCount: 0,
        })
      }
      const g = groups.get(id)!
      g.events.push(e)
      if (e.suggestion_confidence === 'high') g.highCount++
    }
    return [...groups.values()]
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
      // WP-7: always fetch with auto_label=true to get suggestions inline
      events.value = await api.get<TimelineEvent[]>(
        `/api/v1/timeline?date=${date.value}&auto_label=true`
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load timeline'
      events.value = []
    } finally {
      loading.value = false
      if (!error.value) fetchSuggestions()
    }
  }

  // Silent background refetch — no loading spinner, no error clearing
  async function silentRefetch() {
    try {
      events.value = await api.get<TimelineEvent[]>(
        `/api/v1/timeline?date=${date.value}&auto_label=true`
      )
      fetchSuggestions()
    } catch {
      // Keep optimistic state; full fetchTimeline() is called on API errors
    }
  }

  // Immediately mark a single event as labeled in local state (before server confirms)
  function optimisticallyLabelEvent(
    event: TimelineEvent,
    _workflowId: string,
    workflowName: string,
    workflowColor: string | null,
  ) {
    events.value = events.value.map((e) =>
      e.aw_bucket_id === event.aw_bucket_id && e.aw_event_id === event.aw_event_id
        ? {
            ...e,
            session_id: '__optimistic__',
            workflow_name: workflowName,
            workflow_color: workflowColor,
            suggested_workflow_id: null,
            suggested_workflow_name: null,
            suggested_workflow_color: null,
            suggestion_confidence: null,
            suggestion_source: null,
            suggestion_explanation: null,
          }
        : e
    )
    // Remove from selection if it was selected
    const key = eventKeyFor(event)
    if (selectedIds.value.has(key)) {
      const next = new Set(selectedIds.value)
      next.delete(key)
      selectedIds.value = next
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

  // WP-7: Accept a single auto-label suggestion (optimistic — instant UI update)
  async function acceptAutoLabel(event: TimelineEvent) {
    if (!event.suggested_workflow_id) return
    // Instant local update
    optimisticallyLabelEvent(
      event,
      event.suggested_workflow_id,
      event.suggested_workflow_name ?? '',
      event.suggested_workflow_color ?? null,
    )
    try {
      await api.post('/api/v1/auto-label/accept', {
        date: date.value,
        accepts: [
          {
            aw_bucket_id: event.aw_bucket_id,
            aw_event_id: event.aw_event_id,
            workflow_id: event.suggested_workflow_id,
          },
        ],
      })
      silentRefetch() // background sync, no loading flash
    } catch {
      fetchTimeline() // restore on error
    }
  }

  // WP-7: Accept all suggestions for a specific workflow (optimistic)
  async function acceptAllForWorkflow(workflowId: string) {
    const toAccept = autoLabeledEvents.value.filter(
      (e) => e.suggested_workflow_id === workflowId
    )
    if (!toAccept.length) return
    // Snapshot workflow info before optimistic updates clear the suggestions
    const wfName = toAccept[0]?.suggested_workflow_name ?? ''
    const wfColor = toAccept[0]?.suggested_workflow_color ?? null
    for (const event of toAccept) {
      optimisticallyLabelEvent(event, workflowId, wfName, wfColor)
    }
    try {
      await api.post('/api/v1/auto-label/accept', {
        date: date.value,
        accepts: toAccept.map((e) => ({
          aw_bucket_id: e.aw_bucket_id,
          aw_event_id: e.aw_event_id,
          workflow_id: workflowId,
        })),
      })
      silentRefetch()
    } catch {
      fetchTimeline()
    }
  }

  // WP-7: Dismiss all suggestions for a specific workflow
  async function dismissAllForWorkflow(workflowId: string) {
    const toDismiss = autoLabeledEvents.value.filter(
      (e) => e.suggested_workflow_id === workflowId
    )
    if (!toDismiss.length) return
    try {
      await api.post('/api/v1/auto-label/dismiss', {
        date: date.value,
        dismissals: toDismiss.map((e) => ({
          aw_bucket_id: e.aw_bucket_id,
          aw_event_id: e.aw_event_id,
          workflow_id: workflowId,
        })),
      })
      // Optimistically clear from local state
      events.value = events.value.map((e) =>
        e.suggested_workflow_id === workflowId
          ? {
              ...e,
              suggested_workflow_id: null,
              suggested_workflow_name: null,
              suggested_workflow_color: null,
              suggestion_confidence: null,
              suggestion_source: null,
              suggestion_explanation: null,
            }
          : e
      )
    } catch {
      // Non-critical
    }
  }

  // WP-7: Accept all high-confidence auto-labels in bulk (optimistic)
  async function acceptAllHighConfidence() {
    const toAccept = highConfidenceAutoLabels.value
    if (!toAccept.length) return
    for (const event of toAccept) {
      optimisticallyLabelEvent(
        event,
        event.suggested_workflow_id!,
        event.suggested_workflow_name ?? '',
        event.suggested_workflow_color ?? null,
      )
    }
    try {
      await api.post('/api/v1/auto-label/accept', {
        date: date.value,
        accepts: toAccept.map((e) => ({
          aw_bucket_id: e.aw_bucket_id,
          aw_event_id: e.aw_event_id,
          workflow_id: e.suggested_workflow_id!,
        })),
      })
      silentRefetch()
    } catch {
      fetchTimeline()
    }
  }

  // WP-7: Dismiss an auto-label suggestion (negative signal)
  async function dismissAutoLabel(event: TimelineEvent) {
    if (!event.suggested_workflow_id) return
    try {
      await api.post('/api/v1/auto-label/dismiss', {
        date: date.value,
        dismissals: [
          {
            aw_bucket_id: event.aw_bucket_id,
            aw_event_id: event.aw_event_id,
            workflow_id: event.suggested_workflow_id,
          },
        ],
      })
      // Optimistically clear the suggestion from local state
      events.value = events.value.map((e) =>
        e.aw_bucket_id === event.aw_bucket_id && e.aw_event_id === event.aw_event_id
          ? {
              ...e,
              suggested_workflow_id: null,
              suggested_workflow_name: null,
              suggested_workflow_color: null,
              suggestion_confidence: null,
              suggestion_source: null,
              suggestion_explanation: null,
            }
          : e
      )
    } catch {
      // Ignore dismiss errors — non-critical
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
    autoLabeledEvents,
    highConfidenceAutoLabels,
    autoLabelsByWorkflow,
    autoLabelCount,
    highConfidenceCount,
    acceptingAutoLabels,
    isSelected,
    toggleEvent,
    clearSelection,
    selectAllUnlabeled,
    fetchTimeline,
    silentRefetch,
    optimisticallyLabelEvent,
    fetchSuggestions,
    acceptAutoLabel,
    acceptAllForWorkflow,
    dismissAllForWorkflow,
    acceptAllHighConfidence,
    dismissAutoLabel,
    setDate,
    goToday,
    goPrev,
    goNext,
  }
})
