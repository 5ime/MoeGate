<script setup>
import SectionCard from './ui/SectionCard.vue';
import DetailFieldCell from './ui/detail/DetailFieldCell.vue';
import { formatDetailValue, formatTokenLabel } from '../composables/useObjectDetail.js';

defineProps({
  entries: { type: Array, default: () => [] },
});
</script>

<template>
  <SectionCard title="容器信息">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ entries.length }} 项</span>
    </template>

    <div
      v-for="entry in entries.filter((e) => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) === '容器ID')"
      :key="entry.key"
      class="mb-3"
    >
      <DetailFieldCell
        label="容器ID"
        :value="formatDetailValue(entry.value)"
        :field-key="entry.key"
        monospace
      />
    </div>

    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <DetailFieldCell
        v-for="entry in entries.filter((e) => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) !== '容器ID')"
        :key="entry.key"
        :label="formatTokenLabel(entry.key.split('.').slice(-1)[0] || entry.key)"
        :value="formatDetailValue(entry.value)"
        :field-key="entry.key"
        monospace
      />
    </div>
  </SectionCard>
</template>
