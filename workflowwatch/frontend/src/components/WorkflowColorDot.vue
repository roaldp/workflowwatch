<script setup lang="ts">
defineProps<{
  color: string | null
}>()
</script>

<template>
  <span
    class="inline-block w-3 h-3 rounded-full shrink-0"
    :style="color ? { backgroundColor: color } : { backgroundColor: '#94a3b8' }"
  />
</template>
