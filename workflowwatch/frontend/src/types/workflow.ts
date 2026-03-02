export interface WorkflowCompositionStep {
  child_id: string
  child_name: string
  child_color: string | null
  typical_pct: number | null  // 0.0–1.0, advisory
  display_order: number
}

export interface WorkflowCompositionStepInput {
  child_id: string
  typical_pct?: number | null
  display_order?: number
}

export interface Workflow {
  id: string
  name: string
  description: string | null
  color: string | null
  is_composite: boolean
  composition: WorkflowCompositionStep[]
  created_at: string
  updated_at: string
  archived: boolean
}

export interface WorkflowCreate {
  name: string
  description?: string | null
  color?: string | null
  is_composite?: boolean
  composition?: WorkflowCompositionStepInput[]
}

export interface WorkflowUpdate {
  name?: string | null
  description?: string | null
  color?: string | null
  composition?: WorkflowCompositionStepInput[] | null  // null = no change, [] = clear
}

export interface WorkflowBreakdownItem {
  child_id: string
  child_name: string
  child_color: string | null
  actual_duration: number   // seconds
  actual_pct: number        // 0.0–1.0
  typical_pct: number | null
  session_count: number
}

export interface WorkflowStats {
  workflow_id: string
  total_duration: number
  session_count: number
  breakdown: WorkflowBreakdownItem[]
}
