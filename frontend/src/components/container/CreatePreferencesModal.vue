<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  imageSourceLoading: { type: Boolean, default: false },
  imageSourceSaving: { type: Boolean, default: false },
  limitsLoading: { type: Boolean, default: false },
  limitsSaving: { type: Boolean, default: false },
  imageSourceInput: { type: String, default: '' },
  maxContainersInput: { type: String, default: '' },
  maxRenewTimesInput: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:imageSourceInput',
  'update:maxContainersInput',
  'update:maxRenewTimesInput',
]);

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="偏好设置"
    icon="bolt"
    width="max-w-[720px]"
    close-text="取消"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="镜像源" description="为公共镜像配置加速前缀，例如私有仓库或内部镜像站。">
        <template #header>
          <span
            class="rounded-full border px-2 py-0.5 text-[11px] font-medium"
            :class="String(imageSourceInput || '').trim() ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
          >
            {{ String(imageSourceInput || '').trim() ? '已设置' : '未设置' }}
          </span>
        </template>
        <label for="imageSourceInput" class="block text-xs font-medium text-slate-600">仓库前缀</label>
        <input
          id="imageSourceInput"
          :value="imageSourceInput"
          type="text"
          :disabled="imageSourceLoading || imageSourceSaving || limitsSaving"
          placeholder="留空使用默认源，如 registry.example.com/mirror"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
          @input="updateField('imageSourceInput', $event)"
        />
      </SectionCard>

      <SectionCard title="容器上限" description="限制单实例可创建的最大容器数量与可续期次数。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="maxContainersInput" class="block text-xs font-medium text-slate-600">最大容器数</label>
            <input
              id="maxContainersInput"
              :value="maxContainersInput"
              type="number"
              min="1"
              :disabled="limitsLoading || limitsSaving || imageSourceSaving"
              placeholder="默认 30"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('maxContainersInput', $event)"
            />
          </div>
          <div>
            <label for="maxRenewTimesInput" class="block text-xs font-medium text-slate-600">最大续期次数</label>
            <input
              id="maxRenewTimesInput"
              :value="maxRenewTimesInput"
              type="number"
              min="0"
              :disabled="limitsLoading || limitsSaving || imageSourceSaving"
              placeholder="默认 3"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('maxRenewTimesInput', $event)"
            />
          </div>
        </div>
      </SectionCard>
    </div>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="保存"
        submitting-text="保存中..."
        :disabled="imageSourceLoading || imageSourceSaving || limitsLoading || limitsSaving"
        :submitting="imageSourceSaving || limitsSaving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

