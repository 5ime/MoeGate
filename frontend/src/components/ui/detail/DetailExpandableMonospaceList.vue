<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  count: { type: Number, default: undefined },
  resetKey: { type: [String, Number, Boolean], default: null },
});

const showAll = ref(false);

watch(
  () => props.resetKey,
  () => {
    showAll.value = false;
  },
);

const totalCount = computed(() => (props.count ?? props.items.length));
const displayedItems = computed(() => {
  if (showAll.value) return props.items;
  return props.items.slice(0, 1);
});
</script>

<template>
  <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
    <div class="flex items-start justify-between gap-3">
      <p class="text-xs font-semibold text-slate-700">{{ title }}</p>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">{{ totalCount }} 项</span>
    </div>
    <div v-if="displayedItems.length" class="mt-2 space-y-2">
      <div
        v-for="item in displayedItems"
        :key="item"
        class="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap"
      >{{ item }}</div>
    </div>
    <div v-else class="mt-2 rounded-md border border-dashed border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">
      <slot name="empty">无数据</slot>
    </div>
    <button
      v-if="totalCount > 1"
      class="mt-2 inline-flex h-7 items-center justify-center gap-1 rounded-[10px] border border-slate-200 bg-white px-2.5 text-[11px] font-medium text-slate-700 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc]"
      @click="showAll = !showAll"
    >{{ showAll ? `收起${title}` : `展开其余 ${totalCount - 1} 个${title}` }}</button>
  </div>
</template>
