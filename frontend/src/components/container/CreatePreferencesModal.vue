<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  limitsLoading: { type: Boolean, default: false },
  limitsSaving: { type: Boolean, default: false },
  imageSource: { type: String, default: '' },
  composeManagedSubnetPool: { type: String, default: '172.30.0.0/16' },
  composeManagedSubnetPrefix: { type: String, default: '24' },
  maxContainersInput: { type: String, default: '' },
  maxRenewTimesInput: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:imageSource',
  'update:composeManagedSubnetPool',
  'update:composeManagedSubnetPrefix',
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
    subtitle="镜像源、Compose 网络池与创建限制统一在此维护"
    icon="bolt"
    width="max-w-[760px]"
    close-text="取消"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="镜像源设置" description="镜像页与创建页共用这份全局仓库前缀配置。">
        <label for="imageSourceInput" class="block text-xs font-medium text-slate-600">镜像仓库前缀</label>
        <input
          id="imageSourceInput"
          :value="imageSource"
          type="text"
          :disabled="limitsLoading || limitsSaving"
          placeholder="例如：docker.1ms.run 或 registry.example.com/mirror"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
          @input="updateField('imageSource', $event)"
        />
        <p class="mt-2 text-xs leading-5 text-slate-500">留空则直接使用原始镜像名；设置后会自动为未带 registry 的镜像补前缀。</p>
      </SectionCard>

      <SectionCard title="Compose 网络池" description="网络页与创建页共用这份 Compose 受管子网配置。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="composeManagedSubnetPool" class="block text-xs font-medium text-slate-600">地址池</label>
            <input
              id="composeManagedSubnetPool"
              :value="composeManagedSubnetPool"
              type="text"
              :disabled="limitsLoading || limitsSaving"
              placeholder="例如：172.30.0.0/16"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('composeManagedSubnetPool', $event)"
            />
            <p class="mt-2 text-xs leading-5 text-slate-500">为每个 Compose 项目分配独立子网。</p>
          </div>
          <div>
            <label for="composeManagedSubnetPrefix" class="block text-xs font-medium text-slate-600">项目子网前缀</label>
            <input
              id="composeManagedSubnetPrefix"
              :value="composeManagedSubnetPrefix"
              type="number"
              min="1"
              max="30"
              :disabled="limitsLoading || limitsSaving"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('composeManagedSubnetPrefix', $event)"
            />
            <p class="mt-2 text-xs leading-5 text-slate-500">24 表示默认分配 /24；值越大，项目子网越小。</p>
          </div>
        </div>
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
        submit-text="保存设置"
        submitting-text="保存中..."
        :disabled="limitsLoading || limitsSaving"
        :submitting="limitsSaving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

