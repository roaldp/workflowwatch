<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'
import type { SessionCreate } from '../types/session'

interface PendingRule {
  app: string
  workflowId: string
  workflowName: string
}

const timeline = useTimelineStore()
const workflowsStore = useWorkflowsStore()
const { date, events, selectedIds, hasSelection } = storeToRefs(timeline)

const open = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const suggestedWorkflowId = ref<string | null>(null)
const pendingRule = ref<PendingRule | null>(null)
const creatingRule = ref(false)

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
        if (first) suggestedWorkflowId.value = first.workflow_id
      } catch { /* ignore */ }
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

    // Suggest a rule if all selected events share the same app
    const apps = new Set(eventList.map((e) => e.data?.app).filter(Boolean))
    if (apps.size === 1) {
      const appName = [...apps][0] as string
      const workflowName = workflowsStore.workflows.find((w) => w.id === workflowId)?.name ?? ''
      pendingRule.value = { app: appName, workflowId, workflowName }
    }

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

async function createRuleFromSuggestion() {
  if (!pendingRule.value) return
  creatingRule.value = true
  try {
    await api.post('/api/v1/label-rules', {
      workflow_id: pendingRule.value.workflowId,
      rule_type: 'app',
      match_value: pendingRule.value.app,
    })
  } finally {
    creatingRule.value = false
    pendingRule.value = null
  }
}
</script>

<template>
  <div
    v-if="hasSelection"
    class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5"
  >
    <span class="text-sm text-slate-300 font-medium">
      {{ selectedIds.size }} event{{ selectedIds.size !== 1 ? 's' : '' }} selected
    </span>

    <div ref="dropdownRef" class="relative">
      <button
        type="button"
        class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-sm text-white font-medium disabled:opacity-50 transition-colors"
        :disabled="loading"
        @click="open = !open"
      >
        Label as…
      </button>
      <div
        v-if="open"
        class="absolute left-0 top-full z-20 mt-1 min-w-[14rem] rounded-lg border border-slate-600 bg-slate-800 shadow-2xl py-1"
      >
        <button
          v-for="wf in sortedWorkflows"
          :key="wf.id"
          type="button"
          class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-700 transition-colors"
          @click="labelAs(wf.id)"
        >
          <span
            class="h-2.5 w-2.5 shrink-0 rounded-sm"
            :style="wf.color ? { backgroundColor: wf.color } : {}"
          />
          {{ wf.name }}
          <span
            v-if="suggestedWorkflowId === wf.id"
            class="ml-auto text-xs text-indigo-400 font-medium"
          >
            Suggested
          </span>
        </button>
        <p v-if="sortedWorkflows.length === 0" class="px-3 py-2 text-sm text-slate-500">
          No workflows — create one in the sidebar.
        </p>
      </div>
    </div>

    <button
      type="button"
      class="text-sm text-slate-500 hover:text-slate-300 transition-colors"
      @click="timeline.clearSelection()"
    >
      Clear
    </button>

    <p v-if="error" class="w-full text-sm text-red-400">{{ error }}</p>
  </div>

  <!-- Rule suggestion (shown after labeling, outside the selection bar) -->
  <div
    v-if="pendingRule"
    class="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-800/40 bg-emerald-950/20 px-3 py-2.5"
  >
    <span class="text-sm text-emerald-300">
      Always label <strong class="text-white">{{ pendingRule.app }}</strong> as
      <strong class="text-white">{{ pendingRule.workflowName }}</strong>?
    </span>
    <div class="ml-auto flex items-center gap-2">
      <button
        type="button"
        class="rounded-md bg-emerald-700 hover:bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50 transition-colors"
        :disabled="creatingRule"
        @click="createRuleFromSuggestion"
      >
        {{ creatingRule ? 'Creating…' : 'Create rule' }}
      </button>
      <button
        type="button"
        class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        @click="pendingRule = null"
      >
        Dismiss
      </button>
    </div>
  </div>
</template>
