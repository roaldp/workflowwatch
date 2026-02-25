<script setup lang="ts">
import { ref } from 'vue'
import type { TimelineEvent } from '../types/timeline'
import { formatTime, formatDuration } from '../types/timeline'
import { useTimelineStore } from '../stores/timeline'
import { useSessionsStore } from '../stores/sessions'

defineProps<{
  events: TimelineEvent[]
}>()

const timeline = useTimelineStore()
const sessionsStore = useSessionsStore()
const unlabelingId = ref<string | null>(null)

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
</script>

<template>
  <div class="rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
    <div class="max-h-80 overflow-auto">
      <table class="w-full text-sm text-left">
        <thead class="sticky top-0 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
          <tr>
            <th class="px-2 py-2 w-8" aria-label="Select">
              <span class="sr-only">Select</span>
            </th>
            <th class="px-3 py-2 font-medium">App</th>
            <th class="px-3 py-2 font-medium">Title</th>
            <th class="px-3 py-2 font-medium hidden md:table-cell">URL</th>
            <th class="px-3 py-2 font-medium w-16">Start</th>
            <th class="px-3 py-2 font-medium w-20">Duration</th>
            <th class="px-3 py-2 font-medium w-24">Workflow</th>
            <th class="px-2 py-2 w-20" aria-label="Actions"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="e in events"
            :key="`${e.aw_bucket_id}-${e.aw_event_id}`"
            class="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30"
          >
            <td class="px-2 py-2">
              <input
                v-if="!e.session_id"
                type="checkbox"
                :checked="timeline.isSelected(e)"
                :aria-label="`Select ${e.data?.title ?? 'event'}`"
                class="rounded border-slate-300 dark:border-slate-600"
                @change="timeline.toggleEvent(e)"
              />
              <span v-else class="inline-block w-4" aria-hidden="true">—</span>
            </td>
            <td class="px-3 py-2 font-medium text-slate-800 dark:text-slate-200">
              {{ e.data?.app ?? '—' }}
            </td>
            <td class="px-3 py-2 text-slate-700 dark:text-slate-300 truncate max-w-xs" :title="e.data?.title">
              {{ e.data?.title ?? '—' }}
            </td>
            <td class="px-3 py-2 text-slate-600 dark:text-slate-400 hidden md:table-cell truncate max-w-xs" :title="e.data?.url">
              {{ e.data?.url ?? '—' }}
            </td>
            <td class="px-3 py-2 text-slate-600 dark:text-slate-400 whitespace-nowrap">
              {{ formatTime(e.timestamp) }}
            </td>
            <td class="px-3 py-2 text-slate-600 dark:text-slate-400 whitespace-nowrap">
              {{ formatDuration(e.duration) }}
            </td>
            <td class="px-3 py-2">
              <span
                v-if="e.workflow_name"
                class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium"
                :style="e.workflow_color ? { backgroundColor: e.workflow_color + '22', color: e.workflow_color } : {}"
              >
                {{ e.workflow_name }}
              </span>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td class="px-2 py-2">
              <button
                v-if="e.session_id"
                type="button"
                class="text-xs text-slate-500 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-50"
                :disabled="unlabelingId === `${e.aw_bucket_id}:${e.aw_event_id}`"
                @click="unlabel(e)"
              >
                Unlabel
              </button>
              <span v-else class="inline-block w-10" />
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
