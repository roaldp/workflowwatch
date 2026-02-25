<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow } from '../types/workflow'
import WorkflowColorDot from './WorkflowColorDot.vue'
import WorkflowModal from './WorkflowModal.vue'

const store = useWorkflowsStore()
const modalVisible = ref(false)
const editingWorkflow = ref<Workflow | null>(null)

onMounted(() => {
  store.fetchWorkflows()
})

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
  <aside class="w-56 shrink-0 border-r border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 flex flex-col min-h-0">
    <div class="p-3 border-b border-slate-200 dark:border-slate-700">
      <h2 class="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">
        Workflows
      </h2>
    </div>
    <div class="flex-1 overflow-auto p-2">
      <p v-if="store.loading" class="text-sm text-slate-500 py-2">Loading…</p>
      <p v-else-if="store.error" class="text-sm text-red-600 py-2">{{ store.error }}</p>
      <ul v-else class="space-y-0.5">
        <li
          v-for="w in store.workflows"
          :key="w.id"
          class="group flex items-center gap-2 rounded px-2 py-1.5 hover:bg-slate-200/60 dark:hover:bg-slate-700/60"
        >
          <WorkflowColorDot :color="w.color" />
          <button
            type="button"
            class="flex-1 text-left text-sm truncate min-w-0"
            @click="openEdit(w)"
          >
            {{ w.name }}
          </button>
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-600 text-xs px-1"
            title="Archive"
            @click="archive(w)"
          >
            Archive
          </button>
        </li>
      </ul>
    </div>
    <div class="p-2 border-t border-slate-200 dark:border-slate-700">
      <button
        type="button"
        class="w-full rounded border border-dashed border-slate-300 dark:border-slate-600 py-2 text-sm text-slate-600 dark:text-slate-400 hover:border-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        @click="openCreate"
      >
        + New workflow
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
