<script setup>
import { computed } from 'vue';
import BaseModal from '../BaseModal.vue';
import DetailSummaryBanner from '../ui/detail/DetailSummaryBanner.vue';
import DetailLoadingState from '../ui/detail/DetailLoadingState.vue';
import DetailAttrsPanel from '../ui/detail/DetailAttrsPanel.vue';
import ManagedImageSummaryPanel from './detail/ManagedImageSummaryPanel.vue';
import ManagedImageRefsPanel from './detail/ManagedImageRefsPanel.vue';
import ManagedImageTagsDigestsPanel from './detail/ManagedImageTagsDigestsPanel.vue';
import ManagedImageLabelsPanel from './detail/ManagedImageLabelsPanel.vue';
import { formatDetailBool, formatDetailDate } from '../../composables/useDetailFormatters.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '受管镜像详情' },
  loading: { type: Boolean, default: false },
  data: { type: Object, default: null },
});

const emit = defineEmits(['close']);

const PRIMARY_LABELS = new Set(['主标签', '镜像 ID']);

const detailSummary = computed(() => {
  const data = props.data || {};
  return [
    { label: '主标签', value: data.primary_tag || '-' },
    { label: '镜像 ID', value: data.id || '-' },
    { label: '镜像体积', value: data.size_text || '-' },
    { label: '创建时间', value: formatDetailDate(data.created_at) },
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
    { label: '纳管时间', value: formatDetailDate(data.managed_created_at) },
    { label: '最近更新', value: formatDetailDate(data.managed_updated_at) },
    { label: '悬空镜像', value: formatDetailBool(data.is_dangling) },
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
const detailResetKey = computed(() => `${props.visible}:${props.data?.id || ''}`);
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
    <DetailLoadingState v-if="loading" compact message="正在加载受管镜像详情..." />
    <div v-else-if="data" class="space-y-4">
      <DetailSummaryBanner>
        当前镜像包含 {{ detailMetaCount.tags }} 个标签、{{ detailMetaCount.digests }} 个 Digest，
        被 {{ detailMetaCount.containers }} 个受管容器引用，体积 {{ data.size_text || '-' }}。
      </DetailSummaryBanner>

      <ManagedImageSummaryPanel
        title="镜像摘要"
        :summary-entries="detailSummary"
        :relation-entries="detailManagedSummary"
        :primary-labels="PRIMARY_LABELS"
      />

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <ManagedImageRefsPanel :container-refs="data.container_refs || []" />

        <div class="space-y-4">
          <ManagedImageTagsDigestsPanel
            :tags="data.tags || []"
            :digests="data.repo_digests || []"
            :reset-key="detailResetKey"
          />
          <ManagedImageLabelsPanel :labels="data.labels || {}" />
        </div>
      </div>

      <DetailAttrsPanel :content="detailAttrsText" />
    </div>
  </BaseModal>
</template>
