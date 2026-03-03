export interface StreakData {
  date: string
  total_xp: number
  today_xp: number
  current_streak: number
}

export interface SwipeCard {
  aw_bucket_id: string
  aw_event_id: number
  timestamp: string
  duration: number
  data: { app?: string; title?: string; [k: string]: unknown }
  suggested_workflow_id: string
  suggested_workflow_name: string | null
  suggested_workflow_color: string | null
  suggestion_confidence: 'high' | 'medium'
  suggestion_source: 'cache' | 'embedding' | 'rule'
}

export interface SwipeCardQueue {
  date: string
  cards: SwipeCard[]
  total_unlabeled: number
  total_with_suggestions: number
}
