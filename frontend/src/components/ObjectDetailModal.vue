<script setup>
import { computed, toRef } from 'vue';
import BaseModal from './BaseModal.vue';
import DetailSummaryBanner from './ui/detail/DetailSummaryBanner.vue';
import DetailLoadingState from './ui/detail/DetailLoadingState.vue';
import ObjectDetailContainerPanel from './ObjectDetailContainerPanel.vue';
import ObjectDetailSectionPanel from './ObjectDetailSectionPanel.vue';
import { useObjectDetail } from '../composables/useObjectDetail.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  data: { type: [Object, Array, String, Number, Boolean], default: null },
  mode: { type: String, default: '' },
  width: { type: String, default: 'max-w-[980px]' },
});

const emit = defineEmits(['close']);

const { detailEntries, detailSections } = useObjectDetail(toRef(props, 'data'));
const hasObjectData = computed(() => props.data && typeof props.data === 'object');
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="title"
    :icon="loading ? 'loading' : 'bolt'"
    :width="width"
    @close="emit('close')"
  >
    <div class="max-h-[70vh] overflow-y-auto">
      <DetailLoadingState v-if="loading" />

      <template v-else-if="hasObjectData">
        <div class="space-y-3">
          <DetailSummaryBanner>
            共 {{ detailEntries.length }} 个字段，按 {{ detailSections.length }} 个分组展示
          </DetailSummaryBanner>

          <ObjectDetailContainerPanel v-if="mode === 'container'" :entries="detailEntries" />
          <ObjectDetailSectionPanel v-else :sections="detailSections" />
        </div>
      </template>

      <div v-else class="py-12 text-center text-sm text-slate-400">暂无数据</div>
    </div>
  </BaseModal>
</template>
