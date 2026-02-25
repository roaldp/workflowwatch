<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import { useWorkflowsStore } from '../stores/workflows'

onMounted(() => {
  workflowsStore.fetchWorkflows()
})
import { api } from '../api/client'
import type { Suggestion } from '../types/session'
import type { SessionCreate } from '../types/session'

const timeline = useTimelineStore()
const workflowsStore = useWorkflowsStore()
const { date, suggestions, suggestionsLoading } = storeToRefs(timeline)

function workflowName(workflowId: string): string {
  return workflowsStore.workflows.find((w) => w.id === workflowId)?.name ?? workflowId
}

function workflowColor(workflowId: string): string | null {
  return workflowsStore.workflows.find((w) => w.id === workflowId)?.color ?? null
}

function workflowStyle(workflowId: string): Record<string, string> {
  const c = workflowColor(workflowId)
  return c ? { backgroundColor: c } : {}
}

const applying = ref(false)
async function applySuggestion(s: Suggestion) {
  applying.value = true
  try {
    const body: SessionCreate = {
      workflow_id: s.workflow_id,
      date: date.value,
      events: s.event_refs,
    }
    await api.post('/api/v1/sessions', body)
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
  <section v-else-if="suggestions.length > 0" class="rounded border border-slate-200 dark:border-slate-700 bg-amber-50/50 dark:bg-amber-950/20 p-3">
    <h2 class="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
      Suggested labels (pattern match)
    </h2>
    <ul class="space-y-2">
      <li
        v-for="(s, i) in suggestions"
        :key="i"
        class="flex flex-wrap items-center gap-2 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
      >
        <span
          class="h-3 w-3 shrink-0 rounded-full"
          :style="workflowStyle(s.workflow_id)"
        />
        <span class="font-medium text-slate-800 dark:text-slate-200">
          {{ workflowName(s.workflow_id) }}
        </span>
        <span class="text-slate-500 text-sm">
          ({{ s.event_refs.length }} events, {{ s.score }} indicators)
        </span>
        <button
          type="button"
          class="ml-auto rounded bg-slate-600 px-2 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-50"
          :disabled="applying"
          @click="applySuggestion(s)"
        >
          Apply
        </button>
        <p v-if="s.matched_indicators?.length" class="w-full text-xs text-slate-500 mt-1">
          Matched: {{ s.matched_indicators.slice(0, 3).join(', ') }}
        </p>
      </li>
    </ul>
  </section>
</template>
