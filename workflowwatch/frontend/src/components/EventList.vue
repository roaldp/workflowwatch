<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TimelineEvent } from '../types/timeline'
import { formatTime, formatDuration } from '../types/timeline'
import { useTimelineStore } from '../stores/timeline'
import { useSessionsStore } from '../stores/sessions'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'

const props = defineProps<{
  events: TimelineEvent[]
}>()

const timeline = useTimelineStore()
const sessionsStore = useSessionsStore()
const workflowsStore = useWorkflowsStore()
const unlabelingId = ref<string | null>(null)
const acceptingId = ref<string | null>(null)

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

// Suggestions for a row: auto-suggested workflow first, then top alternatives (max 3 total)
function suggestionsFor(event: TimelineEvent) {
  if (event.session_id) return []
  const chips: Array<{ id: string; name: string; color: string | null; isPrimary: boolean }> = []

  if (event.suggested_workflow_id && event.suggested_workflow_name) {
    chips.push({
      id: event.suggested_workflow_id,
      name: event.suggested_workflow_name,
      color: event.suggested_workflow_color ?? null,
      isPrimary: true,
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
  unlabelingId.value = `${e.aw_bucket_id}:${e.aw_event_id}`
  try {
    await sessionsStore.removeEventsFromSession(e.session_id, [
      { aw_bucket_id: e.aw_bucket_id, aw_event_id: e.aw_event_id },
    ])
    await timeline.fetchTimeline()
  } finally {
    unlabelingId.value = null
  }
}

async function acceptSuggestion(e: TimelineEvent) {
  acceptingId.value = `${e.aw_bucket_id}:${e.aw_event_id}`
  try {
    await timeline.acceptAutoLabel(e)
  } finally {
    acceptingId.value = null
  }
}

async function quickLabel(event: TimelineEvent, workflowId: string) {
  const wf = workflowsStore.workflows.find((w) => w.id === workflowId)
  // Instant optimistic update — row appears labeled immediately
  timeline.optimisticallyLabelEvent(event, workflowId, wf?.name ?? '', wf?.color ?? null)
  try {
    await api.post('/api/v1/sessions', {
      workflow_id: workflowId,
      date: timeline.date,
      events: [{ aw_bucket_id: event.aw_bucket_id, aw_event_id: event.aw_event_id }],
    })
    timeline.silentRefetch() // background sync, no loading flash
  } catch {
    timeline.fetchTimeline() // restore correct state on error
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
    <div class="max-h-[32rem] overflow-auto">
      <table class="w-full text-sm text-left">
        <thead class="sticky top-0 bg-slate-800 text-slate-400 border-b border-slate-700">
          <tr>
            <th class="px-2 py-2.5 w-8">
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
            class="border-b border-slate-800 hover:bg-slate-800/40 transition-colors"
          >
            <!-- Select checkbox -->
            <td class="px-2 py-2">
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
              <span
                v-if="e.workflow_name"
                class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                :style="e.workflow_color ? { backgroundColor: e.workflow_color + '25', color: e.workflow_color } : {}"
              >
                {{ e.workflow_name }}
              </span>
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
                    ? (e.suggestion_explanation ?? `Assign to ${chip.name}`)
                    : `Assign to ${chip.name}`"
                  class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs transition-all disabled:opacity-40"
                  :class="chip.isPrimary
                    ? 'font-medium outline outline-1 hover:brightness-110'
                    : 'text-slate-500 border border-slate-700 hover:border-slate-500 hover:text-slate-300 bg-slate-800/60'"
                  :style="chip.isPrimary && chip.color
                    ? { backgroundColor: chip.color + '20', color: chip.color, outlineColor: chip.color + '60' }
                    : {}"
                  @click="chip.isPrimary && e.suggested_workflow_id
                    ? acceptSuggestion(e)
                    : quickLabel(e, chip.id)"
                >
                  <!-- Confidence dot for primary (auto-suggested) chip -->
                  <span
                    v-if="chip.isPrimary"
                    class="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                    :class="e.suggestion_confidence === 'high' ? 'bg-emerald-400' : 'bg-amber-400'"
                  />
                  {{ chip.name }}
                </button>
              </div>
              <span v-else class="text-slate-700">—</span>
            </td>

            <!-- Actions column -->
            <td class="px-2 py-2">
              <button
                v-if="e.session_id"
                type="button"
                class="text-xs text-slate-600 hover:text-red-400 disabled:opacity-50 transition-colors"
                :disabled="unlabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                @click="unlabel(e)"
              >
                Unlabel
              </button>
              <!-- Dismiss button for auto-suggested rows -->
              <button
                v-else-if="e.suggested_workflow_id"
                type="button"
                class="text-xs text-slate-600 hover:text-red-400 transition-colors"
                title="Dismiss suggestion"
                @click="timeline.dismissAutoLabel(e)"
              >
                ✕
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
