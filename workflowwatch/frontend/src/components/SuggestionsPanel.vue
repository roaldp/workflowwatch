<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useTimelineStore } from '../stores/timeline'
import { useWorkflowsStore } from '../stores/workflows'
import { api } from '../api/client'
import type { Suggestion, SessionCreate } from '../types/session'
import type { TimelineEvent } from '../types/timeline'
import { eventKey } from '../types/session'

onMounted(() => workflowsStore.fetchWorkflows())

const timeline = useTimelineStore()
const workflowsStore = useWorkflowsStore()
const { date, events, suggestions, suggestionsLoading, suggestionPreview } = storeToRefs(timeline)

function workflowName(id: string) {
  return workflowsStore.workflows.find((w) => w.id === id)?.name ?? id
}
function workflowColor(id: string) {
  return workflowsStore.workflows.find((w) => w.id === id)?.color ?? null
}

function suggestionEventKeys(s: Suggestion) {
  return new Set(s.event_refs.map((r) => eventKey(r.aw_bucket_id, r.aw_event_id)))
}

function isPreviewed(s: Suggestion) {
  const current = suggestionPreview.value
  if (!current || current.workflow_id !== s.workflow_id) return false
  const keys = suggestionEventKeys(s)
  if (keys.size !== current.event_keys.size) return false
  for (const k of keys) if (!current.event_keys.has(k)) return false
  return true
}

function togglePreview(s: Suggestion) {
  if (isPreviewed(s)) {
    timeline.clearSuggestionPreview()
    return
  }
  timeline.previewSuggestion(s, workflowName(s.workflow_id))
}

const MAX_VISIBLE_INDICATORS = 4
function visibleIndicators(s: Suggestion) {
  return (s.matched_indicators ?? []).slice(0, MAX_VISIBLE_INDICATORS)
}
function hiddenIndicatorsCount(s: Suggestion) {
  return Math.max(0, (s.matched_indicators?.length ?? 0) - MAX_VISIBLE_INDICATORS)
}

type PatternConfidence = 'low' | 'medium' | 'high'
const MEDIUM_CONFIDENCE_MIN_SCORE = 4
const HIGH_CONFIDENCE_MIN_SCORE = 6
const APPLY_CONFIDENCE_MIN_SCORE = HIGH_CONFIDENCE_MIN_SCORE
const CONFIDENCE_SCORE_TARGET = 6

function confidenceFromScore(score: number): PatternConfidence {
  if (score >= HIGH_CONFIDENCE_MIN_SCORE) return 'high'
  if (score >= MEDIUM_CONFIDENCE_MIN_SCORE) return 'medium'
  return 'low'
}

function confidenceClass(score: number) {
  const confidence = confidenceFromScore(score)
  if (confidence === 'high') return 'text-emerald-300'
  if (confidence === 'medium') return 'text-amber-300'
  return 'text-slate-500'
}

function confidenceLabel(score: number) {
  const confidence = confidenceFromScore(score)
  if (confidence === 'high') return 'High confidence'
  if (confidence === 'medium') return 'Building confidence'
  return 'Learning'
}

function canApplySuggestion(s: Suggestion) {
  return s.score >= APPLY_CONFIDENCE_MIN_SCORE
}

function confidenceProgress(score: number) {
  return Math.min(100, Math.round((score / CONFIDENCE_SCORE_TARGET) * 100))
}

const highConfidenceSuggestions = computed(() =>
  suggestions.value.filter((s) => s.score >= HIGH_CONFIDENCE_MIN_SCORE)
)

function parseErrorDetail(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as { detail?: string }
    return parsed?.detail ?? raw
  } catch {
    return raw
  }
}

