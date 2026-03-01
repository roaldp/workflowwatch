import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Workflow, WorkflowCreate, WorkflowUpdate } from '../types/workflow'

export const useWorkflowsStore = defineStore('workflows', () => {
  const workflows = ref<Workflow[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchWorkflows(includeArchived = false) {
    loading.value = true
    error.value = null
    try {
      const path = includeArchived ? '/api/v1/workflows?archived=true' : '/api/v1/workflows'
      workflows.value = await api.get<Workflow[]>(path)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch workflows'
      workflows.value = []
    } finally {
      loading.value = false
    }
  }

  async function createWorkflow(payload: WorkflowCreate) {
    error.value = null
    const w = await api.post<Workflow>('/api/v1/workflows', payload)
    await fetchWorkflows()
    return w
  }

  async function updateWorkflow(id: string, payload: WorkflowUpdate) {
    error.value = null
    const w = await api.put<Workflow>(`/api/v1/workflows/${id}`, payload)
    const i = workflows.value.findIndex((x) => x.id === id)
    if (i >= 0) workflows.value[i] = w
    return w
  }

  async function archiveWorkflow(id: string) {
    error.value = null
    await api.delete(`/api/v1/workflows/${id}`)
    workflows.value = workflows.value.filter((x) => x.id !== id)
  }

  return {
    workflows,
    loading,
    error,
    fetchWorkflows,
    createWorkflow,
    updateWorkflow,
    archiveWorkflow,
  }
})
