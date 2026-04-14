<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  limitsLoading: { type: Boolean, default: false },
  limitsSaving: { type: Boolean, default: false },
  maxContainersInput: { type: String, default: '' },
  maxRenewTimesInput: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
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
    title="创建偏好"
    icon="bolt"
    width="max-w-[640px]"
    close-text="取消"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="容器上限" description="限制单实例可创建的最大容器数量与可续期次数。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="maxContainersInput" class="block text-xs font-medium text-slate-600">最大容器数</label>
            <input
              id="maxContainersInput"
              :value="maxContainersInput"
              type="number"
              min="1"
              :disabled="limitsLoading || limitsSaving"
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
              :disabled="limitsLoading || limitsSaving"
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
        :disabled="limitsLoading || limitsSaving"
        :submitting="limitsSaving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

