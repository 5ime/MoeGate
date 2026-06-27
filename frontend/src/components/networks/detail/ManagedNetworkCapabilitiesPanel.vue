<script setup>
import SectionCard from '../../ui/SectionCard.vue';
import DetailFieldCell from '../../ui/detail/DetailFieldCell.vue';
import { formatDetailBool } from '../../../composables/useDetailFormatters.js';

defineProps({
  internal: { type: Boolean, default: false },
  attachable: { type: Boolean, default: false },
  enableIpv6: { type: Boolean, default: false },
});
</script>

<template>
  <SectionCard title="网络能力">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">3 项</span>
    </template>
    <div class="grid grid-cols-1 gap-3">
      <DetailFieldCell label="内部网络" :value="formatDetailBool(internal)" />
      <DetailFieldCell label="允许附加" :value="formatDetailBool(attachable)" />
      <DetailFieldCell label="IPv6" :value="formatDetailBool(enableIpv6)" />
    </div>
  </SectionCard>
</template>
