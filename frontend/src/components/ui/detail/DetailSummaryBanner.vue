<script setup>
defineProps({
  title: { type: String, default: '数据摘要' },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3">
    <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ title }}</p>
    <p class="mt-1 text-sm text-slate-700">
      <slot />
    </p>
  </div>
</template>
