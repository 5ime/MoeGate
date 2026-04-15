<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  imageSource: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:imageSource',
]);

function updateField(event) {
  emit('update:imageSource', event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="镜像源设置"
    subtitle="镜像页与创建页共用这份全局仓库前缀配置"
    icon="bolt"
    width="max-w-[640px]"
    @close="emit('close')"
  >
    <SectionCard title="仓库前缀" description="为镜像拉取与按镜像创建容器提供统一前缀。">
      <template #header>
        <span
          class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
          :class="String(props.imageSource || '').trim() ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
        >{{ String(props.imageSource || '').trim() ? '已设置' : '未设置' }}</span>
      </template>

      <label class="block text-xs font-medium text-slate-600">镜像仓库前缀</label>
      <input
        :value="imageSource"
        class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
        placeholder="例如：docker.1ms.run 或 registry.example.com/mirror"
        @input="updateField"
      />
      <p class="mt-2 text-xs leading-5 text-slate-500">留空则直接使用原始镜像名；设置后会自动为未带 registry 的镜像补前缀。</p>
    </SectionCard>

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