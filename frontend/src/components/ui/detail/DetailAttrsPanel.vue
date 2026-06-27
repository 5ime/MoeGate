<script setup>
import SectionCard from '../SectionCard.vue';

defineProps({
  title: { type: String, default: '原始 attrs' },
  content: { type: String, default: '{}' },
});
</script>

<template>
  <SectionCard :title="title">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">调试信息</span>
    </template>
    <pre class="max-h-[260px] overflow-auto rounded-[12px] border border-slate-200 bg-[#fbfbfc] p-3 font-mono text-xs leading-relaxed text-slate-900">{{ content }}</pre>
  </SectionCard>
</template>
