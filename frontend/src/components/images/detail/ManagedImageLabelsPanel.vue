<script setup>
import SectionCard from '../../ui/SectionCard.vue';
import DetailFieldCell from '../../ui/detail/DetailFieldCell.vue';
import { formatDetailText } from '../../../composables/useDetailFormatters.js';

defineProps({
  labels: { type: Object, default: () => ({}) },
});
</script>

<template>
  <SectionCard title="镜像标签元数据">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ Object.keys(labels).length }} 项</span>
    </template>
    <div v-if="Object.keys(labels).length" class="grid grid-cols-1 gap-3">
      <DetailFieldCell
        v-for="(value, key) in labels"
        :key="key"
        :label="key"
        :value="formatDetailText(value)"
      />
    </div>
    <div v-else class="rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500">
      当前没有镜像标签元数据
    </div>
  </SectionCard>
</template>
