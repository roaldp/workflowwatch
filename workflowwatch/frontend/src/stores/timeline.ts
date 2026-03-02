import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/client'
import type { TimelineEvent } from '../types/timeline'
import { todayISO, addDays } from '../types/timeline'
import { eventKey } from '../types/session'
import type { Suggestion } from '../types/session'

interface SuggestionPreview {
  workflow_id: string
  workflow_name: string
  score: number
  matched_indicators: string[]
  event_keys: Set<string>
}

function suggestionEventKeySet(suggestion: Suggestion): Set<string> {
  return new Set(
    suggestion.event_refs.map((r) => eventKey(r.aw_bucket_id, r.aw_event_id))
  )
}

function overlapSize(a: Set<string>, b: Set<string>): number {
  let count = 0
  for (const key of a) {
    if (b.has(key)) count += 1
  }
  return count
}

export const useTimelineStore = defineStore('timeline', () => {
  const date = ref(todayISO())
  const events = ref<TimelineEvent[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedIds = ref<Set<string>>(new Set())
  const suggestions = ref<Suggestion[]>([])
  const suggestionsLoading = ref(false)
  const suggestionPreview = ref<SuggestionPreview | null>(null)
  const recentlyAppliedPatternKeys = ref<Set<string>>(new Set())
  const focusEventKey = ref<string | null>(null)
  const recentPatternContributionEventCounts = ref<Map<string, number>>(new Map())
  const recentPatternContributionWorkflowCounts = ref<Map<string, number>>(new Map())

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
      if (suggestionPreview.value) {
        const eventKeys = new Set(events.value.map((e) => eventKeyFor(e)))
        const validPreviewKeys = new Set(
          [...suggestionPreview.value.event_keys].filter((k) => eventKeys.has(k))
        )
        if (validPreviewKeys.size === 0) {
          suggestionPreview.value = null
        } else {
          suggestionPreview.value = {
            ...suggestionPreview.value,
            event_keys: validPreviewKeys,
          }
        }
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load timeline'
      events.value = []
      suggestionPreview.value = null
    } finally {
      loading.value = false
      if (!error.value) fetchSuggestions()
    }
  }

  // Silent background refetch — no loading spinner, no error clearing
  async function silentRefetch() {
    try {
      events.value = await api.get<TimelineEvent[]>(
        `/api/v1/timeline?date=${date.value}`
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

  function optimisticallyUnlabelEvent(event: TimelineEvent) {
    events.value = events.value.map((e) =>
      e.aw_bucket_id === event.aw_bucket_id && e.aw_event_id === event.aw_event_id
        ? {
            ...e,
            session_id: null,
            workflow_name: null,
            workflow_color: null,
          }
        : e
    )
  }

  async function fetchSuggestions() {
    suggestionsLoading.value = true
    try {
      const res = await api.get<{ date: string; suggestions: Suggestion[] }>(
        `/api/v1/suggestions?date=${date.value}`
      )
      suggestions.value = res.suggestions ?? []
      if (suggestionPreview.value) {
        const current = suggestionPreview.value
        let bestMatch: Suggestion | null = null
        let bestOverlap = 0
        for (const s of suggestions.value) {
          if (s.workflow_id !== current.workflow_id) continue
          const keys = suggestionEventKeySet(s)
          const overlap = overlapSize(current.event_keys, keys)
          if (overlap > bestOverlap) {
            bestMatch = s
            bestOverlap = overlap
          }
        }
        if (bestMatch && bestOverlap > 0) {
          suggestionPreview.value = {
            ...current,
            score: bestMatch.score,
            matched_indicators: bestMatch.matched_indicators ?? [],
            event_keys: suggestionEventKeySet(bestMatch),
          }
        }
      }
    } catch {
      suggestions.value = []
    } finally {
      suggestionsLoading.value = false
    }
  }

  function previewSuggestion(suggestion: Suggestion, workflowName: string) {
    suggestionPreview.value = {
      workflow_id: suggestion.workflow_id,
      workflow_name: workflowName,
      score: suggestion.score,
      matched_indicators: suggestion.matched_indicators ?? [],
      event_keys: new Set(
        suggestion.event_refs.map((r) => eventKey(r.aw_bucket_id, r.aw_event_id))
      ),
    }
  }

  function clearSuggestionPreview() {
    suggestionPreview.value = null
  }

  function removeEventFromSuggestionPreview(event: TimelineEvent) {
    if (!suggestionPreview.value) return
    const key = eventKeyFor(event)
    if (!suggestionPreview.value.event_keys.has(key)) return
    const next = new Set(suggestionPreview.value.event_keys)
    next.delete(key)
    if (next.size === 0) {
      suggestionPreview.value = null
      return
    }
    suggestionPreview.value = {
      ...suggestionPreview.value,
      event_keys: next,
    }
  }

  function markPatternApplied(eventRefs: Array<{ aw_bucket_id: string; aw_event_id: number }>) {
    const keys = new Set(eventRefs.map((r) => eventKey(r.aw_bucket_id, r.aw_event_id)))
    recentlyAppliedPatternKeys.value = keys
    focusEventKey.value = eventRefs.length > 0
      ? eventKey(eventRefs[0]!.aw_bucket_id, eventRefs[0]!.aw_event_id)
      : null
    window.setTimeout(() => {
      recentlyAppliedPatternKeys.value = new Set()
    }, 2400)
  }

  function markPatternContribution(
    workflowId: string,
    eventRef: { aw_bucket_id: string; aw_event_id: number },
  ) {
    const key = eventKey(eventRef.aw_bucket_id, eventRef.aw_event_id)
    const eventCounts = new Map(recentPatternContributionEventCounts.value)
    eventCounts.set(key, (eventCounts.get(key) ?? 0) + 1)
    recentPatternContributionEventCounts.value = eventCounts

    const workflowCounts = new Map(recentPatternContributionWorkflowCounts.value)
    workflowCounts.set(workflowId, (workflowCounts.get(workflowId) ?? 0) + 1)
    recentPatternContributionWorkflowCounts.value = workflowCounts

    window.setTimeout(() => {
      const nextEventCounts = new Map(recentPatternContributionEventCounts.value)
      const eventCount = nextEventCounts.get(key) ?? 0
      if (eventCount <= 1) nextEventCounts.delete(key)
      else nextEventCounts.set(key, eventCount - 1)
      recentPatternContributionEventCounts.value = nextEventCounts

      const nextWorkflowCounts = new Map(recentPatternContributionWorkflowCounts.value)
      const workflowCount = nextWorkflowCounts.get(workflowId) ?? 0
      if (workflowCount <= 1) nextWorkflowCounts.delete(workflowId)
      else nextWorkflowCounts.set(workflowId, workflowCount - 1)
      recentPatternContributionWorkflowCounts.value = nextWorkflowCounts
    }, 2400)
  }

  function isRecentlyPatternApplied(event: TimelineEvent) {
    return recentlyAppliedPatternKeys.value.has(eventKeyFor(event))
  }

  function isRecentlyPatternContributionEvent(event: TimelineEvent) {
    return recentPatternContributionEventCounts.value.has(eventKeyFor(event))
  }

  function hasRecentPatternContribution(workflowId: string) {
    return recentPatternContributionWorkflowCounts.value.has(workflowId)
  }

  function consumeFocusEventKey() {
    focusEventKey.value = null
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
    suggestionPreview,
    focusEventKey,
    isSelected,
    toggleEvent,
    clearSelection,
    selectAllUnlabeled,
    fetchTimeline,
    silentRefetch,
    optimisticallyLabelEvent,
    optimisticallyUnlabelEvent,
    fetchSuggestions,
    previewSuggestion,
    clearSuggestionPreview,
    removeEventFromSuggestionPreview,
    markPatternApplied,
    markPatternContribution,
    isRecentlyPatternApplied,
    isRecentlyPatternContributionEvent,
    hasRecentPatternContribution,
    consumeFocusEventKey,
    setDate,
    goToday,
    goPrev,
    goNext,
  }
})
