<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow, WorkflowCompositionStepInput } from '../types/workflow'

const PRESET_COLORS = [
  '#6366F1', '#3B82F6', '#10B981', '#F59E0B',
  '#EF4444', '#8B5CF6', '#EC4899', '#94A3B8',
]

interface StepDraft {
  child_id: string
  typical_pct: string  // string for input binding, convert to number on save
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    workflow: Workflow | null
  }>(),
  { workflow: null }
)

const emit = defineEmits<{
  close: []
  saved: []
}>()

const name = ref('')
const description = ref('')
const color = ref(PRESET_COLORS[0])
const isComposite = ref(false)
const steps = ref<StepDraft[]>([])
const submitting = ref(false)
const error = ref('')

const store = useWorkflowsStore()

// Available child workflow options: non-archived, non-composite, not the workflow being edited
const childOptions = computed(() =>
  store.workflows.filter(
    (w) => !w.archived && !w.is_composite && w.id !== props.workflow?.id
  )
)

// Child IDs already in steps (to avoid duplicates in picker)
const usedChildIds = computed(() => new Set(steps.value.map((s) => s.child_id)))

watch(
  () => [props.visible, props.workflow] as const,
  ([visible, w]) => {
    if (visible) {
      name.value = w?.name ?? ''
      description.value = w?.description ?? ''
      color.value = w?.color ?? PRESET_COLORS[0]
      isComposite.value = w?.is_composite ?? false
      steps.value = (w?.composition ?? []).map((c) => ({
        child_id: c.child_id,
        typical_pct: c.typical_pct != null ? String(Math.round(c.typical_pct * 100)) : '',
      }))
      error.value = ''
    }
  },
  { immediate: true }
)

// Fetch workflows when modal opens so child picker is populated
watch(
  () => props.visible,
  (v) => { if (v) store.fetchWorkflows() }
)

function addStep() {
  // Add first available workflow not already in steps
  const available = childOptions.value.find((w) => !usedChildIds.value.has(w.id))
  if (!available) return
  steps.value.push({ child_id: available.id, typical_pct: '' })
}

function removeStep(index: number) {
  steps.value.splice(index, 1)
}

