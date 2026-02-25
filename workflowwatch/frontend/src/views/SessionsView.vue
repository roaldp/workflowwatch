<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useSessionsStore } from '../stores/sessions'
import { useWorkflowsStore } from '../stores/workflows'
import SessionCard from '../components/SessionCard.vue'

const sessionsStore = useSessionsStore()
const workflowsStore = useWorkflowsStore()
const { sessionsByDay, loading, error, start, end } = storeToRefs(sessionsStore)

onMounted(async () => {
  await workflowsStore.fetchWorkflows()
  await sessionsStore.fetchSessions()
})

function workflowFor(session: { workflow_id: string }) {
  return workflowsStore.workflows.find((w) => w.id === session.workflow_id)
}

const dateRangeLabel = computed(() => `${start.value} to ${end.value}`)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-medium text-slate-800 dark:text-slate-200">
        Sessions
      </h2>
      <p class="text-sm text-slate-500">{{ dateRangeLabel }}</p>
    </div>
    <div v-if="loading" class="py-8 text-center text-slate-500">
      Loading sessions…
    </div>
    <div v-else-if="error" class="rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
      <p class="text-red-700 dark:text-red-300">{{ error }}</p>
      <button
        type="button"
        class="mt-2 rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
        @click="sessionsStore.fetchSessions()"
      >
        Retry
      </button>
    </div>
    <template v-else>
      <div v-for="{ day, sessions: daySessions } in sessionsByDay" :key="day" class="space-y-2">
        <h3 class="text-sm font-medium text-slate-600 dark:text-slate-400">
          {{ day }}
        </h3>
        <div class="space-y-2">
          <SessionCard
            v-for="session in daySessions"
            :key="session.id"
            :session="session"
            :workflow-name="workflowFor(session)?.name ?? 'Unknown'"
            :workflow-color="workflowFor(session)?.color ?? null"
          />
        </div>
      </div>
      <p v-if="sessionsByDay.length === 0" class="text-slate-500 text-sm">
        No sessions in this range.
      </p>
    </template>
  </div>
</template>
