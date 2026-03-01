<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'

const store = useTimelineStore()
const { autoLabelsByWorkflow, acceptingAutoLabels } = storeToRefs(store)

// Build a compact preview: unique apps per group
function groupPreview(events: typeof autoLabelsByWorkflow.value[number]['events']) {
  const appsSeen = new Set<string>()
  const apps: string[] = []
  for (const e of events) {
    const app = e.data?.app
    if (app && !appsSeen.has(app)) {
      appsSeen.add(app)
      apps.push(app)
    }
    if (apps.length >= 4) break
  }
  return { apps, more: appsSeen.size < events.length ? events.length - appsSeen.size : 0 }
}

// JS transition hooks for smooth height collapse (avoids abrupt layout shifts)
function onBeforeLeave(el: Element) {
  const h = (el as HTMLElement)
  h.style.height = h.offsetHeight + 'px'
  h.style.overflow = 'hidden'
}
function onLeave(el: Element, done: () => void) {
  const h = el as HTMLElement
  requestAnimationFrame(() => {
    h.style.transition = 'height 0.22s ease, opacity 0.18s ease, margin-bottom 0.22s ease'
    h.style.height = '0'
    h.style.opacity = '0'
    h.style.marginBottom = '0'
    h.addEventListener('transitionend', done, { once: true })
  })
}
function onAfterLeave(el: Element) {
  const h = el as HTMLElement
  h.style.height = ''
  h.style.overflow = ''
  h.style.opacity = ''
  h.style.transition = ''
  h.style.marginBottom = ''
}
function onEnter(el: Element, done: () => void) {
  const h = el as HTMLElement
  const targetHeight = h.scrollHeight
  h.style.height = '0'
  h.style.opacity = '0'
  h.style.overflow = 'hidden'
  requestAnimationFrame(() => {
    h.style.transition = 'height 0.22s ease, opacity 0.18s ease'
    h.style.height = targetHeight + 'px'
    h.style.opacity = '1'
    h.addEventListener('transitionend', () => {
      h.style.height = ''
      h.style.overflow = ''
      h.style.transition = ''
      done()
    }, { once: true })
  })
}
</script>

<template>
  <Transition
    @before-leave="onBeforeLeave"
    @leave="onLeave"
    @after-leave="onAfterLeave"
    @enter="onEnter"
  >
    <section
      v-if="autoLabelsByWorkflow.length > 0"
      class="rounded-lg border border-indigo-800/40 bg-indigo-950/20 px-3 py-2.5 space-y-2"
    >
      <p class="text-xs font-semibold uppercase tracking-widest text-indigo-400">
        Auto-label suggestions
      </p>

      <div
        v-for="group in autoLabelsByWorkflow"
        :key="group.id"
        class="flex flex-wrap items-start gap-x-2 gap-y-1.5"
      >
        <!-- Workflow identity + counts -->
        <div class="flex items-center gap-2 min-w-0">
          <span
            class="h-2.5 w-2.5 rounded-sm shrink-0 mt-0.5"
            :style="group.color ? { backgroundColor: group.color } : {}"
          />
          <span class="text-sm text-slate-200 font-medium">{{ group.name }}</span>
          <span class="text-xs text-slate-500 whitespace-nowrap">
            {{ group.events.length }} event{{ group.events.length !== 1 ? 's' : '' }}
            <template v-if="group.highCount > 0">· {{ group.highCount }} high-confidence</template>
          </span>
        </div>

        <!-- App name chips showing what's being proposed -->
        <div class="flex flex-wrap items-center gap-1 flex-1 min-w-0">
          <span
            v-for="app in groupPreview(group.events).apps"
            :key="app"
            class="rounded px-1.5 py-0.5 text-xs bg-slate-800 text-slate-400 border border-slate-700/60"
          >
            {{ app }}
          </span>
          <span
            v-if="groupPreview(group.events).more > 0"
            class="text-xs text-slate-600"
          >
            +{{ groupPreview(group.events).more }} more
          </span>
        </div>

        <!-- Per-workflow actions -->
        <div class="ml-auto flex items-center gap-2 shrink-0">
          <button
            type="button"
            class="rounded-md bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50 transition-colors"
            :disabled="acceptingAutoLabels"
            @click="store.acceptAllForWorkflow(group.id)"
          >
            <span v-if="acceptingAutoLabels">…</span>
            <span v-else>Accept all</span>
          </button>
          <button
            type="button"
            class="rounded-md border border-slate-700 text-slate-500 hover:text-red-400 hover:border-red-800 px-2.5 py-1 text-xs transition-colors"
            :disabled="acceptingAutoLabels"
            @click="store.dismissAllForWorkflow(group.id)"
          >
            Reject all
          </button>
        </div>
      </div>
    </section>
  </Transition>
</template>
