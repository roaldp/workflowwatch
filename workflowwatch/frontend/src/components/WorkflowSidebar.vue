<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow } from '../types/workflow'
import WorkflowModal from './WorkflowModal.vue'
import { api } from '../api/client'

const emit = defineEmits<{
  (e: 'go-to-sessions', workflowId: string): void
}>()

interface LabelRule {
  id: string
  workflow_id: string
  rule_type: string
  match_value: string
  workflow_name: string
  workflow_color: string | null
}

const store = useWorkflowsStore()
const modalVisible = ref(false)
const editingWorkflow = ref<Workflow | null>(null)
const rules = ref<LabelRule[]>([])
const rulesOpen = ref(false)

onMounted(async () => {
  await store.fetchWorkflows()
  await fetchRules()
})

async function fetchRules() {
  try {
    rules.value = await api.get<LabelRule[]>('/api/v1/label-rules')
  } catch {
    rules.value = []
  }
}

async function deleteRule(id: string) {
  await api.delete(`/api/v1/label-rules/${id}`)
  rules.value = rules.value.filter((r) => r.id !== id)
}

function openCreate() {
  editingWorkflow.value = null
  modalVisible.value = true
}

function openEdit(w: Workflow) {
  editingWorkflow.value = w
  modalVisible.value = true
}

function closeModal() {
  modalVisible.value = false
  editingWorkflow.value = null
}

async function archive(w: Workflow) {
  if (confirm(`Archive "${w.name}"? It will be hidden from the list.`)) {
    await store.archiveWorkflow(w.id)
  }
}
</script>

<template>
  <aside class="w-60 shrink-0 flex flex-col min-h-0 bg-slate-900 text-slate-100">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-slate-700/60">
      <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">
        Workflows
      </span>
    </div>

    <!-- Workflow list -->
    <div class="flex-1 overflow-auto py-2">
      <p v-if="store.loading" class="px-4 py-3 text-sm text-slate-500">Loading…</p>
      <p v-else-if="store.error" class="px-4 py-3 text-sm text-red-400">{{ store.error }}</p>

      <!-- Empty state -->
      <div
        v-else-if="store.workflows.length === 0"
        class="px-4 py-6 text-center"
      >
        <p class="text-sm text-slate-400 mb-1">No workflows yet</p>
        <p class="text-xs text-slate-500">Create one to start labeling your time</p>
      </div>

      <ul v-else class="space-y-px px-2">
        <li
          v-for="w in store.workflows"
          :key="w.id"
          class="group flex items-center gap-2.5 rounded-md px-3 py-2 hover:bg-slate-700/60 cursor-pointer transition-colors"
          @click="emit('go-to-sessions', w.id)"
        >
          <!-- Color swatch -->
          <span
            class="w-2.5 h-2.5 rounded-sm shrink-0"
            :style="{ backgroundColor: w.color ?? '#94a3b8' }"
          />
          <!-- Name -->
          <span class="flex-1 text-sm text-slate-200 truncate">{{ w.name }}</span>
          <!-- Edit button -->
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-xs text-slate-500 hover:text-slate-200 transition-opacity px-1"
            title="Edit workflow"
            @click.stop="openEdit(w)"
          >
            ✎
          </button>
          <!-- Archive button -->
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-xs text-slate-500 hover:text-red-400 transition-opacity px-1"
            title="Archive workflow"
            @click.stop="archive(w)"
          >
            ✕
          </button>
        </li>
      </ul>

      <!-- Rules section -->
      <div class="mt-3 px-2">
        <button
          type="button"
          class="w-full flex items-center justify-between px-3 py-1.5 rounded-md text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 transition-colors"
          @click="rulesOpen = !rulesOpen"
        >
          <span class="font-medium uppercase tracking-widest">Rules</span>
          <span>{{ rulesOpen ? '▾' : '▸' }}</span>
        </button>
        <ul v-if="rulesOpen" class="mt-1 space-y-1">
          <li
            v-for="rule in rules"
            :key="rule.id"
            class="group flex items-center gap-2 rounded-md px-3 py-1.5 hover:bg-slate-800/60"
          >
            <span
              class="w-2 h-2 rounded-sm shrink-0"
              :style="rule.workflow_color ? { backgroundColor: rule.workflow_color } : {}"
            />
            <span class="flex-1 text-xs text-slate-400 truncate">
              <span class="text-slate-300">{{ rule.match_value }}</span>
              <span class="text-slate-600"> → {{ rule.workflow_name }}</span>
            </span>
            <button
              type="button"
              class="opacity-0 group-hover:opacity-100 text-xs text-slate-600 hover:text-red-400 transition-opacity"
              title="Delete rule"
              @click="deleteRule(rule.id)"
            >
              ✕
            </button>
          </li>
          <li v-if="rules.length === 0" class="px-3 py-1 text-xs text-slate-600">
            No rules yet
          </li>
        </ul>
      </div>
    </div>

    <!-- New workflow button -->
    <div class="p-3 border-t border-slate-700/60">
      <button
        type="button"
        class="w-full flex items-center justify-center gap-2 rounded-md bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 py-2.5 text-sm font-medium text-white transition-colors"
        @click="openCreate"
      >
        <span class="text-lg leading-none">+</span>
        New workflow
      </button>
    </div>
  </aside>

  <WorkflowModal
    :visible="modalVisible"
    :workflow="editingWorkflow"
    @close="closeModal"
    @saved="closeModal"
  />
</template>
