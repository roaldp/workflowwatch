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
const timeRange = computed(() =>
  `${formatTime(props.session.started_at)} – ${formatTime(props.session.ended_at)}`
)

async function toggleExpand() {
  if (expanded.value) { expanded.value = false; return }
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

async function confirmDelete() {
  if (!confirm('Delete this session? Events will become unlabeled.')) return
  await sessionsStore.deleteSession(props.session.id)
}

async function removeEvent(aw_bucket_id: string, aw_event_id: number) {
  await sessionsStore.removeEventsFromSession(props.session.id, [{ aw_bucket_id, aw_event_id }])
  detail.value = await sessionsStore.fetchSession(props.session.id)
  if (detail.value && detail.value.events.length === 0) {
    expanded.value = false
    detail.value = null
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800 overflow-hidden">
    <div
      class="flex flex-wrap items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-slate-700/50 transition-colors"
      @click="toggleExpand"
    >
      <span
        class="h-2.5 w-2.5 shrink-0 rounded-sm"
        :style="workflowColor ? { backgroundColor: workflowColor } : {}"
      />
      <span class="font-medium text-slate-200">{{ workflowName }}</span>
      <span v-if="session.title" class="text-slate-400 text-sm">— {{ session.title }}</span>
      <span class="text-slate-500 text-sm ml-auto">{{ timeRange }} · {{ durationFormatted }}</span>
      <span class="text-slate-600 text-xs">
        {{ expanded && detail ? detail.events.length : '…' }} events
      </span>
    </div>

    <div v-if="expanded" class="border-t border-slate-700 px-3 py-2.5">
      <div v-if="loadingDetail" class="text-sm text-slate-500">Loading…</div>
      <template v-else-if="detail">
        <div v-if="editing" class="space-y-2 mb-3">
          <input
            v-model="editTitle"
            type="text"
            placeholder="Title (optional)"
            class="w-full rounded-lg border border-slate-600 bg-slate-700 text-slate-200 placeholder-slate-500 px-2.5 py-1.5 text-sm focus:outline-none focus:border-indigo-500"
          />
          <textarea
            v-model="editNotes"
            placeholder="Notes (optional)"
            rows="2"
            class="w-full rounded-lg border border-slate-600 bg-slate-700 text-slate-200 placeholder-slate-500 px-2.5 py-1.5 text-sm focus:outline-none focus:border-indigo-500 resize-none"
          />
          <div class="flex gap-2">
            <button
              type="button"
              class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 text-sm text-white transition-colors"
              @click="saveEdit"
            >Save</button>
            <button
              type="button"
              class="rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 px-2.5 py-1 text-sm transition-colors"
              @click="editing = false"
            >Cancel</button>
          </div>
        </div>

        <div v-else class="flex gap-3 mb-3">
          <button
            type="button"
            class="text-sm text-slate-400 hover:text-slate-200 transition-colors"
            @click.stop="startEdit"
          >Edit</button>
          <button
            type="button"
            class="text-sm text-red-500 hover:text-red-400 transition-colors"
            @click.stop="confirmDelete"
          >Delete</button>
        </div>

        <p class="text-xs text-slate-500 mb-1.5 uppercase tracking-wide">Events</p>
        <ul class="space-y-1 max-h-48 overflow-auto">
          <li
            v-for="ev in detail.events"
            :key="`${ev.aw_bucket_id}-${ev.aw_event_id}`"
            class="flex items-center justify-between gap-2 text-sm py-1 border-b border-slate-700/50 last:border-0"
          >
            <span class="truncate text-slate-300">
              {{ ev.event_data?.app ?? '?' }} — {{ ev.event_data?.title ?? '—' }}
            </span>
            <span class="text-slate-500 shrink-0 text-xs">{{ formatDuration(ev.event_duration) }}</span>
            <button
              type="button"
              class="text-xs text-red-500 hover:text-red-400 shrink-0 transition-colors"
              @click.stop="removeEvent(ev.aw_bucket_id, ev.aw_event_id)"
            >Remove</button>
          </li>
        </ul>
      </template>
    </div>
  </div>
</template>
