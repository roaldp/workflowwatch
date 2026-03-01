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

    // Color priority: confirmed label > auto-suggestion > app hash
    const isSuggested = !e.session_id && !!e.suggested_workflow_id
    const color = e.workflow_color
      || (isSuggested ? e.suggested_workflow_color : null)
      || appColor(e.data?.app)

    // Suggested events render at reduced opacity to signal "pending"
    const opacity = isSuggested
      ? (e.suggestion_confidence === 'high' ? 0.55 : 0.35)
      : 1

    const tooltipSuffix = isSuggested
      ? ` [Auto: ${e.suggested_workflow_name}${e.suggestion_confidence === 'high' ? ' ●' : ' ◐'}]`
      : ''

    return {
      ...e,
      left: `${left}%`,
      width: `${Math.max(width, 0.5)}%`,
      color,
      opacity,
      isSuggested,
      tooltip: `${e.data?.app ?? '?'} — ${e.data?.title ?? ''} (${formatDuration(e.duration)})${tooltipSuffix}`,
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
          opacity: block.opacity,
          minWidth: '4px',
          boxShadow: block.session_id && block.workflow_color
            ? `inset 3px 0 0 0 ${block.workflow_color}`
            : block.isSuggested && block.suggested_workflow_color
              ? `inset 2px 0 0 0 ${block.suggested_workflow_color}88`
              : undefined,
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
