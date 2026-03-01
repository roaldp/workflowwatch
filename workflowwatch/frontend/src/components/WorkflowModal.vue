<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkflowsStore } from '../stores/workflows'
import type { Workflow } from '../types/workflow'

const PRESET_COLORS = [
  '#6366F1', '#3B82F6', '#10B981', '#F59E0B',
  '#EF4444', '#8B5CF6', '#EC4899', '#94A3B8',
]

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
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      @click.self="handleClose"
    >
      <div
        class="dark:bg-slate-800 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-md mx-4 p-6"
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
              placeholder="e.g. Startup Sourcing"
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
