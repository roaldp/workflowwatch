<script setup lang="ts">
import { watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useStreakStore } from '../stores/streak'
import { useTimelineStore } from '../stores/timeline'
import SwipeCard from './SwipeCard.vue'

const streak = useStreakStore()
const timeline = useTimelineStore()
const { date } = storeToRefs(timeline)
const {
  streakData,
  currentCard,
  nextCard,
  remainingCards,
  hasCards,
  totalUnlabeled,
  totalWithSuggestions,
  loading,
  processing,
  collapsed,
} = storeToRefs(streak)

async function refresh() {
  await Promise.all([
    streak.fetchStreakData(date.value),
    streak.fetchCards(date.value),
  ])
}

onMounted(refresh)
watch(date, refresh)

async function onAccept() {
  await streak.acceptCard(date.value)
  // Keep timeline in sync
  timeline.silentRefetch()
}

async function onDismiss() {
  await streak.dismissCard(date.value)
}
</script>

<template>
  <section
    v-if="streakData"
    class="rounded-lg border border-slate-700 bg-slate-900/40 p-3"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-sm font-medium text-slate-300">Daily Streak</h2>
      <button
        type="button"
        class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        @click="streak.toggleCollapsed()"
      >
        {{ collapsed ? 'Expand' : 'Collapse' }}
      </button>
    </div>

    <!-- Stats bar -->
    <div class="flex items-center gap-4 text-sm">
      <span v-if="streakData.current_streak > 0" class="text-amber-400 font-medium">
        {{ streakData.current_streak }} day streak
      </span>
      <span v-else class="text-slate-500">
        No active streak
      </span>
      <span class="text-slate-200 font-medium">
        {{ streakData.total_xp }} XP
      </span>
      <span v-if="streakData.today_xp > 0" class="text-emerald-400">
        +{{ streakData.today_xp }} today
      </span>
    </div>

    <!-- Card area (collapsible) -->
    <template v-if="!collapsed">
      <!-- Loading state -->
      <div v-if="loading" class="mt-3 text-xs text-slate-500">
        Loading cards...
      </div>

      <!-- Card stack + info -->
      <div v-else-if="hasCards" class="mt-3 flex items-start gap-4">
        <!-- Card stack -->
        <div class="relative" style="min-height: 200px; width: 320px;">
          <!-- Peek card (behind) -->
          <div
            v-if="nextCard"
            class="absolute inset-0 rounded-xl border border-slate-700 bg-slate-800/70 shadow"
            style="transform: translateY(6px) scale(0.97); z-index: 0; opacity: 0.6;"
          />

          <!-- Active card -->
          <div style="position: relative; z-index: 10;">
            <SwipeCard
              :card="currentCard!"
              :processing="processing"
              @accept="onAccept"
              @dismiss="onDismiss"
            />
          </div>
        </div>

        <!-- Side info -->
        <div class="flex flex-col gap-1 text-xs text-slate-500 pt-2">
          <span>{{ remainingCards }} card{{ remainingCards !== 1 ? 's' : '' }} remaining</span>
          <span>{{ totalUnlabeled }} unlabeled total</span>
          <span v-if="totalWithSuggestions > 0">
            {{ totalWithSuggestions }} with suggestions
          </span>
          <p class="mt-3 text-[11px] text-slate-600">
            Swipe right to accept<br />
            Swipe left to skip
          </p>
        </div>
      </div>

      <!-- Empty state: no cards -->
      <div v-else class="mt-2 text-xs text-slate-500">
        <span v-if="totalUnlabeled === 0">
          All events labeled for today. Nice work!
        </span>
        <span v-else>
          No suggestions available. Label events in the table below to train the pattern matcher.
        </span>
      </div>
    </template>
  </section>
</template>
