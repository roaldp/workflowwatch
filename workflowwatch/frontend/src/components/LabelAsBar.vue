<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'
import type { SessionCreate } from '../types/session'

const timeline = useTimelineStore()
const workflowsStore = useWorkflowsStore()
const { date, events, selectedIds, hasSelection } = storeToRefs(timeline)

const open = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const suggestedWorkflowId = ref<string | null>(null)

watch(open, async (isOpen) => {
  if (isOpen) {
    error.value = null
    suggestedWorkflowId.value = null
    await workflowsStore.fetchWorkflows()
    if (hasSelection.value && selectedIds.value.size > 0) {
      const selectedEvents = events.value.filter((e) =>
        selectedIds.value.has(`${e.aw_bucket_id}:${e.aw_event_id}`)
      )
      const payload = selectedEvents.map((e) => ({
        app: e.data?.app ?? undefined,
        title: e.data?.title ?? undefined,
        url: e.data?.url ?? undefined,
      }))
      try {
        const res = await api.post<{ ranked: { workflow_id: string }[] }>(
          '/api/v1/suggestions/score',
          { events: payload }
        )
        const first = res.ranked?.[0]
        if (first) {
          suggestedWorkflowId.value = first.workflow_id
        }
      } catch {
        // ignore score failure
      }
    }
  }
})

const sortedWorkflows = computed(() => {
  const list = [...workflowsStore.workflows]
  const sid = suggestedWorkflowId.value
  if (!sid) return list
  const suggested = list.find((w) => w.id === sid)
  if (!suggested) return list
  return [suggested, ...list.filter((w) => w.id !== sid)]
})

function handleClickOutside(e: MouseEvent) {
  if (open.value && dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

async function labelAs(workflowId: string) {
  if (!hasSelection.value || selectedIds.value.size === 0) return
  loading.value = true
  error.value = null
  try {
    const eventList = events.value.filter((e) =>
      selectedIds.value.has(`${e.aw_bucket_id}:${e.aw_event_id}`)
    )
    const body: SessionCreate = {
      workflow_id: workflowId,
      date: date.value,
      events: eventList.map((e) => ({
        aw_bucket_id: e.aw_bucket_id,
        aw_event_id: e.aw_event_id,
      })),
    }
    await api.post('/api/v1/sessions', body)
    timeline.clearSelection()
    await timeline.fetchTimeline()
    open.value = false
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Failed to create session'
    try {
      const parsed = JSON.parse(msg)
      error.value = parsed.detail ?? msg
    } catch {
      error.value = msg
    }
  } finally {
    loading.value = false
  }
}

</script>

<template>
  <div v-if="hasSelection" class="flex flex-wrap items-center gap-2 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3 py-2">
    <span class="text-sm text-slate-600 dark:text-slate-400">
      {{ selectedIds.size }} selected
    </span>
    <div ref="dropdownRef" class="relative">
      <button
        type="button"
        class="rounded bg-slate-700 dark:bg-slate-600 px-3 py-1.5 text-sm text-white hover:bg-slate-600 dark:hover:bg-slate-500 disabled:opacity-50"
        :disabled="loading"
        @click="open = !open"
      >
        Label as…
      </button>
      <div
        v-if="open"
        class="absolute left-0 top-full z-10 mt-1 min-w-[12rem] rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg py-1"
      >
        <button
          v-for="wf in sortedWorkflows"
          :key="wf.id"
          type="button"
          class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700"
          @click="labelAs(wf.id)"
        >
          <span
            class="h-3 w-3 shrink-0 rounded-full"
            :style="wf.color ? { backgroundColor: wf.color } : {}"
          />
          {{ wf.name }}
          <span v-if="suggestedWorkflowId === wf.id" class="text-xs text-amber-600 dark:text-amber-400">Suggested</span>
        </button>
        <p
          v-if="sortedWorkflows.length === 0"
          class="px-3 py-2 text-sm text-slate-500"
        >
          No workflows. Create one in the sidebar.
        </p>
      </div>
    </div>
    <button
      type="button"
      class="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
      @click="timeline.clearSelection()"
    >
      Clear
    </button>
    <p v-if="error" class="w-full text-sm text-red-600 dark:text-red-400">
      {{ error }}
    </p>
  </div>
</template>
