<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Session, SessionWithEvents } from '../types/session'
import { formatTime, formatDuration } from '../types/timeline'
import { useSessionsStore } from '../stores/sessions'

const props = defineProps<{
  session: Session
  workflowName: string
  workflowColor: string | null
}>()

const sessionsStore = useSessionsStore()

const expanded = ref(false)
const detail = ref<SessionWithEvents | null>(null)
const loadingDetail = ref(false)

const durationFormatted = computed(() => formatDuration(props.session.duration))
const timeRange = computed(() => {
  const s = props.session.started_at
  const e = props.session.ended_at
  return `${formatTime(s)} – ${formatTime(e)}`
})

async function toggleExpand() {
  if (expanded.value) {
    expanded.value = false
    return
  }
  loadingDetail.value = true
  detail.value = await sessionsStore.fetchSession(props.session.id)
  loadingDetail.value = false
  expanded.value = true
}

const editing = ref(false)
const editTitle = ref('')
const editNotes = ref('')

function startEdit() {
  editTitle.value = props.session.title ?? ''
  editNotes.value = props.session.notes ?? ''
  editing.value = true
}

async function saveEdit() {
  await sessionsStore.updateSession(props.session.id, {
    title: editTitle.value || null,
    notes: editNotes.value || null,
  })
  editing.value = false
}

function cancelEdit() {
  editing.value = false
}

async function confirmDelete() {
  if (!confirm('Delete this session? Events will become unlabeled.')) return
  await sessionsStore.deleteSession(props.session.id)
}

async function removeEvent(aw_bucket_id: string, aw_event_id: number) {
  await sessionsStore.removeEventsFromSession(props.session.id, [
    { aw_bucket_id, aw_event_id },
  ])
  detail.value = await sessionsStore.fetchSession(props.session.id)
  if (detail.value && detail.value.events.length === 0) {
    expanded.value = false
    detail.value = null
  }
}
</script>

<template>
  <div class="rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
    <div
      class="flex flex-wrap items-center gap-2 px-3 py-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50"
      @click="toggleExpand"
    >
      <span
        class="h-3 w-3 shrink-0 rounded-full"
        :style="workflowColor ? { backgroundColor: workflowColor } : {}"
      />
      <span class="font-medium text-slate-800 dark:text-slate-200">
        {{ workflowName }}
      </span>
      <span v-if="session.title" class="text-slate-600 dark:text-slate-400 text-sm">
        — {{ session.title }}
      </span>
      <span class="text-slate-500 text-sm ml-auto">
        {{ timeRange }} · {{ durationFormatted }}
      </span>
      <span class="text-slate-400 text-sm">
        {{ detail?.events?.length ?? '…' }} events
      </span>
    </div>
    <div v-if="expanded" class="border-t border-slate-200 dark:border-slate-700 px-3 py-2">
      <div v-if="loadingDetail" class="text-sm text-slate-500">Loading…</div>
      <template v-else-if="detail">
        <div v-if="editing" class="space-y-2 mb-3">
          <input
            v-model="editTitle"
            type="text"
            placeholder="Title (optional)"
            class="w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-2 py-1.5 text-sm"
          />
          <textarea
            v-model="editNotes"
            placeholder="Notes (optional)"
            rows="2"
            class="w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-2 py-1.5 text-sm"
          />
          <div class="flex gap-2">
            <button
              type="button"
              class="rounded bg-slate-600 px-2 py-1 text-sm text-white hover:bg-slate-700"
              @click="saveEdit"
            >
              Save
            </button>
            <button
              type="button"
              class="rounded border border-slate-300 dark:border-slate-600 px-2 py-1 text-sm"
              @click="cancelEdit"
            >
              Cancel
            </button>
          </div>
        </div>
        <div v-else class="flex gap-2 mb-3">
          <button
            type="button"
            class="text-sm text-slate-600 dark:text-slate-400 hover:underline"
            @click.stop="startEdit"
          >
            Edit
          </button>
          <button
            type="button"
            class="text-sm text-red-600 dark:text-red-400 hover:underline"
            @click.stop="confirmDelete"
          >
            Delete
          </button>
        </div>
        <div class="text-xs text-slate-500 mb-1">Events</div>
        <ul class="space-y-1 max-h-48 overflow-auto">
          <li
            v-for="ev in detail.events"
            :key="`${ev.aw_bucket_id}-${ev.aw_event_id}`"
            class="flex items-center justify-between gap-2 text-sm py-1 border-b border-slate-100 dark:border-slate-700/50"
          >
            <span class="truncate">
              {{ ev.event_data?.app ?? '?' }} — {{ ev.event_data?.title ?? '—' }}
            </span>
            <span class="text-slate-500 shrink-0">{{ formatDuration(ev.event_duration) }}</span>
            <button
              type="button"
              class="text-xs text-red-600 hover:underline shrink-0"
              @click.stop="removeEvent(ev.aw_bucket_id, ev.aw_event_id)"
            >
              Remove
            </button>
          </li>
        </ul>
      </template>
    </div>
  </div>
</template>
