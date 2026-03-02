<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import type { TimelineEvent } from '../types/timeline'
import { formatTime, formatDuration } from '../types/timeline'
import { useTimelineStore } from '../stores/timeline'
import { useSessionsStore } from '../stores/sessions'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'

const props = defineProps<{
  events: TimelineEvent[]
  patternView?: boolean
}>()

const timeline = useTimelineStore()
const sessionsStore = useSessionsStore()
const workflowsStore = useWorkflowsStore()
const { suggestions, focusEventKey, suggestionPreview } = storeToRefs(timeline)
const unlabelingId = ref<string | null>(null)
const removingPatternId = ref<string | null>(null)
const editingLabelId = ref<string | null>(null)
const relabelingId = ref<string | null>(null)
const rowRefs = new Map<string, HTMLTableRowElement>()

const unlabeledEvents = computed(() => props.events.filter((e) => !e.session_id))
const allUnlabeledSelected = computed(
  () =>
    unlabeledEvents.value.length > 0 &&
    unlabeledEvents.value.every((e) => timeline.isSelected(e))
)
const someUnlabeledSelected = computed(
  () => timeline.selectedCount > 0 && !allUnlabeledSelected.value
)

function toggleSelectAll() {
  if (allUnlabeledSelected.value) {
    timeline.clearSelection()
  } else {
    for (const e of unlabeledEvents.value) {
      if (!timeline.isSelected(e)) timeline.toggleEvent(e)
    }
  }
}

function eventKey(e: TimelineEvent) {
  return `${e.aw_bucket_id}:${e.aw_event_id}`
}

function eventRefKey(ref: { aw_bucket_id: string; aw_event_id: number }) {
  return `${ref.aw_bucket_id}:${ref.aw_event_id}`
}

type PatternConfidence = 'low' | 'medium' | 'high'

function confidenceFromScore(score: number): PatternConfidence {
  if (score >= 6) return 'high'
  if (score >= 4) return 'medium'
  return 'low'
}

const patternHintByEvent = computed(() => {
  const map = new Map<string, {
    workflowId: string
    score: number
    confidence: PatternConfidence
    indicators: string[]
  }>()
  for (const s of suggestions.value) {
    if (s.score < 6) continue
    const confidence = confidenceFromScore(s.score)
    for (const ref of s.event_refs) {
      const key = `${ref.aw_bucket_id}:${ref.aw_event_id}`
      const current = map.get(key)
      if (!current || s.score > current.score) {
        map.set(key, {
          workflowId: s.workflow_id,
          score: s.score,
          confidence,
          indicators: s.matched_indicators ?? [],
        })
      }
    }
  }
  return map
})

// Suggestions for a row: pattern-suggested workflow first, then manual alternatives (max 3 total)
function suggestionsFor(event: TimelineEvent) {
  if (event.session_id) return []
  const chips: Array<{
    id: string
    name: string
    color: string | null
    isPrimary: boolean
    score?: number
    confidence?: PatternConfidence
    indicators?: string[]
  }> = []
  const hint = patternHintByEvent.value.get(eventKey(event))
  if (hint) {
    const wf = workflowsStore.workflows.find((w) => w.id === hint.workflowId)
    chips.push({
      id: hint.workflowId,
      name: wf?.name ?? hint.workflowId,
      color: wf?.color ?? null,
      isPrimary: true,
      score: hint.score,
      confidence: hint.confidence,
      indicators: hint.indicators,
    })
  }

  for (const wf of workflowsStore.workflows) {
    if (chips.length >= 3) break
    if (chips.some((c) => c.id === wf.id)) continue
    chips.push({ id: wf.id, name: wf.name, color: wf.color ?? null, isPrimary: false })
  }

  return chips
}

