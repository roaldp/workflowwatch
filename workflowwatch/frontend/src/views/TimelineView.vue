<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import TimelineBar from '../components/TimelineBar.vue'
import EventList from '../components/EventList.vue'
import LabelAsBar from '../components/LabelAsBar.vue'
import SuggestionsPanel from '../components/SuggestionsPanel.vue'
import AutoLabelBar from '../components/AutoLabelBar.vue'

const store = useTimelineStore()
const { date, events, loading, error } = storeToRefs(store)

const unlabeledCount = computed(() =>
  events.value.filter((e) => !e.session_id).length
)
</script>

<template>
  <div class="space-y-4">
    <div v-if="loading" class="flex items-center justify-center py-12">
      <span class="text-slate-500">Loading timeline…</span>
    </div>
    <div v-else-if="error" class="rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
      <p class="text-red-700 dark:text-red-300">{{ error }}</p>
      <button
        type="button"
        class="mt-2 rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
        @click="store.fetchTimeline()"
      >
        Retry
      </button>
    </div>
    <template v-else>
      <section>
        <h2 class="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">Timeline</h2>
        <TimelineBar :events="events" :date="date" />
      </section>
      <AutoLabelBar />
      <SuggestionsPanel />
      <LabelAsBar />
      <section>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-sm font-medium text-slate-600 dark:text-slate-400">Events</h2>
          <button
            v-if="unlabeledCount > 0"
            type="button"
            class="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            @click="store.selectAllUnlabeled()"
          >
            Select all unlabeled
          </button>
        </div>
        <EventList :events="events" />
      </section>
      <p v-if="events.length === 0" class="text-slate-500 text-sm">
        No activity recorded for this day.
      </p>
    </template>
  </div>
</template>
