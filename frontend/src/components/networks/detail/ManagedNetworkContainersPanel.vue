<script setup>
import SectionCard from '../../ui/SectionCard.vue';
import DetailFieldCell from '../../ui/detail/DetailFieldCell.vue';

defineProps({
  containerIds: { type: Array, default: () => [] },
});
</script>

<template>
  <SectionCard title="附加容器">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ containerIds.length }} 项</span>
    </template>
    <div class="h-[260px] min-h-0 overflow-auto">
      <div v-if="containerIds.length" class="grid grid-cols-1 gap-3">
        <DetailFieldCell
          v-for="containerId in containerIds"
          :key="containerId"
          label="容器"
          :value="containerId"
          monospace
        />
      </div>
      <div v-else class="flex h-full items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500">
        当前没有挂载容器
      </div>
    </div>
  </SectionCard>
</template>
