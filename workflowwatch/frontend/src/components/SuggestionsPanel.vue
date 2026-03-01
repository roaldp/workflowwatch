<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'
import { formatTime, formatDuration } from '../types/timeline'
import type { Suggestion, SessionCreate } from '../types/session'
import type { TimelineEvent } from '../types/timeline'

onMounted(() => workflowsStore.fetchWorkflows())

const timeline = useTimelineStore()
const workflowsStore = useWorkflowsStore()
const { date, suggestions, suggestionsLoading, events } = storeToRefs(timeline)

const expandedIndex = ref<number | null>(null)

function workflowName(id: string) {
  return workflowsStore.workflows.find((w) => w.id === id)?.name ?? id
}
function workflowColor(id: string) {
  return workflowsStore.workflows.find((w) => w.id === id)?.color ?? null
}

function toggleExpand(i: number) {
  expandedIndex.value = expandedIndex.value === i ? null : i
}

function linkedEvents(s: Suggestion): TimelineEvent[] {
  const refSet = new Set(
    s.event_refs.map((r) => `${r.aw_bucket_id}:${r.aw_event_id}`)
  )
  return events.value.filter(
    (e) => refSet.has(`${e.aw_bucket_id}:${e.aw_event_id}`)
  )
}

const MAX_VISIBLE_EVENTS = 50

const applying = ref(false)
async function applySuggestion(s: Suggestion) {
  applying.value = true
  try {
    const body: SessionCreate = { workflow_id: s.workflow_id, date: date.value, events: s.event_refs }
    await api.post('/api/v1/sessions', body)
    expandedIndex.value = null
    await timeline.fetchTimeline()
    await timeline.fetchSuggestions()
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <section v-if="suggestionsLoading" class="text-sm text-slate-500">
    Loading suggestions…
  </section>
  <section
    v-else-if="suggestions.length > 0"
    class="rounded-lg border border-amber-800/40 bg-amber-950/20 p-3"
  >
    <h2 class="text-sm font-medium text-amber-400 mb-2">Pattern-matched suggestions</h2>
    <ul class="space-y-2">
      <li
        v-for="(s, i) in suggestions"
        :key="i"
        class="rounded-lg border border-slate-700 bg-slate-800 overflow-hidden"
      >
        <!-- Header row -->
        <div class="flex flex-wrap items-center gap-2 px-3 py-2">
          <span
            class="h-2.5 w-2.5 shrink-0 rounded-sm"
            :style="workflowColor(s.workflow_id) ? { backgroundColor: workflowColor(s.workflow_id)! } : {}"
          />
          <span class="font-medium text-slate-200">{{ workflowName(s.workflow_id) }}</span>
          <button
            type="button"
            class="text-slate-500 text-xs hover:text-slate-300 transition-colors cursor-pointer"
            @click="toggleExpand(i)"
          >
            {{ s.event_refs.length }} events · {{ s.score }} indicators
            <span class="ml-0.5">{{ expandedIndex === i ? '▾' : '▸' }}</span>
          </button>
          <button
            type="button"
            class="ml-auto rounded-lg bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50 transition-colors"
            :disabled="applying"
            @click="applySuggestion(s)"
          >
            Apply
          </button>
          <p v-if="s.matched_indicators?.length" class="w-full text-xs text-slate-500 mt-0.5">
            {{ s.matched_indicators.slice(0, 3).join(' · ') }}
          </p>
        </div>

        <!-- Expandable events table -->
        <div v-if="expandedIndex === i" class="border-t border-slate-700">
          <div class="max-h-64 overflow-auto">
            <table class="w-full text-xs text-left">
              <thead class="sticky top-0 bg-slate-800 text-slate-400 border-b border-slate-700">
                <tr>
                  <th class="px-3 py-1.5 font-medium">App</th>
                  <th class="px-3 py-1.5 font-medium">Title</th>
                  <th class="px-3 py-1.5 font-medium w-16">Start</th>
                  <th class="px-3 py-1.5 font-medium w-16">Duration</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="e in linkedEvents(s).slice(0, MAX_VISIBLE_EVENTS)"
                  :key="`${e.aw_bucket_id}-${e.aw_event_id}`"
                  class="border-b border-slate-800/60 hover:bg-slate-700/30"
                >
                  <td class="px-3 py-1 text-slate-300 truncate max-w-[8rem]" :title="e.data?.app">
                    {{ e.data?.app ?? '—' }}
                  </td>
                  <td class="px-3 py-1 text-slate-400 truncate max-w-xs" :title="e.data?.title">
                    {{ e.data?.title ?? '—' }}
                  </td>
                  <td class="px-3 py-1 text-slate-500 whitespace-nowrap">
                    {{ formatTime(e.timestamp) }}
                  </td>
                  <td class="px-3 py-1 text-slate-500 whitespace-nowrap">
                    {{ formatDuration(e.duration) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p
            v-if="linkedEvents(s).length > MAX_VISIBLE_EVENTS"
            class="px-3 py-1 text-xs text-slate-600"
          >
            Showing {{ MAX_VISIBLE_EVENTS }} of {{ linkedEvents(s).length }} events
          </p>
        </div>
      </li>
    </ul>
  </section>
</template>
