<script setup>
import { computed } from 'vue';
import SectionCard from '../../ui/SectionCard.vue';
import DetailFieldCell from '../../ui/detail/DetailFieldCell.vue';
import { splitDetailSummaryEntries } from '../../../composables/useDetailFormatters.js';

const props = defineProps({
  summaryEntries: { type: Array, default: () => [] },
  relationEntries: { type: Array, default: () => [] },
  primaryLabels: { type: Set, required: true },
  title: { type: String, default: '摘要' },
});

const detailSummarySections = computed(() => splitDetailSummaryEntries(props.summaryEntries, props.primaryLabels));
const totalCount = computed(() => props.summaryEntries.length + props.relationEntries.length);
</script>

<template>
  <SectionCard :title="title">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ totalCount }} 项</span>
    </template>

    <div v-if="relationEntries.length" class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
      <DetailFieldCell
        v-for="entry in relationEntries"
        :key="entry.label"
        :label="entry.label"
        :value="entry.value"
      />
    </div>

    <div v-if="detailSummarySections.primary.length" class="mt-3 space-y-3">
      <DetailFieldCell
        v-for="entry in detailSummarySections.primary"
        :key="entry.label"
        :label="entry.label"
        :value="entry.value"
      />
    </div>

    <div v-if="detailSummarySections.secondary.length" class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      <DetailFieldCell
        v-for="entry in detailSummarySections.secondary"
        :key="entry.label"
        :label="entry.label"
        :value="entry.value"
      />
    </div>
  </SectionCard>
</template>
