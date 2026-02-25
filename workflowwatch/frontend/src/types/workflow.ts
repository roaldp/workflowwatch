export interface Workflow {
  id: string
  name: string
  description: string | null
  color: string | null
  created_at: string
  updated_at: string
  archived: boolean
}

export interface WorkflowCreate {
  name: string
  description?: string | null
  color?: string | null
}

export interface WorkflowUpdate {
  name?: string | null
  description?: string | null
  color?: string | null
}
