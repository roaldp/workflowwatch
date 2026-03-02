<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow, WorkflowStats } from '../types/workflow'
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

// Composite breakdown panel
const statsWorkflow = ref<Workflow | null>(null)
const stats = ref<WorkflowStats | null>(null)
const statsLoading = ref(false)

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
    if (statsWorkflow.value?.id === w.id) statsWorkflow.value = null
  }
}

async function openStats(w: Workflow) {
  if (statsWorkflow.value?.id === w.id) {
    statsWorkflow.value = null
    return
  }
  statsWorkflow.value = w
  statsLoading.value = true
  stats.value = null
  try {
    stats.value = await store.fetchWorkflowStats(w.id)
  } finally {
    statsLoading.value = false
  }
}

function handleWorkflowClick(w: Workflow) {
  if (w.is_composite) {
    openStats(w)
  } else {
    emit('go-to-sessions', w.id)
  }
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
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
        >
          <div
            class="group flex items-center gap-2.5 rounded-md px-3 py-2 hover:bg-slate-700/60 cursor-pointer transition-colors"
            :class="statsWorkflow?.id === w.id ? 'bg-slate-700/40' : ''"
            @click="handleWorkflowClick(w)"
          >
            <!-- Color swatch: rotated (diamond) for composite, square for regular -->
            <span
              v-if="w.is_composite"
              class="w-2.5 h-2.5 shrink-0 rotate-45 rounded-sm"
              :style="{ backgroundColor: w.color ?? '#94a3b8' }"
              title="Composite process"
            />
            <span
              v-else
              class="w-2.5 h-2.5 rounded-sm shrink-0"
              :style="{ backgroundColor: w.color ?? '#94a3b8' }"
            />
            <!-- Name -->
            <span class="flex-1 text-sm text-slate-200 truncate">{{ w.name }}</span>
            <!-- Composite badge (hover-reveal) -->
            <span
              v-if="w.is_composite"
              class="shrink-0 text-[10px] text-slate-500 font-medium tracking-wide opacity-0 group-hover:opacity-100 transition-opacity"
            >
              process
            </span>
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
          </div>

          <!-- Inline breakdown panel for composite workflows -->
          <div
            v-if="w.is_composite && statsWorkflow?.id === w.id"
            class="mx-2 mb-1 rounded-md bg-slate-800/60 border border-slate-700/50 px-3 py-2.5 text-xs"
          >
            <div v-if="statsLoading" class="text-slate-500">Loading…</div>
            <div v-else-if="stats && stats.breakdown.length > 0">
              <p class="text-slate-400 mb-2">
                {{ formatDuration(stats.total_duration) }} across
                {{ stats.session_count }} session{{ stats.session_count !== 1 ? 's' : '' }}
              </p>
              <!-- Stacked bar -->
              <div class="flex h-2 rounded-full overflow-hidden mb-2.5">
                <div
                  v-for="item in stats.breakdown"
                  :key="item.child_id"
                  :style="{ width: (item.actual_pct * 100) + '%', backgroundColor: item.child_color ?? '#94a3b8' }"
                  :title="`${item.child_name}: ${Math.round(item.actual_pct * 100)}%`"
                />
              </div>
              <!-- Breakdown rows -->
              <div
                v-for="item in stats.breakdown"
                :key="item.child_id"
                class="flex items-center gap-2 py-0.5"
              >
                <span
                  class="w-2 h-2 rounded-sm shrink-0"
                  :style="{ backgroundColor: item.child_color ?? '#94a3b8' }"
                />
                <span class="flex-1 text-slate-300 truncate">{{ item.child_name }}</span>
                <span class="text-slate-400 shrink-0">{{ Math.round(item.actual_pct * 100) }}%</span>
                <span
                  v-if="item.typical_pct != null"
                  class="text-slate-600 shrink-0"
                  :title="`Target: ${Math.round(item.typical_pct * 100)}%`"
                >
                  ({{ Math.round(item.typical_pct * 100) }}% target)
                </span>
              </div>
            </div>
            <div v-else class="text-slate-600">
              No sessions linked yet.<br>
              Label time and assign sessions to this process.
            </div>
          </div>
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
