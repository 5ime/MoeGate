<script setup>
import BaseModal from '../BaseModal.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  pending: { type: Boolean, default: false },
  inlineError: { type: String, default: '' },
  type: { type: String, default: 'tcp' },
  localPort: { type: String, default: '' },
  remotePort: { type: String, default: '' },
  domain: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:type',
  'update:localPort',
  'update:remotePort',
  'update:domain',
]);

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="编辑代理"
    icon="bolt"
    width="max-w-[720px]"
    close-text="取消"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3">
          <p class="text-xs font-semibold tracking-tight text-slate-900">端口与类型</p>
          <p class="mt-1 text-xs text-slate-500">修改后会更新对应代理配置。</p>
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label for="editFrpType" class="block text-xs font-medium text-slate-600">类型</label>
            <input
              id="editFrpType"
              :value="type"
              type="text"
              :disabled="pending"
              placeholder="tcp / http / https / udp"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('type', $event)"
            />
          </div>
          <div>
            <label for="editFrpLocalPort" class="block text-xs font-medium text-slate-600">本地端口</label>
            <input
              id="editFrpLocalPort"
              :value="localPort"
              type="number"
              min="1"
              :disabled="pending"
              placeholder="如: 8080"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('localPort', $event)"
            />
          </div>
          <div>
            <label for="editFrpRemotePort" class="block text-xs font-medium text-slate-600">远程端口</label>
            <input
              id="editFrpRemotePort"
              :value="remotePort"
              type="number"
              min="1024"
              max="65535"
              :disabled="pending"
              placeholder="如: 20080"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('remotePort', $event)"
            />
          </div>
        </div>
      </div>

      <div v-show="['http','https'].includes(String(type || '').toLowerCase())" class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3">
          <p class="text-xs font-semibold tracking-tight text-slate-900">域名</p>
        </div>
        <label for="editFrpDomain" class="block text-xs font-medium text-slate-600">域名</label>
        <input
          id="editFrpDomain"
          :value="domain"
          type="text"
          :disabled="pending"
          placeholder="如: xxx.example.com"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
          @input="updateField('domain', $event)"
        />
      </div>

      <p v-if="inlineError" class="text-xs leading-5 text-rose-600">{{ inlineError }}</p>
    </div>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="保存修改"
        submitting-text="保存中..."
        :disabled="false"
        :submitting="pending"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

