<script setup>
const props = defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  variant: { type: String, default: 'white' }, // 'white' | 'muted'
});

function containerClass() {
  if (props.variant === 'muted') return 'rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3';
  return 'rounded-xl border border-slate-200 bg-white p-4';
}
</script>

<template>
  <div :class="containerClass()">
    <div v-if="title || description || $slots.header" class="mb-3 flex items-start justify-between gap-3">
      <div v-if="title || description">
        <p v-if="title" class="text-xs font-semibold tracking-tight text-slate-900">{{ title }}</p>
        <p v-if="description" class="mt-1 text-xs text-slate-500">{{ description }}</p>
      </div>
      <slot name="header" />
    </div>
    <slot />
  </div>
</template>

