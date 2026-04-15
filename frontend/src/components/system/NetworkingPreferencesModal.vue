<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  composeManagedSubnetPool: { type: String, default: '172.30.0.0/16' },
  composeManagedSubnetPrefix: { type: String, default: '24' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:composeManagedSubnetPool',
  'update:composeManagedSubnetPrefix',
]);

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="Compose 网络池"
    subtitle="网络页与创建页共用这份 Compose 受管子网配置"
    icon="bolt"
    width="max-w-[760px]"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="地址分配" description="Compose 项目默认从这里分配受管子网；单容器手填 network 不受这里影响。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label class="block text-xs font-medium text-slate-600">地址池</label>
            <input
              :value="composeManagedSubnetPool"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              placeholder="例如：172.30.0.0/16"
              @input="updateField('composeManagedSubnetPool', $event)"
            />
            <p class="mt-2 text-xs leading-5 text-slate-500">为每个 Compose 项目分配独立子网。</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600">项目子网前缀</label>
            <input
              :value="composeManagedSubnetPrefix"
              type="number"
              min="1"
              max="30"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              @input="updateField('composeManagedSubnetPrefix', $event)"
            />
            <p class="mt-2 text-xs leading-5 text-slate-500">24 表示默认分配 /24；值越大，项目子网越小。</p>
          </div>
        </div>
      </SectionCard>
    </div>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="保存设置"
        submitting-text="保存中..."
        :disabled="saving"
        :submitting="saving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>