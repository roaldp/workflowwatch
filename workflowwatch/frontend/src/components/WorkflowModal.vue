<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow } from '../types/workflow'

const PRESET_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']

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
const submitting = ref(false)
const error = ref('')

watch(
  () => [props.visible, props.workflow] as const,
  ([visible, w]) => {
    if (visible) {
      name.value = w?.name ?? ''
      description.value = w?.description ?? ''
      color.value = w?.color ?? PRESET_COLORS[0]
      error.value = ''
    }
  },
  { immediate: true }
)

const store = useWorkflowsStore()

async function submit() {
  const n = name.value.trim()
  if (!n) {
    error.value = 'Name is required'
    return
  }
  error.value = ''
  submitting.value = true
  try {
    if (props.workflow) {
      await store.updateWorkflow(props.workflow.id, {
        name: n,
        description: description.value.trim() || null,
        color: color.value || undefined,
      })
    } else {
      await store.createWorkflow({
        name: n,
        description: description.value.trim() || null,
        color: color.value || undefined,
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
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      @click.self="handleClose"
    >
      <div
        class="bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <h2 id="modal-title" class="text-lg font-semibold mb-4">
          {{ workflow ? 'Edit workflow' : 'New workflow' }}
        </h2>

        <form @submit.prevent="submit" class="space-y-4">
          <div>
            <label for="wf-name" class="block text-sm font-medium mb-1">Name *</label>
            <input
              id="wf-name"
              v-model="name"
              type="text"
              required
              class="w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2"
              placeholder="e.g. Startup Sourcing"
            />
          </div>
          <div>
            <label for="wf-desc" class="block text-sm font-medium mb-1">Description</label>
            <textarea
              id="wf-desc"
              v-model="description"
              rows="2"
              class="w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2"
              placeholder="Optional"
            />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Color</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="c in PRESET_COLORS"
                :key="c"
                type="button"
                class="w-8 h-8 rounded-full border-2 transition"
                :class="color === c ? 'border-slate-800 scale-110' : 'border-transparent'"
                :style="{ backgroundColor: c }"
                @click="color = c"
              />
            </div>
            <input
              v-model="color"
              type="text"
              class="mt-2 w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1 text-sm"
              placeholder="#hex"
            />
          </div>

          <p v-if="error" class="text-red-600 text-sm">{{ error }}</p>

          <div class="flex justify-end gap-2 pt-2">
            <button
              type="button"
              class="px-4 py-2 rounded border border-slate-300 dark:border-slate-600"
              @click="handleClose"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="px-4 py-2 rounded bg-slate-800 text-white disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Saving…' : workflow ? 'Save' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
