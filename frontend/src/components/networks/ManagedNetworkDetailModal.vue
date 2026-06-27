<script setup>
import { computed } from 'vue';
import BaseModal from '../BaseModal.vue';
import DetailSummaryBanner from '../ui/detail/DetailSummaryBanner.vue';
import DetailLoadingState from '../ui/detail/DetailLoadingState.vue';
import DetailAttrsPanel from '../ui/detail/DetailAttrsPanel.vue';
import ManagedImageSummaryPanel from '../images/detail/ManagedImageSummaryPanel.vue';
import ManagedNetworkContainersPanel from './detail/ManagedNetworkContainersPanel.vue';
import ManagedNetworkCapabilitiesPanel from './detail/ManagedNetworkCapabilitiesPanel.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '网络详情' },
  loading: { type: Boolean, default: false },
  data: { type: Object, default: null },
});

const emit = defineEmits(['close']);

const PRIMARY_LABELS = new Set(['网络名称', '网络 ID']);

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

const detailAttrsText = computed(() => JSON.stringify(props.data?.attrs || {}, null, 2));

const detailMetaCount = computed(() => {
  const data = props.data || {};
  return {
    labels: Object.keys(data.labels || {}).length,
    attachedContainers: (data.attached_container_ids || []).length,
  };
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
    <DetailLoadingState v-if="loading" compact message="正在加载网络详情..." />
    <div v-else-if="data" class="space-y-4">
      <DetailSummaryBanner>
        当前网络包含 {{ detailMetaCount.labels }} 个标签，挂载 {{ detailMetaCount.attachedContainers }} 个容器，驱动为 {{ data.driver || '-' }}。
      </DetailSummaryBanner>

      <ManagedImageSummaryPanel
        title="网络摘要"
        :summary-entries="detailSummary"
        :relation-entries="detailRelationSummary"
        :primary-labels="PRIMARY_LABELS"
      />

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <ManagedNetworkContainersPanel :container-ids="data.attached_container_ids || []" />
        <ManagedNetworkCapabilitiesPanel
          :internal="data.internal"
          :attachable="data.attachable"
          :enable-ipv6="data.enable_ipv6"
        />
      </div>

      <DetailAttrsPanel :content="detailAttrsText" />
    </div>
  </BaseModal>
</template>