async function unlabel(e: TimelineEvent) {
  if (!e.session_id) return
  if (e.session_id === '__optimistic__') return
  const key = `${e.aw_bucket_id}:${e.aw_event_id}`
  unlabelingId.value = key
  try {
    timeline.optimisticallyUnlabelEvent(e)
    await sessionsStore.removeEventsFromSession(e.session_id, [
      { aw_bucket_id: e.aw_bucket_id, aw_event_id: e.aw_event_id },
    ])
    timeline.silentRefetch()
    if (editingLabelId.value === key) editingLabelId.value = null
  } catch {
    timeline.silentRefetch()
  } finally {
    unlabelingId.value = null
  }
}

function contributesToPatternProgress(event: TimelineEvent, workflowId: string): boolean {
  const key = eventKey(event)
  return suggestions.value.some(
    (s) =>
      s.workflow_id === workflowId &&
      s.event_refs.some((ref) => eventRefKey(ref) === key)
  )
}

async function quickLabel(event: TimelineEvent, workflowId: string) {
  const wf = workflowsStore.workflows.find((w) => w.id === workflowId)
  const contributes = contributesToPatternProgress(event, workflowId)
  // Instant optimistic update — row appears labeled immediately
  timeline.optimisticallyLabelEvent(event, workflowId, wf?.name ?? '', wf?.color ?? null)
  try {
    await api.post('/api/v1/sessions', {
      workflow_id: workflowId,
      date: timeline.date,
      events: [{ aw_bucket_id: event.aw_bucket_id, aw_event_id: event.aw_event_id }],
    })
    if (contributes) {
      timeline.markPatternContribution(workflowId, {
        aw_bucket_id: event.aw_bucket_id,
        aw_event_id: event.aw_event_id,
      })
    }
    timeline.silentRefetch() // background sync, no loading flash
  } catch {
    timeline.silentRefetch()
  }
}

function startEditLabel(event: TimelineEvent) {
  editingLabelId.value = eventKey(event)
}

function cancelEditLabel() {
  editingLabelId.value = null
}

function isEditingLabel(event: TimelineEvent) {
  return editingLabelId.value === eventKey(event)
}

async function relabelEvent(event: TimelineEvent, workflowId: string) {
  if (!event.session_id) return
  if (event.session_id === '__optimistic__') return
  const key = eventKey(event)
  const currentWorkflow = workflowsStore.workflows.find(
    (w) => w.name === event.workflow_name
  )
  if (currentWorkflow?.id === workflowId) {
    editingLabelId.value = null
    return
  }
  const wf = workflowsStore.workflows.find((w) => w.id === workflowId)
  const contributes = contributesToPatternProgress(event, workflowId)
  relabelingId.value = key
  timeline.optimisticallyLabelEvent(event, workflowId, wf?.name ?? workflowId, wf?.color ?? null)
  try {
    await sessionsStore.removeEventsFromSession(event.session_id, [
      { aw_bucket_id: event.aw_bucket_id, aw_event_id: event.aw_event_id },
    ])
    await api.post('/api/v1/sessions', {
      workflow_id: workflowId,
      date: timeline.date,
      events: [{ aw_bucket_id: event.aw_bucket_id, aw_event_id: event.aw_event_id }],
    })
    if (contributes) {
      timeline.markPatternContribution(workflowId, {
        aw_bucket_id: event.aw_bucket_id,
        aw_event_id: event.aw_event_id,
      })
    }
    editingLabelId.value = null
    timeline.silentRefetch()
  } catch {
    editingLabelId.value = null
    timeline.silentRefetch()
  } finally {
    relabelingId.value = null
  }
}

function relabelOptions(event: TimelineEvent) {
  const currentName = event.workflow_name ?? ''
  return workflowsStore.workflows.filter((w) => w.name !== currentName)
}

function setRowRef(el: unknown, event: TimelineEvent) {
  const key = eventKey(event)
  const row = el instanceof Element ? (el as HTMLTableRowElement) : null
  if (!row) {
    rowRefs.delete(key)
    return
  }
  rowRefs.set(key, row)
}

function isInSuggestionPreview(event: TimelineEvent) {
  if (!suggestionPreview.value) return false
  return suggestionPreview.value.event_keys.has(eventKey(event))
}

