<script setup>
import { computed, ref, watch } from 'vue';
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '受管镜像详情' },
  loading: { type: Boolean, default: false },
  data: { type: Object, default: null },
});

const emit = defineEmits(['close']);

function formatValue(value) {
  const text = String(value || '').trim();
  return text || '-';
}

function formatDate(value) {
  const text = String(value || '').trim();
  if (!text) return '-';
  const normalized = text.replace('T', ' ').replace('Z', '');
  return normalized.split('.')[0] || '-';
}

function boolLabel(value) {
  return value ? '是' : '否';
}

const detailSummary = computed(() => {
  const data = props.data || {};
  return [
    { label: '主标签', value: data.primary_tag || '-' },
    { label: '镜像 ID', value: data.id || '-' },
    { label: '镜像体积', value: data.size_text || '-' },
    { label: '创建时间', value: formatDate(data.created_at) },
    { label: '架构', value: data.architecture || '-' },
    { label: '系统', value: data.os || '-' },
  ];
});

const detailManagedSummary = computed(() => {
  const data = props.data || {};
  return [
    { label: '受管来源', value: data.managed_source || '-' },
    { label: '请求镜像', value: data.managed_requested_image || '-' },
    { label: '解析镜像', value: data.managed_resolved_image || '-' },
    { label: '纳管时间', value: formatDate(data.managed_created_at) },
    { label: '最近更新', value: formatDate(data.managed_updated_at) },
    { label: '悬空镜像', value: boolLabel(data.is_dangling) },
  ];
});

const detailMetaCount = computed(() => {
  const data = props.data || {};
  return {
    tags: (data.tags || []).length,
    digests: (data.repo_digests || []).length,
    labels: Object.keys(data.labels || {}).length,
    containers: (data.container_refs || []).length,
  };
});

const detailAttrsText = computed(() => JSON.stringify(props.data?.attrs || {}, null, 2));
const showAllTags = ref(false);
const showAllDigests = ref(false);

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      showAllTags.value = false;
      showAllDigests.value = false;
    }
  },
);

watch(
  () => props.data,
  () => {
    showAllTags.value = false;
    showAllDigests.value = false;
  },
);

const displayedTags = computed(() => {
  const tags = props.data?.tags || [];
  if (showAllTags.value) return tags;
  return tags.slice(0, 1);
});

const displayedDigests = computed(() => {
  const digests = props.data?.repo_digests || [];
  if (showAllDigests.value) return digests;
  return digests.slice(0, 1);
});

const DETAIL_PRIMARY_LABELS = new Set(['主标签', '镜像 ID']);
const detailSummarySections = computed(() => {
  const primary = [];
  const secondary = [];
  for (const entry of detailSummary.value) {
    if (DETAIL_PRIMARY_LABELS.has(entry.label)) primary.push(entry);
    else secondary.push(entry);
  }
  return { primary, secondary };
});

const labelEntries = computed(() => Object.entries(props.data?.labels || {}));
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
    <div v-if="loading" class="py-8 text-center text-sm text-slate-500">正在加载受管镜像详情...</div>
    <div v-else-if="data" class="space-y-4">
      <SectionCard variant="muted">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">数据摘要</p>
        <p class="mt-1 text-sm text-slate-700">
          当前镜像包含 {{ detailMetaCount.tags }} 个标签、{{ detailMetaCount.digests }} 个 Digest，
          被 {{ detailMetaCount.containers }} 个受管容器引用，体积 {{ data.size_text || '-' }}。
        </p>
      </SectionCard>

      <SectionCard title="镜像摘要">
        <template #header>
          <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailSummary.length + detailManagedSummary.length }} 项</span>
        </template>

        <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div
            v-for="entry in detailManagedSummary"
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
        <SectionCard title="引用容器">
          <template #header>
            <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailMetaCount.containers }} 项</span>
          </template>
          <div class="h-[260px] min-h-0 overflow-auto">
            <div v-if="(data.container_refs || []).length" class="grid grid-cols-1 gap-3">
              <div
                v-for="container in data.container_refs || []"
                :key="container.id || container.name"
                class="rounded-md border border-slate-200 bg-slate-50/60 p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <p class="text-xs font-semibold text-slate-700">容器</p>
                </div>
                <div class="mt-2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ formatValue(container.id) }}
                </div>
              </div>
            </div>
            <div v-else class="flex h-full items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500">
              当前没有受管容器引用该镜像
            </div>
          </div>
        </SectionCard>

        <div class="space-y-4">
          <SectionCard title="标签与 Digest">
            <template #header>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailMetaCount.tags + detailMetaCount.digests }} 项</span>
            </template>
            <div class="space-y-3">
              <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <div class="flex items-start justify-between gap-3">
                  <p class="text-xs font-semibold text-slate-700">镜像标签</p>
                  <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">{{ detailMetaCount.tags }} 项</span>
                </div>
                <div v-if="displayedTags.length" class="mt-2 space-y-2">
                  <div
                    v-for="tag in displayedTags"
                    :key="tag"
                    class="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap"
                  >{{ tag }}</div>
                </div>
                <div v-else class="mt-2 rounded-md border border-dashed border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">无标签</div>
                <button
                  v-if="detailMetaCount.tags > 1"
                  class="mt-2 inline-flex h-7 items-center justify-center gap-1 rounded-[10px] border border-slate-200 bg-white px-2.5 text-[11px] font-medium text-slate-700 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc]"
                  @click="showAllTags = !showAllTags"
                >{{ showAllTags ? '收起标签' : `展开其余 ${detailMetaCount.tags - 1} 个标签` }}</button>
              </div>

              <div class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <div class="flex items-start justify-between gap-3">
                  <p class="text-xs font-semibold text-slate-700">Repo Digests</p>
                  <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">{{ detailMetaCount.digests }} 项</span>
                </div>
                <div v-if="displayedDigests.length" class="mt-2 space-y-2">
                  <div
                    v-for="digest in displayedDigests"
                    :key="digest"
                    class="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap"
                  >{{ digest }}</div>
                </div>
                <div v-else class="mt-2 rounded-md border border-dashed border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">无 Digest</div>
                <button
                  v-if="detailMetaCount.digests > 1"
                  class="mt-2 inline-flex h-7 items-center justify-center gap-1 rounded-[10px] border border-slate-200 bg-white px-2.5 text-[11px] font-medium text-slate-700 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc]"
                  @click="showAllDigests = !showAllDigests"
                >{{ showAllDigests ? '收起 Digest' : `展开其余 ${detailMetaCount.digests - 1} 个 Digest` }}</button>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="镜像标签元数据">
            <template #header>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailMetaCount.labels }} 项</span>
            </template>
            <div v-if="labelEntries.length" class="grid grid-cols-1 gap-3">
              <div v-for="[key, value] in labelEntries" :key="key" class="rounded-md border border-slate-200 bg-slate-50/60 p-3">
                <p class="text-xs font-semibold text-slate-700">{{ key }}</p>
                <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ formatValue(value) }}
                </div>
              </div>
            </div>
            <div v-else class="rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500">
              当前没有镜像标签元数据
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