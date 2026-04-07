<script setup>
import SectionCard from './SectionCard.vue';

const props = defineProps({
  title: { type: String, default: '' },
  value: { type: [String, Number], default: '-' },
  suffix: { type: String, default: '' },
  secondaryValue: { type: [String, Number], default: '' },
  secondarySuffix: { type: String, default: '' },
  badge: { type: String, default: '' },
  description: { type: String, default: '' },
  valueId: { type: String, default: '' },
  heightClass: { type: String, default: 'h-[90px]' },
});
</script>

<template>
  <SectionCard :class="[heightClass, 'flex flex-col justify-between px-4 py-3']">
    <div class="flex items-start justify-between gap-2">
      <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">{{ title }}</span>
      <span v-if="badge" class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">{{ badge }}</span>
    </div>
    <div class="mt-1 flex items-baseline gap-2">
      <span :id="valueId || undefined" class="block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ value }}</span>
      <span v-if="suffix" class="text-xs font-medium text-slate-500">{{ suffix }}</span>
      <template v-if="secondaryValue !== '' && secondaryValue !== null && secondaryValue !== undefined">
        <span class="text-slate-300">/</span>
        <span class="block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ secondaryValue }}</span>
        <span v-if="secondarySuffix" class="text-xs font-medium text-slate-500">{{ secondarySuffix }}</span>
      </template>
    </div>
    <p v-if="description" class="text-xs leading-5 text-slate-500">{{ description }}</p>
  </SectionCard>
</template>