async function removeFromPatternSuggestion(event: TimelineEvent) {
  if (!suggestionPreview.value) return
  const key = eventKey(event)
  removingPatternId.value = key
  try {
    await api.post('/api/v1/suggestions/dismiss-event', {
      date: timeline.date,
      workflow_id: suggestionPreview.value.workflow_id,
      event_ref: {
        aw_bucket_id: event.aw_bucket_id,
        aw_event_id: event.aw_event_id,
      },
    })
    timeline.removeEventFromSuggestionPreview(event)
    await timeline.fetchSuggestions()
  } finally {
    removingPatternId.value = null
  }
}

watch(
  () => focusEventKey.value,
  async (key) => {
    if (!key) return
    await nextTick()
    const row = rowRefs.get(key)
    if (row) {
      row.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    timeline.consumeFocusEventKey()
  }
)
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
    <div class="max-h-[32rem] overflow-auto">
      <table class="w-full text-sm text-left">
        <thead class="sticky top-0 bg-slate-800 text-slate-400 border-b border-slate-700">
          <tr>
            <th v-if="!props.patternView" class="px-2 py-2.5 w-8">
              <input
                v-if="unlabeledEvents.length > 0"
                type="checkbox"
                :checked="allUnlabeledSelected"
                :indeterminate="someUnlabeledSelected"
                aria-label="Select all unlabeled events"
                class="rounded border-slate-600 bg-slate-700 accent-indigo-500"
                @change="toggleSelectAll"
              />
              <span v-else class="sr-only">Select</span>
            </th>
            <th class="px-3 py-2.5 font-medium w-32">App</th>
            <th class="px-3 py-2.5 font-medium">Title</th>
            <th class="px-3 py-2.5 font-medium w-16">Start</th>
            <th class="px-3 py-2.5 font-medium w-16">Duration</th>
            <th class="px-3 py-2.5 font-medium w-28">Workflow</th>
            <th class="px-3 py-2.5 font-medium">Suggestions</th>
            <th class="px-2 py-2.5 w-16"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="e in events"
            :key="`${e.aw_bucket_id}-${e.aw_event_id}`"
            :ref="(el) => setRowRef(el, e)"
            :class="[
              'border-b border-slate-800 hover:bg-slate-800/40 transition-colors',
              e.session_id && !timeline.isRecentlyPatternApplied(e) ? 'opacity-60' : '',
              timeline.isRecentlyPatternContributionEvent(e) ? 'bg-indigo-950/30 ring-1 ring-indigo-500/40' : '',
              timeline.isRecentlyPatternApplied(e) ? 'bg-emerald-950/25 ring-1 ring-emerald-600/35 animate-[pulse_1.2s_ease-in-out_2]' : '',
            ]"
          >
            <!-- Select checkbox -->
            <td v-if="!props.patternView" class="px-2 py-2">
              <input
                v-if="!e.session_id"
                type="checkbox"
                :checked="timeline.isSelected(e)"
                :aria-label="`Select ${e.data?.title ?? 'event'}`"
                class="rounded border-slate-600 bg-slate-700 accent-indigo-500"
                @change="timeline.toggleEvent(e)"
              />
              <span v-else class="inline-block w-4 text-slate-600" aria-hidden="true">—</span>
            </td>

            <!-- App -->
            <td class="px-3 py-2 font-medium text-slate-200 truncate max-w-[8rem]" :title="e.data?.app">
              {{ e.data?.app ?? '—' }}
            </td>

            <!-- Title -->
            <td class="px-3 py-2 text-slate-300 truncate max-w-xs" :title="e.data?.title">
              {{ e.data?.title ?? '—' }}
            </td>

            <!-- Start -->
            <td class="px-3 py-2 text-slate-400 whitespace-nowrap">
              {{ formatTime(e.timestamp) }}
            </td>

            <!-- Duration -->
            <td class="px-3 py-2 text-slate-400 whitespace-nowrap">
              {{ formatDuration(e.duration) }}
            </td>

            <!-- Workflow (confirmed label only) -->
            <td class="px-3 py-2">
              <template v-if="e.workflow_name">
                <span
                  class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                  :style="e.workflow_color ? { backgroundColor: e.workflow_color + '25', color: e.workflow_color } : {}"
                >
                  {{ e.workflow_name }}
                </span>
                <span
                  v-if="timeline.isRecentlyPatternContributionEvent(e)"
                  class="ml-1 inline-flex items-center rounded border border-indigo-500/40 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300"
                >
                  + Pattern progress
                </span>
              </template>
              <span v-else class="text-slate-700">—</span>
            </td>

            <!-- Suggestions column: clickable workflow chips for unlabeled rows -->
            <td class="px-3 py-1.5">
              <div v-if="!e.session_id" class="flex flex-wrap gap-1">
                <button
                  v-for="chip in suggestionsFor(e)"
                  :key="chip.id"
                  type="button"
                  :title="chip.isPrimary
                    ? `Pattern confidence: ${chip.confidence} (${chip.score} indicators)`
                    : `Assign to ${chip.name}`"
                  class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs transition-all disabled:opacity-40"
                  :class="chip.isPrimary
                    ? 'font-medium outline outline-1 hover:brightness-110'
                    : 'text-slate-500 border border-slate-700 hover:border-slate-500 hover:text-slate-300 bg-slate-800/60'"
                  :style="chip.isPrimary && chip.color
                    ? { backgroundColor: chip.color + '20', color: chip.color, outlineColor: chip.color + '60' }
                    : {}"
                  @click="quickLabel(e, chip.id)"
                >
                  <!-- Confidence dot for primary (pattern-suggested) chip -->
                  <span
                    v-if="chip.isPrimary"
                    class="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                    :class="chip.confidence === 'high' ? 'bg-emerald-400' : chip.confidence === 'medium' ? 'bg-amber-400' : 'bg-slate-500'"
                  />
                  {{ chip.name }}
                </button>
              </div>
              <div v-else-if="isEditingLabel(e)" class="flex flex-wrap items-center gap-1">
                <button
                  v-for="wf in relabelOptions(e)"
                  :key="wf.id"
                  type="button"
                  class="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors disabled:opacity-50"
                  :disabled="relabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                  @click="relabelEvent(e, wf.id)"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :style="wf.color ? { backgroundColor: wf.color } : {}"
                  />
                  {{ wf.name }}
                </button>
                <button
                  type="button"
                  class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  :disabled="relabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                  @click="cancelEditLabel()"
                >
                  Cancel
                </button>
              </div>
              <span v-else class="text-slate-700">—</span>
            </td>

            <!-- Actions column -->
            <td class="px-2 py-2">
              <button
                v-if="e.session_id"
                type="button"
                class="text-xs text-slate-500 hover:text-slate-200 disabled:opacity-50 transition-colors"
                :disabled="e.session_id === '__optimistic__' || unlabelingId === `${e.aw_bucket_id}:${e.aw_event_id}` || relabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                @click="startEditLabel(e)"
              >
                Edit label
              </button>
              <button
                v-if="e.session_id"
                type="button"
                class="ml-2 text-xs text-slate-600 hover:text-red-400 disabled:opacity-50 transition-colors"
                :disabled="e.session_id === '__optimistic__' || unlabelingId === `${e.aw_bucket_id}:${e.aw_event_id}` || relabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                @click="unlabel(e)"
              >
                Unlabel
              </button>
              <button
                v-else-if="isInSuggestionPreview(e)"
                type="button"
                class="text-xs text-slate-600 hover:text-red-400 disabled:opacity-50 transition-colors"
                :disabled="removingPatternId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                title="Remove this event from the current pattern suggestion"
                @click="removeFromPatternSuggestion(e)"
              >
                Remove from pattern
              </button>
              <span v-else class="inline-block w-8" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="events.length === 0" class="px-3 py-4 text-slate-500 text-sm text-center">
      No events to show
    </p>
  </div>
</template>
