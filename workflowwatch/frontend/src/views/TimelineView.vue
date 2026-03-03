<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import TimelineBar from '../components/TimelineBar.vue'
import EventList from '../components/EventList.vue'
import LabelAsBar from '../components/LabelAsBar.vue'
import SuggestionsPanel from '../components/SuggestionsPanel.vue'
import DailyStreakPanel from '../components/DailyStreakPanel.vue'

const store = useTimelineStore()
const { date, events, loading, error, suggestionPreview } = storeToRefs(store)
const eventSearch = ref('')
const appFilter = ref('')

const filteredEvents = computed(() => {
  const preview = suggestionPreview.value
  if (!preview) return events.value
  return events.value.filter((e) => preview.event_keys.has(`${e.aw_bucket_id}:${e.aw_event_id}`))
})

const appOptions = computed(() => {
  const apps = new Set<string>()
  for (const e of filteredEvents.value) {
    const app = e.data?.app
    if (app) apps.add(app)
  }
  return [...apps].sort((a, b) => a.localeCompare(b))
})

const displayedEvents = computed(() => {
  const q = eventSearch.value.trim().toLowerCase()
  return filteredEvents.value.filter((e) => {
    if (appFilter.value && e.data?.app !== appFilter.value) return false
    if (!q) return true
    const app = (e.data?.app ?? '').toLowerCase()
    const title = (e.data?.title ?? '').toLowerCase()
    return app.includes(q) || title.includes(q)
  })
})

const unlabeledCount = computed(() =>
  displayedEvents.value.filter((e) => !e.session_id).length
)
const labeledCount = computed(() =>
  displayedEvents.value.filter((e) => !!e.session_id).length
)

function selectAllShownUnlabeled() {
  const visibleUnlabeled = displayedEvents.value.filter((e) => !e.session_id)
  if (visibleUnlabeled.length === 0) return
  const allVisibleSelected = visibleUnlabeled.every((e) => store.isSelected(e))

  for (const event of visibleUnlabeled) {
    const isSelected = store.isSelected(event)
    if (allVisibleSelected && isSelected) store.toggleEvent(event)
    if (!allVisibleSelected && !isSelected) store.toggleEvent(event)
  }
}

function clearEventFilters() {
  eventSearch.value = ''
  appFilter.value = ''
}
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
      <DailyStreakPanel />
      <SuggestionsPanel />
      <LabelAsBar />
      <section>
        <div
          v-if="suggestionPreview"
          class="mb-2 rounded-lg border border-amber-800/50 bg-amber-950/20 px-3 py-2"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="rounded border border-amber-600/50 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300">
              Pattern-match view
            </span>
            <p class="text-sm text-amber-200">
              Previewing
              <strong>{{ suggestionPreview.workflow_name }}</strong>
              on {{ filteredEvents.length }} affected events.
            </p>
            <button
              type="button"
              class="ml-auto text-xs text-slate-400 hover:text-slate-200 transition-colors"
              @click="store.clearSuggestionPreview()"
            >
              Clear preview
            </button>
          </div>
          <p v-if="suggestionPreview.matched_indicators.length" class="mt-1 text-xs text-slate-400">
            Pattern checks: {{ suggestionPreview.matched_indicators.join(' · ') }}
          </p>
        </div>
        <div class="mb-2 flex items-center justify-between gap-2">
          <div class="flex items-center gap-3">
            <h2 class="text-sm font-medium text-slate-600 dark:text-slate-400">
              Events
              <span v-if="suggestionPreview" class="ml-2 text-xs font-normal text-amber-400">
                Pattern-match view
              </span>
            </h2>
            <span v-if="!suggestionPreview && (labeledCount > 0 || unlabeledCount > 0)" class="text-xs text-slate-500">
              <span class="text-emerald-500 font-medium">{{ labeledCount }}</span> labeled
              <span class="mx-1 text-slate-700">·</span>
              <span :class="unlabeledCount > 0 ? 'text-slate-400' : 'text-slate-600'">{{ unlabeledCount }}</span> unlabeled
            </span>
          </div>
          <button
            v-if="unlabeledCount > 0 && !suggestionPreview"
            type="button"
            class="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            @click="selectAllShownUnlabeled()"
          >
            Select all unlabeled
          </button>
        </div>
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <input
            v-model="eventSearch"
            type="text"
            placeholder="Search app or title"
            class="min-w-[14rem] rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <select
            v-model="appFilter"
            class="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All apps</option>
            <option v-for="app in appOptions" :key="app" :value="app">{{ app }}</option>
          </select>
          <button
            v-if="eventSearch || appFilter"
            type="button"
            class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            @click="clearEventFilters()"
          >
            Clear filters
          </button>
        </div>
        <EventList :events="displayedEvents" :pattern-view="!!suggestionPreview" />
      </section>
      <p v-if="events.length === 0" class="text-slate-500 text-sm">No activity recorded for this day.</p>
      <p v-else-if="suggestionPreview && filteredEvents.length === 0" class="text-slate-500 text-sm">
        No events left in this preview.
      </p>
    </template>
  </div>
</template>
