<script setup>
defineProps({
  message: { type: String, default: '加载中...' },
  compact: { type: Boolean, default: false },
});
</script>

<template>
  <div :class="compact ? 'py-8 text-center text-sm text-slate-500' : 'flex items-center justify-center py-12'">
    <svg v-if="!compact" class="h-5 w-5 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
    <span :class="compact ? '' : 'ml-2 text-sm text-slate-500'">{{ message }}</span>
  </div>
</template>