function parseAlreadyLabeledKeys(raw: string): Set<string> {
  const detail = parseErrorDetail(raw)
  if (!detail.includes('already labeled')) return new Set()
  const matches = detail.match(/([^\s,'"\]]+:\d+)/g) ?? []
  return new Set(matches)
}

function refsForUnlabeledEvents(refs: Suggestion['event_refs']) {
  const unlabeled = new Set(
    events.value
      .filter((e) => !e.session_id)
      .map((e) => eventKey(e.aw_bucket_id, e.aw_event_id))
  )
  return refs.filter((r) => unlabeled.has(eventKey(r.aw_bucket_id, r.aw_event_id)))
}

function optimisticallyLabelPatternRefs(
  refs: Suggestion['event_refs'],
  workflowId: string,
) {
  const name = workflowName(workflowId)
  const color = workflowColor(workflowId)
  const byKey = new Map<string, TimelineEvent>()
  for (const e of events.value) {
    byKey.set(eventKey(e.aw_bucket_id, e.aw_event_id), e)
  }
  for (const ref of refs) {
    const key = eventKey(ref.aw_bucket_id, ref.aw_event_id)
    const ev = byKey.get(key)
    if (!ev || ev.session_id) continue
    timeline.optimisticallyLabelEvent(ev, workflowId, name, color)
  }
}

const applying = ref(false)
const applyError = ref<string | null>(null)
async function applySuggestion(s: Suggestion) {
  if (!canApplySuggestion(s)) return
  applying.value = true
  applyError.value = null
  try {
    let refsToApply = refsForUnlabeledEvents(s.event_refs)
    if (refsToApply.length === 0) {
      await timeline.silentRefetch()
      return
    }
    optimisticallyLabelPatternRefs(refsToApply, s.workflow_id)
    const firstBody: SessionCreate = {
      workflow_id: s.workflow_id,
      date: date.value,
      events: refsToApply,
    }
    try {
      await api.post('/api/v1/sessions', firstBody)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      const conflicting = parseAlreadyLabeledKeys(message)
      if (conflicting.size === 0) throw err
      refsToApply = refsToApply.filter(
        (r) => !conflicting.has(eventKey(r.aw_bucket_id, r.aw_event_id))
      )
      if (refsToApply.length === 0) {
        await timeline.silentRefetch()
        return
      }
      await api.post('/api/v1/sessions', {
        workflow_id: s.workflow_id,
        date: date.value,
        events: refsToApply,
      } satisfies SessionCreate)
    }
    if (!isPreviewed(s)) {
      timeline.previewSuggestion({ ...s, event_refs: refsToApply }, workflowName(s.workflow_id))
    }
    timeline.markPatternApplied(refsToApply)
    await timeline.silentRefetch()
    await timeline.fetchSuggestions()
  } catch (err) {
    applyError.value = parseErrorDetail(err instanceof Error ? err.message : String(err))
    await timeline.silentRefetch()
  } finally {
    applying.value = false
  }
}

const declining = ref(false)
async function declineSuggestion(s: Suggestion) {
  declining.value = true
  try {
    await api.post('/api/v1/suggestions/dismiss', {
      date: date.value,
      dismissals: [
        {
          workflow_id: s.workflow_id,
          event_refs: s.event_refs,
        },
      ],
    })
    if (isPreviewed(s)) timeline.clearSuggestionPreview()
    await timeline.fetchSuggestions()
  } finally {
    declining.value = false
  }
}
</script>

<template>
  <section v-if="suggestionsLoading" class="text-sm text-slate-500">
    Loading suggestions…
  </section>
  <section
    v-else-if="suggestions.length > 0 && highConfidenceSuggestions.length === 0"
    class="rounded-lg border border-slate-700 bg-slate-900/40 p-3"
  >
    <h2 class="text-sm font-medium text-slate-300 mb-1">Pattern-matched suggestions</h2>
    <p class="text-xs text-slate-500">
      No high-confidence pattern matches yet. Keep labeling events in-line to build confidence.
    </p>
  </section>
  <section
    v-else-if="highConfidenceSuggestions.length > 0"
    class="rounded-lg border border-amber-800/40 bg-amber-950/20 p-3"
  >
    <h2 class="text-sm font-medium text-amber-400 mb-1">Pattern-matched suggestions</h2>
    <p class="text-xs text-slate-500 mb-2">
      Game loop: label single events in the table, watch pattern confidence grow, then apply a confident match in bulk.
    </p>
    <p v-if="applyError" class="mb-2 text-xs text-red-300">
      Apply failed: {{ applyError }}
    </p>
    <ul class="space-y-2">
      <li
        v-for="(s, i) in highConfidenceSuggestions"
        :key="i"
        class="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 transition-all"
        :class="timeline.hasRecentPatternContribution(s.workflow_id)
          ? 'ring-1 ring-indigo-500/50 bg-indigo-950/20'
          : ''"
      >
        <div class="flex flex-wrap items-start gap-2">
          <span
            class="h-2.5 w-2.5 shrink-0 rounded-sm mt-1"
            :style="workflowColor(s.workflow_id) ? { backgroundColor: workflowColor(s.workflow_id)! } : {}"
          />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="font-medium text-slate-200">{{ workflowName(s.workflow_id) }}</span>
              <span class="text-xs text-slate-500">{{ s.event_refs.length }} affected events</span>
              <span class="text-xs text-slate-500">{{ s.score }} matching indicators</span>
              <span class="text-xs font-medium" :class="confidenceClass(s.score)">
                {{ confidenceLabel(s.score) }}
              </span>
              <span
                v-if="timeline.hasRecentPatternContribution(s.workflow_id)"
                class="text-[11px] rounded border border-indigo-500/40 bg-indigo-500/10 px-1.5 py-0.5 text-indigo-300"
              >
                Progress updated from recent label
              </span>
            </div>
            <div class="mt-1">
              <div class="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                <span>Confidence progress</span>
                <span>{{ s.score }} / {{ CONFIDENCE_SCORE_TARGET }} indicators</span>
              </div>
              <div class="h-1.5 rounded-full bg-slate-800 border border-slate-700 overflow-hidden">
                <div
                  class="h-full transition-all duration-300"
                  :class="confidenceFromScore(s.score) === 'high'
                    ? 'bg-emerald-500'
                    : confidenceFromScore(s.score) === 'medium'
                      ? 'bg-amber-500'
                      : 'bg-slate-600'"
                  :style="{ width: `${confidenceProgress(s.score)}%` }"
                />
              </div>
            </div>
            <div v-if="s.matched_indicators?.length" class="mt-1 flex flex-wrap gap-1">
              <span
                v-for="indicator in visibleIndicators(s)"
                :key="indicator"
                class="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[11px] text-slate-400"
              >
                {{ indicator }}
              </span>
              <span
                v-if="hiddenIndicatorsCount(s) > 0"
                class="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[11px] text-slate-500"
              >
                +{{ hiddenIndicatorsCount(s) }} more
              </span>
            </div>
          </div>
          <button
            type="button"
            class="rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors"
            :class="isPreviewed(s)
              ? 'border-amber-500/70 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25'
              : 'border-slate-600 text-slate-300 hover:bg-slate-700'"
            @click="togglePreview(s)"
          >
            {{ isPreviewed(s) ? 'Previewing in Events' : 'Preview in Events' }}
          </button>
          <button
            type="button"
            class="rounded-lg border border-slate-600 text-slate-300 hover:border-red-700 hover:text-red-300 px-2.5 py-1 text-xs font-medium disabled:opacity-50 transition-colors"
            :disabled="applying || declining"
            @click="declineSuggestion(s)"
          >
            Decline
          </button>
          <button
            type="button"
            class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50 transition-colors"
            :disabled="applying || declining || !canApplySuggestion(s)"
            :title="canApplySuggestion(s)
              ? 'Apply this confident pattern match'
              : `Need ${APPLY_CONFIDENCE_MIN_SCORE}+ indicators before bulk apply`"
            @click="applySuggestion(s)"
          >
            Apply
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>
