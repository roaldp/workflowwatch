<script setup lang="ts">
import { ref, computed } from 'vue'
import type { SwipeCard } from '../types/streak'

const props = defineProps<{
  card: SwipeCard
  processing: boolean
}>()

const emit = defineEmits<{
  accept: []
  dismiss: []
}>()

// Swipe gesture state
const dragging = ref(false)
const deltaX = ref(0)
const startX = ref(0)
const animatingOut = ref<'left' | 'right' | null>(null)

const SWIPE_THRESHOLD = 100
const HINT_THRESHOLD = 50

const cardStyle = computed(() => {
  if (animatingOut.value) {
    const x = animatingOut.value === 'right' ? 400 : -400
    return {
      transform: `translateX(${x}px) rotate(${x * 0.03}deg)`,
      transition: 'transform 200ms ease-out, opacity 200ms ease-out',
      opacity: '0',
    }
  }
  if (!dragging.value) return {}
  return {
    transform: `translateX(${deltaX.value}px) rotate(${deltaX.value * 0.03}deg)`,
    transition: 'none',
  }
})

const showAcceptHint = computed(() => deltaX.value > HINT_THRESHOLD)
const showDismissHint = computed(() => deltaX.value < -HINT_THRESHOLD)

function onPointerDown(e: PointerEvent) {
  if (props.processing || animatingOut.value) return
  dragging.value = true
  startX.value = e.clientX
  deltaX.value = 0
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  deltaX.value = e.clientX - startX.value
}

function onPointerUp() {
  if (!dragging.value) return
  dragging.value = false

  if (deltaX.value > SWIPE_THRESHOLD) {
    animateOut('right')
  } else if (deltaX.value < -SWIPE_THRESHOLD) {
    animateOut('left')
  } else {
    deltaX.value = 0
  }
}

function animateOut(direction: 'left' | 'right') {
  animatingOut.value = direction
  setTimeout(() => {
    animatingOut.value = null
    deltaX.value = 0
    if (direction === 'right') emit('accept')
    else emit('dismiss')
  }, 200)
}

function onAcceptClick() {
  if (props.processing || animatingOut.value) return
  animateOut('right')
}

function onDismissClick() {
  if (props.processing || animatingOut.value) return
  animateOut('left')
}

function onKeyDown(e: KeyboardEvent) {
  if (props.processing || animatingOut.value) return
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    animateOut('right')
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    animateOut('left')
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function appInitial(app: string | undefined): string {
  if (!app) return '?'
  return app.charAt(0).toUpperCase()
}
</script>

<template>
  <div
    class="relative w-full max-w-sm select-none touch-none cursor-grab active:cursor-grabbing"
    :style="cardStyle"
    tabindex="0"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @keydown="onKeyDown"
  >
    <!-- Accept overlay hint -->
    <div
      class="absolute inset-0 rounded-xl border-2 border-emerald-500 bg-emerald-500/10 flex items-center justify-center z-10 pointer-events-none transition-opacity duration-100"
      :class="showAcceptHint ? 'opacity-100' : 'opacity-0'"
    >
      <span class="text-emerald-400 font-bold text-lg tracking-wide">ACCEPT</span>
    </div>

    <!-- Dismiss overlay hint -->
    <div
      class="absolute inset-0 rounded-xl border-2 border-red-500 bg-red-500/10 flex items-center justify-center z-10 pointer-events-none transition-opacity duration-100"
      :class="showDismissHint ? 'opacity-100' : 'opacity-0'"
    >
      <span class="text-red-400 font-bold text-lg tracking-wide">SKIP</span>
    </div>

    <!-- Card body -->
    <div class="rounded-xl border border-slate-700 bg-slate-800 shadow-lg p-4 space-y-3">
      <!-- App + title -->
      <div class="flex items-start gap-3">
        <div
          class="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white"
          :style="{ backgroundColor: card.suggested_workflow_color ?? '#6366f1' }"
        >
          {{ appInitial(card.data.app) }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-slate-200 truncate">{{ card.data.app ?? 'Unknown' }}</p>
          <p class="text-xs text-slate-400 truncate">{{ card.data.title ?? 'Untitled' }}</p>
        </div>
      </div>

      <!-- Time + duration -->
      <div class="flex items-center gap-3 text-xs text-slate-500">
        <span>{{ formatTime(card.timestamp) }}</span>
        <span class="text-slate-700">&middot;</span>
        <span>{{ formatDuration(card.duration) }}</span>
      </div>

      <!-- Suggested workflow -->
      <div class="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2">
        <span
          class="h-2.5 w-2.5 shrink-0 rounded-sm"
          :style="card.suggested_workflow_color ? { backgroundColor: card.suggested_workflow_color } : {}"
        />
        <span class="text-sm font-medium text-slate-200">{{ card.suggested_workflow_name ?? 'Unknown' }}</span>
        <span
          class="ml-auto rounded border px-1.5 py-0.5 text-[11px] font-medium"
          :class="card.suggestion_confidence === 'high'
            ? 'border-emerald-700 bg-emerald-900/30 text-emerald-300'
            : 'border-amber-700 bg-amber-900/30 text-amber-300'"
        >
          {{ card.suggestion_confidence === 'high' ? 'High' : 'Medium' }}
        </span>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-2 pt-1">
        <button
          type="button"
          class="flex-1 rounded-lg border border-slate-600 py-1.5 text-sm font-medium text-slate-300 hover:border-red-700 hover:text-red-300 transition-colors disabled:opacity-50"
          :disabled="processing"
          @click.stop="onDismissClick"
        >
          Skip
        </button>
        <button
          type="button"
          class="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 py-1.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
          :disabled="processing"
          @click.stop="onAcceptClick"
        >
          Accept
        </button>
      </div>
    </div>
  </div>
</template>
