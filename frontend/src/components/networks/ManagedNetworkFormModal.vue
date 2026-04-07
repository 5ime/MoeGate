<script setup>
import BaseModal from '../BaseModal.vue';
import KeyValueLinesEditor from '../KeyValueLinesEditor.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '创建受管网络' },
  subtitle: { type: String, default: '' },
  saving: { type: Boolean, default: false },
  errorText: { type: String, default: '' },

  name: { type: String, default: '' },
  driver: { type: String, default: 'bridge' },
  subnet: { type: String, default: '' },
  gateway: { type: String, default: '' },
  composeProjectId: { type: String, default: '' },
  internal: { type: Boolean, default: false },
  attachable: { type: Boolean, default: false },
  enableIpv6: { type: Boolean, default: false },
  labelsText: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'validate-labels',
  'update:name',
  'update:driver',
  'update:subnet',
  'update:gateway',
  'update:composeProjectId',
  'update:internal',
  'update:attachable',
  'update:enableIpv6',
  'update:labelsText',
]);

const capabilityOptions = [
  { key: 'internal', label: '内部网络', description: '仅限网络内互通。' },
  { key: 'attachable', label: '允许附加', description: '允许后续手动连接。' },
  { key: 'enableIpv6', label: '启用 IPv6', description: '启用 IPv6 支持。' },
];

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}

function updateBool(field, event) {
  emit(`update:${field}`, !!event.target.checked);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="title"
    :subtitle="subtitle"
    icon="bolt"
    width="max-w-[920px]"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard variant="muted">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">填写说明</p>
        <p class="mt-1 text-sm text-slate-700">子网可以直接填写 172.33.0.1/24，系统会自动整理成标准网段；网关需要位于子网内。</p>
      </SectionCard>

      <SectionCard title="基础配置" description="名称、驱动和地址规划决定网络的基本行为。">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label class="block text-xs font-medium text-slate-600">网络名称</label>
            <input :value="name" type="text" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" placeholder="例如 lab-net" @input="updateField('name', $event)" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600">驱动</label>
            <input :value="driver" type="text" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" placeholder="默认 bridge" @input="updateField('driver', $event)" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600">子网</label>
            <input :value="subnet" type="text" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" placeholder="例如 172.28.0.0/16" @input="updateField('subnet', $event)" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600">网关</label>
            <input :value="gateway" type="text" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" placeholder="例如 172.28.0.1" @input="updateField('gateway', $event)" />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="关联与能力" description="可选填写一个归属 ID，用于标记 Compose 项目或单容器来源。">
        <div>
          <label class="block text-xs font-medium text-slate-600">归属 ID</label>
          <input :value="composeProjectId" type="text" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" placeholder="可选，可填 Compose 项目或单容器标识" @input="updateField('composeProjectId', $event)" />
        </div>

        <div class="mt-4 grid grid-cols-3 gap-3">
          <label
            v-for="option in capabilityOptions"
            :key="option.key"
            class="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-3 text-sm text-slate-700"
          >
            <input
              :checked="option.key === 'internal' ? internal : option.key === 'attachable' ? attachable : enableIpv6"
              type="checkbox"
              class="mt-0.5 h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400"
              :disabled="saving"
              @change="updateBool(option.key, $event)"
            />
            <span>
              <span class="block font-medium text-slate-800">{{ option.label }}</span>
              <span class="mt-1 block text-xs leading-5 text-slate-500">{{ option.description }}</span>
            </span>
          </label>
        </div>

        <div class="mt-4 rounded-xl border border-dashed border-slate-300 bg-slate-50/70 px-3 py-3 text-xs leading-5 text-slate-500">
          网络更新采用离线重建策略。只要网络仍被容器占用，后端就会拒绝修改或删除。
        </div>
      </SectionCard>

      <SectionCard>
        <KeyValueLinesEditor
          :model-value="labelsText"
          :rows="8"
          placeholder="例如&#10;env=test&#10;owner=lab"
          helper-text="系统会自动维护 moegate.managed 和可选的 moegate.compose_project_id，无需手动重复填写。"
          @update:modelValue="emit('update:labelsText', $event)"
          @validate="emit('validate-labels')"
        >
          <template #header>
            <div>
              <p class="text-xs font-semibold tracking-tight text-slate-900">附加标签</p>
              <p class="mt-1 text-xs text-slate-500">每行一个标签，格式 key=value。系统标签会自动补齐，不需要手填。</p>
            </div>
          </template>
        </KeyValueLinesEditor>
      </SectionCard>

      <p v-if="errorText" class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-600">{{ errorText }}</p>
    </div>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="保存网络"
        submitting-text="保存中..."
        :disabled="saving"
        :submitting="saving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

