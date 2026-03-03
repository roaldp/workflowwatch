import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/client'
import type { StreakData, SwipeCard, SwipeCardQueue } from '../types/streak'

export const useStreakStore = defineStore('streak', () => {
  const streakData = ref<StreakData | null>(null)
  const cards = ref<SwipeCard[]>([])
  const totalUnlabeled = ref(0)
  const totalWithSuggestions = ref(0)
  const loading = ref(false)
  const processing = ref(false)
  const collapsed = ref(false)

  const currentCard = computed(() => cards.value[0] ?? null)
  const nextCard = computed(() => cards.value[1] ?? null)
  const remainingCards = computed(() => cards.value.length)
  const hasCards = computed(() => cards.value.length > 0)

  async function fetchStreakData(date: string) {
    try {
      streakData.value = await api.get<StreakData>(`/api/v1/streak?date=${date}`)
    } catch {
      // Keep previous state on error
    }
  }

  async function fetchCards(date: string) {
    loading.value = true
    try {
      const queue = await api.get<SwipeCardQueue>(`/api/v1/streak/cards?date=${date}`)
      cards.value = queue.cards
      totalUnlabeled.value = queue.total_unlabeled
      totalWithSuggestions.value = queue.total_with_suggestions
    } catch {
      cards.value = []
    } finally {
      loading.value = false
    }
  }

  async function acceptCard(date: string) {
    const card = currentCard.value
    if (!card || processing.value) return

    processing.value = true
    try {
      await api.post('/api/v1/streak/accept', {
        date,
        aw_bucket_id: card.aw_bucket_id,
        aw_event_id: card.aw_event_id,
        workflow_id: card.suggested_workflow_id,
      })

      // Remove accepted card from queue
      cards.value = cards.value.slice(1)

      // Optimistically update streak data
      if (streakData.value) {
        streakData.value = {
          ...streakData.value,
          total_xp: streakData.value.total_xp + 1,
          today_xp: streakData.value.today_xp + 1,
          current_streak: streakData.value.current_streak || 1,
        }
      }
    } finally {
      processing.value = false
    }
  }

  async function dismissCard(date: string) {
    const card = currentCard.value
    if (!card || processing.value) return

    processing.value = true
    try {
      await api.post('/api/v1/streak/dismiss', {
        date,
        aw_bucket_id: card.aw_bucket_id,
        aw_event_id: card.aw_event_id,
        workflow_id: card.suggested_workflow_id,
      })

      // Remove dismissed card from queue
      cards.value = cards.value.slice(1)
    } finally {
      processing.value = false
    }
  }

  function toggleCollapsed() {
    collapsed.value = !collapsed.value
  }

  return {
    streakData,
    cards,
    totalUnlabeled,
    totalWithSuggestions,
    loading,
    processing,
    collapsed,
    currentCard,
    nextCard,
    remainingCards,
    hasCards,
    fetchStreakData,
    fetchCards,
    acceptCard,
    dismissCard,
    toggleCollapsed,
  }
})
