<script setup>
import SectionCard from './ui/SectionCard.vue';
import DetailFieldCell from './ui/detail/DetailFieldCell.vue';
import { formatDetailValue, sectionItemCount } from '../composables/useObjectDetail.js';

defineProps({
  sections: { type: Array, default: () => [] },
});
</script>

<template>
  <SectionCard
    v-for="section in sections"
    :key="section.key"
    :title="section.title"
  >
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ sectionItemCount(section) }} 项</span>
    </template>

    <div v-if="section.items.length" class="divide-y divide-slate-100">
      <div v-for="entry in section.items" :key="entry.key">
        <DetailFieldCell
          :label="entry.label"
          :value="formatDetailValue(entry.value)"
          :field-key="entry.key"
          monospace
        />
      </div>
    </div>

    <div v-if="section.arrayGroups.length" class="mt-3 space-y-3">
      <div
        v-for="bucket in section.arrayGroups"
        :key="bucket.key"
        class="overflow-hidden rounded-xl border border-slate-200 bg-white"
      >
        <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
          <p class="text-xs font-semibold text-slate-800">{{ bucket.title }}</p>
          <span class="text-[11px] font-medium text-slate-500">{{ bucket.items.length }} 项</span>
        </div>
        <div class="divide-y divide-slate-100">
          <div
            v-for="entry in bucket.items.filter((e) => e.label === '容器ID')"
            :key="entry.key"
            class="px-3 py-2.5"
          >
            <DetailFieldCell
              :label="entry.label"
              :value="formatDetailValue(entry.value)"
              :field-key="entry.key"
              monospace
            />
          </div>

          <div class="px-3 py-2.5">
            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <DetailFieldCell
                v-for="entry in bucket.items.filter((e) => e.label !== '容器ID')"
                :key="entry.key"
                :label="entry.label"
                :value="formatDetailValue(entry.value)"
                :field-key="entry.key"
                monospace
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </SectionCard>
</template>
