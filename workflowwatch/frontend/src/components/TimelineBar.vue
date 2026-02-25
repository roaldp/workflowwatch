<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEvent } from '../types/timeline'
import { appColor } from '../types/timeline'
import { formatTime, formatDuration } from '../types/timeline'

const props = defineProps<{
  events: TimelineEvent[]
  date: string
}>()

const DAY_MS = 24 * 60 * 60 * 1000

const dayStart = computed(() => new Date(props.date + 'T00:00:00').getTime())
const dayEnd = computed(() => dayStart.value + DAY_MS)

const blocks = computed(() => {
  const start = dayStart.value
  const end = dayEnd.value
  const total = end - start
  return props.events.map((e) => {
    const t = new Date(e.timestamp).getTime()
    const left = Math.max(0, ((t - start) / total) * 100)
    const width = Math.min(
      (e.duration * 1000 / total) * 100,
      100 - left
    )
    const color = e.workflow_color || appColor(e.data?.app)
    return {
      ...e,
      left: `${left}%`,
      width: `${Math.max(width, 0.5)}%`,
      color,
      tooltip: `${e.data?.app ?? '?'} — ${e.data?.title ?? ''} (${formatDuration(e.duration)})`,
      timeRange: `${formatTime(e.timestamp)} – ${formatTime(new Date(t + e.duration * 1000).toISOString())}`,
    }
  })
})
</script>

<template>
  <div class="w-full">
    <div class="text-xs text-slate-500 mb-1 flex justify-between">
      <span>00:00</span>
      <span>24h</span>
    </div>
    <div
      class="relative h-10 w-full rounded bg-slate-200 dark:bg-slate-700 overflow-hidden"
      role="img"
      aria-label="Timeline of events"
    >
      <div
        v-for="block in blocks"
        :key="`${block.aw_bucket_id}-${block.aw_event_id}`"
        class="absolute top-0.5 bottom-0.5 rounded-sm transition-opacity hover:opacity-90 cursor-default"
        :style="{
          left: block.left,
          width: block.width,
          backgroundColor: block.color,
          minWidth: '4px',
          boxShadow: block.session_id && block.workflow_color ? `inset 3px 0 0 0 ${block.workflow_color}` : undefined,
        }"
        :title="block.timeRange + ' — ' + block.tooltip"
      >
        <span class="sr-only">{{ block.tooltip }}</span>
      </div>
    </div>
    <p v-if="events.length === 0" class="text-sm text-slate-500 mt-2">
      No events this day
    </p>
  </div>
</template>
