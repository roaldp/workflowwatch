<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import WorkflowSidebar from '../components/WorkflowSidebar.vue'
import TimelineView from './TimelineView.vue'
import SessionsView from './SessionsView.vue'
import { useTimelineStore } from '../stores/timeline'
import { useSessionsStore } from '../stores/sessions'

const timeline = useTimelineStore()
const sessionsStore = useSessionsStore()
const { date } = storeToRefs(timeline)
const mainView = ref<'timeline' | 'sessions'>('timeline')

onMounted(() => {
  timeline.fetchTimeline()
})

function navigateToWorkflow(workflowId: string) {
  sessionsStore.workflowId = workflowId
  mainView.value = 'sessions'
  sessionsStore.fetchSessions()
}

function switchToSessions() {
  sessionsStore.workflowId = null
  mainView.value = 'sessions'
  sessionsStore.fetchSessions()
}
</script>

<template>
  <div class="flex flex-col h-screen bg-slate-950 text-slate-100">
    <!-- Header -->
    <header class="shrink-0 border-b border-slate-800 bg-slate-900 px-4 py-3 flex items-center justify-between gap-4">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-semibold text-white tracking-tight">WorkflowWatch</h1>
        <nav class="flex gap-0.5">
          <button
            type="button"
            :class="mainView === 'timeline'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
            class="rounded px-3 py-1.5 text-sm font-medium transition-colors"
            @click="mainView = 'timeline'"
          >
            Timeline
          </button>
          <button
            type="button"
            :class="mainView === 'sessions'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
            class="rounded px-3 py-1.5 text-sm font-medium transition-colors"
            @click="switchToSessions"
          >
            Sessions
          </button>
        </nav>
      </div>

      <div v-if="mainView === 'timeline'" class="flex items-center gap-1.5">
        <button
          type="button"
          class="rounded px-2.5 py-1.5 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          @click="timeline.goToday()"
        >
          Today
        </button>
        <button
          type="button"
          class="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors text-xs"
          aria-label="Previous day"
          @click="timeline.goPrev()"
        >
          ◀
        </button>
        <button
          type="button"
          class="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors text-xs"
          aria-label="Next day"
          @click="timeline.goNext()"
        >
          ▶
        </button>
        <input
          v-model="date"
          type="date"
          class="rounded-lg border border-slate-700 bg-slate-800 text-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:border-indigo-500"
          @change="timeline.fetchTimeline()"
        />
      </div>
    </header>

    <div class="flex flex-1 min-h-0">
      <WorkflowSidebar @go-to-sessions="navigateToWorkflow" />
      <main class="flex-1 overflow-auto p-6 bg-slate-950">
        <TimelineView v-if="mainView === 'timeline'" />
        <SessionsView v-else />
      </main>
    </div>
  </div>
</template>
