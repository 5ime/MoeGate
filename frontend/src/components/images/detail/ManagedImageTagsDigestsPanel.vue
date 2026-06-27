<script setup>
import SectionCard from '../../ui/SectionCard.vue';
import DetailExpandableMonospaceList from '../../ui/detail/DetailExpandableMonospaceList.vue';

defineProps({
  tags: { type: Array, default: () => [] },
  digests: { type: Array, default: () => [] },
  resetKey: { type: [String, Number, Boolean], default: null },
});
</script>

<template>
  <SectionCard title="标签与 Digest">
    <template #header>
      <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ tags.length + digests.length }} 项</span>
    </template>
    <div class="space-y-3">
      <DetailExpandableMonospaceList title="标签" :items="tags" :reset-key="resetKey">
        <template #empty>无标签</template>
      </DetailExpandableMonospaceList>
      <DetailExpandableMonospaceList title="Repo Digests" :items="digests" :reset-key="resetKey">
        <template #empty>无 Digest</template>
      </DetailExpandableMonospaceList>
    </div>
  </SectionCard>
</template>
