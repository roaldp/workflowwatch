<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import WorkflowSidebar from '../components/WorkflowSidebar.vue'
import TimelineView from './TimelineView.vue'
import SessionsView from './SessionsView.vue'
import { useTimelineStore } from '../stores/timeline'

const timeline = useTimelineStore()
const { date } = storeToRefs(timeline)
const mainView = ref<'timeline' | 'sessions'>('timeline')

onMounted(() => {
  timeline.fetchTimeline()
})
</script>

<template>
  <div class="flex flex-col h-screen">
    <header class="shrink-0 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-3 flex items-center justify-between gap-4">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-semibold text-slate-800 dark:text-slate-100">WorkflowWatch</h1>
        <nav class="flex gap-1">
          <button
            type="button"
            :class="mainView === 'timeline' ? 'bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'"
            class="rounded px-2 py-1.5 text-sm font-medium"
            @click="mainView = 'timeline'"
          >
            Timeline
          </button>
          <button
            type="button"
            :class="mainView === 'sessions' ? 'bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'"
            class="rounded px-2 py-1.5 text-sm font-medium"
            @click="mainView = 'sessions'"
          >
            Sessions
          </button>
        </nav>
      </div>
      <div v-if="mainView === 'timeline'" class="flex items-center gap-2">
        <button
          type="button"
          class="rounded px-2 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          @click="timeline.goToday()"
        >
          Today
        </button>
        <button
          type="button"
          class="rounded p-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          aria-label="Previous day"
          @click="timeline.goPrev()"
        >
          ◀
        </button>
        <button
          type="button"
          class="rounded p-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
          aria-label="Next day"
          @click="timeline.goNext()"
        >
          ▶
        </button>
        <input
          v-model="date"
          type="date"
          class="rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200 px-2 py-1.5 text-sm"
          @change="timeline.fetchTimeline()"
        />
      </div>
    </header>
    <div class="flex flex-1 min-h-0">
      <WorkflowSidebar />
      <main class="flex-1 overflow-auto p-6 bg-slate-100 dark:bg-slate-900">
        <TimelineView v-if="mainView === 'timeline'" />
        <SessionsView v-else />
      </main>
    </div>
  </div>
</template>