async function submit() {
  const n = name.value.trim()
  if (!n) {
    error.value = 'Name is required'
    return
  }
  if (isComposite.value && steps.value.length === 0) {
    error.value = 'A process needs at least one step'
    return
  }
  error.value = ''
  submitting.value = true

  const composition: WorkflowCompositionStepInput[] = isComposite.value
    ? steps.value.map((s, i) => ({
        child_id: s.child_id,
        typical_pct: s.typical_pct ? parseFloat(s.typical_pct) / 100 : null,
        display_order: i,
      }))
    : []

  try {
    if (props.workflow) {
      await store.updateWorkflow(props.workflow.id, {
        name: n,
        description: description.value.trim() || null,
        color: color.value || undefined,
        composition: isComposite.value ? composition : [],
      })
    } else {
      await store.createWorkflow({
        name: n,
        description: description.value.trim() || null,
        color: color.value || undefined,
        is_composite: isComposite.value,
        composition,
      })
    }
    emit('saved')
    emit('close')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Request failed'
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  if (!submitting.value) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      @click.self="handleClose"
    >
      <div
        class="dark:bg-slate-800 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div class="flex items-center justify-between mb-5">
          <h2 id="modal-title" class="text-lg font-semibold text-white">
            {{ workflow ? 'Edit workflow' : 'New workflow' }}
          </h2>
          <button
            type="button"
            class="text-slate-400 hover:text-slate-200 text-xl leading-none"
            aria-label="Close"
            @click="handleClose"
          >
            ✕
          </button>
        </div>

        <form @submit.prevent="submit" class="space-y-4">
          <div>
            <label for="wf-name" class="block text-sm font-medium text-slate-300 mb-1.5">
              Name <span class="text-red-400">*</span>
            </label>
            <input
              id="wf-name"
              v-model="name"
              type="text"
              required
              autofocus
              class="w-full rounded-lg border border-slate-600 bg-slate-700 text-white placeholder-slate-500 px-3 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              :placeholder="isComposite ? 'e.g. Startup Sourcing' : 'e.g. Deep Work'"
            />
          </div>

          <div>
            <label for="wf-desc" class="block text-sm font-medium text-slate-300 mb-1.5">
              Description <span class="text-slate-500 font-normal">(optional)</span>
            </label>
            <textarea
              id="wf-desc"
              v-model="description"
              rows="2"
              class="w-full rounded-lg border border-slate-600 bg-slate-700 text-white placeholder-slate-500 px-3 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-none"
              placeholder="What does this workflow cover?"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Color</label>
            <div class="flex flex-wrap gap-2.5">
              <button
                v-for="c in PRESET_COLORS"
                :key="c"
                type="button"
                class="w-8 h-8 rounded-full transition-transform focus:outline-none"
                :class="color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-slate-800 scale-110' : 'opacity-70 hover:opacity-100'"
                :style="{ backgroundColor: c }"
                @click="color = c"
              />
            </div>
            <input
              v-model="color"
              type="text"
              class="mt-3 w-32 rounded-lg border border-slate-600 bg-slate-700 text-slate-300 placeholder-slate-500 px-3 py-1.5 text-sm focus:outline-none focus:border-indigo-500"
              placeholder="#hex"
            />
          </div>

          <!-- Composite toggle -->
          <div class="border-t border-slate-700 pt-4">
            <label class="flex items-center gap-3 cursor-pointer select-none">
              <button
                type="button"
                class="relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors focus:outline-none"
                :class="isComposite ? 'bg-indigo-600' : 'bg-slate-600'"
                @click="isComposite = !isComposite"
                :aria-checked="isComposite"
                role="switch"
              >
                <span
                  class="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5"
                  :class="isComposite ? 'translate-x-4' : 'translate-x-0.5'"
                />
              </button>
              <span class="text-sm text-slate-200 font-medium">This is a composite process</span>
            </label>
            <p class="mt-1 ml-12 text-xs text-slate-500">
              Groups multiple workflows into a named process (e.g. Startup Sourcing = Research + Deep Work + Email)
            </p>
          </div>

          <!-- Composition steps (only when composite) -->
          <div v-if="isComposite" class="space-y-2">
            <p class="text-xs font-semibold uppercase tracking-widest text-slate-500">Steps</p>

            <div v-if="steps.length === 0" class="text-xs text-slate-600 px-1">
              No steps yet — add one below.
            </div>

            <div
              v-for="(step, i) in steps"
              :key="i"
              class="flex items-center gap-2"
            >
              <!-- Child workflow picker -->
              <select
                v-model="step.child_id"
                class="flex-1 rounded-lg border border-slate-600 bg-slate-700 text-sm text-white px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                <option
                  v-for="w in childOptions"
                  :key="w.id"
                  :value="w.id"
                  :disabled="usedChildIds.has(w.id) && step.child_id !== w.id"
                >
                  {{ w.name }}
                </option>
              </select>

              <!-- Percentage (advisory) -->
              <div class="flex items-center gap-1 shrink-0">
                <input
                  v-model="step.typical_pct"
                  type="number"
                  min="0"
                  max="100"
                  placeholder="—"
                  class="w-14 rounded-lg border border-slate-600 bg-slate-700 text-sm text-white px-2 py-1.5 focus:outline-none focus:border-indigo-500 text-center"
                />
                <span class="text-xs text-slate-500">%</span>
              </div>

              <!-- Remove -->
              <button
                type="button"
                class="text-slate-600 hover:text-red-400 transition-colors text-sm shrink-0"
                title="Remove step"
                @click="removeStep(i)"
              >
                ✕
              </button>
            </div>

            <button
              type="button"
              class="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors mt-1"
              :disabled="childOptions.every((w) => usedChildIds.has(w.id))"
              @click="addStep"
            >
              <span class="text-base leading-none">+</span> Add step
            </button>

            <p v-if="steps.length > 0" class="text-xs text-slate-600 mt-1">
              Percentages are advisory targets. Actual breakdown is computed from real session data.
            </p>
          </div>

          <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>

          <div class="flex justify-end gap-2 pt-1">
            <button
              type="button"
              class="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700 hover:text-white transition-colors text-sm"
              @click="handleClose"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm disabled:opacity-50 transition-colors"
              :disabled="submitting"
            >
              {{ submitting ? 'Saving…' : workflow ? 'Save changes' : 'Create workflow' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
