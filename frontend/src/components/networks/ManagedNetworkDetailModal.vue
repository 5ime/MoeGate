<script setup>
import { computed } from 'vue';
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '网络详情' },
  loading: { type: Boolean, default: false },
  data: { type: Object, default: null },
});

const emit = defineEmits(['close']);

function boolLabel(value) {
  return value ? '是' : '否';
}

const detailSummary = computed(() => {
  const data = props.data || {};
  return [
    { label: '网络名称', value: data.name || '-' },
    { label: '网络 ID', value: data.id || '-' },
    { label: '驱动', value: data.driver || '-' },
    { label: '作用域', value: data.scope || '-' },
    { label: '子网', value: data.subnet || '-' },
    { label: '网关', value: data.gateway || '-' },
  ];
});

const detailRelationSummary = computed(() => {
  const data = props.data || {};
  return [
    { label: '归属 ID', value: data.compose_project_id || '-' },
    { label: '挂载容器数', value: String(data.attached_container_count ?? 0) },
  ];
});

const detailAttrsText = computed(() => {
  const attrs = props.data?.attrs;
  return JSON.stringify(attrs || {}, null, 2);
});

const detailMetaCount = computed(() => {
  const data = props.data || {};
  return {
    labels: Object.keys(data.labels || {}).length,
    attachedContainers: (data.attached_container_ids || []).length,
  };
});

const DETAIL_PRIMARY_LABELS = new Set(['网络名称', '网络 ID']);
const detailSummarySections = computed(() => {
  const primary = [];
  const secondary = [];
  for (const entry of detailSummary.value) {
    if (DETAIL_PRIMARY_LABELS.has(entry.label)) primary.push(entry);
    else secondary.push(entry);
  }
  return { primary, secondary };
});
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="title"
    subtitle="摘要字段来自服务层整理，原始 attrs 保留在底部便于排查"
    icon="info"
    width="max-w-[980px]"
    @close="emit('close')"
  >
    <div v-if="loading" class="py-8 text-center text-sm text-slate-500">正在加载网络详情...</div>
    <div v-else-if="data" class="space-y-4">
      <SectionCard variant="muted">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">数据摘要</p>
        <p class="mt-1 text-sm text-slate-700">
          当前网络包含 {{ detailMetaCount.labels }} 个标签，挂载 {{ detailMetaCount.attachedContainers }} 个容器，驱动为 {{ data.driver || '-' }}。
        </p>
      </SectionCard>

      <SectionCard title="网络摘要">
        <template #header>
          <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailSummary.length + detailRelationSummary.length }} 项</span>
        </template>

        <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div
            v-for="entry in detailRelationSummary"
            :key="entry.label"
            class="rounded-md border border-slate-200 bg-slate-50/60 p-3"
          >
            <p class="text-xs font-semibold text-slate-700">{{ entry.label }}</p>
            <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
              {{ entry.value }}
            </div>
          </div>
        </div>

        <div v-if="detailSummarySections.primary.length" class="mt-3 space-y-3">
          <div v-for="entry in detailSummarySections.primary" :key="entry.label" class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
            <p class="text-xs font-semibold text-slate-700">{{ entry.label }}</p>
            <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
              {{ entry.value }}
            </div>
          </div>
        </div>
        <div v-if="detailSummarySections.secondary.length" class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div v-for="entry in detailSummarySections.secondary" :key="entry.label" class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
            <p class="text-xs font-semibold text-slate-700">{{ entry.label }}</p>
            <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
              {{ entry.value }}
            </div>
          </div>
        </div>
      </SectionCard>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <SectionCard title="附加容器">
          <template #header>
            <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailMetaCount.attachedContainers }} 项</span>
          </template>
          <div class="h-[260px] min-h-0 overflow-auto">
            <div v-if="(data.attached_container_ids || []).length" class="grid grid-cols-1 gap-3">
              <div
                v-for="containerId in data.attached_container_ids || []"
                :key="containerId"
                class="rounded-md border border-slate-200 bg-slate-50/60 p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <p class="text-xs font-semibold text-slate-700">容器</p>
                </div>
                <div class="mt-2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ containerId }}
                </div>
              </div>
            </div>
            <div v-else class="h-full rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500 flex items-center justify-center">
              当前没有挂载容器
            </div>
          </div>
        </SectionCard>

        <div class="space-y-4">
          <SectionCard title="网络能力">
            <template #header>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">3 项</span>
            </template>
            <div class="grid grid-cols-1 gap-3">
              <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <p class="text-xs font-semibold text-slate-700">内部网络</p>
                <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800">{{ boolLabel(data.internal) }}</div>
              </div>
              <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <p class="text-xs font-semibold text-slate-700">允许附加</p>
                <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800">{{ boolLabel(data.attachable) }}</div>
              </div>
              <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <p class="text-xs font-semibold text-slate-700">IPv6</p>
                <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800">{{ boolLabel(data.enable_ipv6) }}</div>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>

      <SectionCard title="原始 attrs">
        <template #header>
          <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">调试信息</span>
        </template>
        <pre class="max-h-[260px] overflow-auto rounded-[12px] border border-slate-200 bg-[#fbfbfc] p-3 font-mono text-xs leading-relaxed text-slate-900">{{ detailAttrsText }}</pre>
      </SectionCard>
    </div>
  </BaseModal>
</template>

