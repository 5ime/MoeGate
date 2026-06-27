<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number, Boolean], default: '' },
  fieldKey: { type: String, default: '' },
  monospace: { type: Boolean, default: false },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
    <p class="text-xs font-semibold text-slate-700" :title="fieldKey || label">{{ label }}</p>
    <div
      class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap"
      :class="monospace ? 'font-mono' : ''"
    >
      {{ value }}
    </div>
  </div>
</template>
