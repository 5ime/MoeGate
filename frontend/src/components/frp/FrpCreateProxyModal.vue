<script setup>
import BaseModal from '../BaseModal.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  pending: { type: Boolean, default: false },
  enabled: { type: Boolean, default: true },
  inlineError: { type: String, default: '' },
  name: { type: String, default: '' },
  localPort: { type: String, default: '' },
  remotePort: { type: String, default: '' },
  type: { type: String, default: 'tcp' },
  domain: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'submit',
  'update:name',
  'update:localPort',
  'update:remotePort',
  'update:type',
  'update:domain',
]);

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="新增代理"
    icon="bolt"
    width="max-w-[640px]"
    close-text="取消"
    @close="emit('close')"
  >
    <form id="createFrpForm" @submit.prevent="emit('submit')">
      <div class="space-y-4">
        <div class="rounded-xl border border-slate-200 bg-white p-4">
          <div class="mb-3">
            <p class="text-xs font-semibold tracking-tight text-slate-900">基础信息</p>
            <p class="mt-1 text-xs text-slate-500">名称与本地端口必填，其它为可选项。</p>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label for="frpName" class="block text-xs font-medium text-slate-600">名称 *</label>
              <input
                id="frpName"
                :value="name"
                type="text"
                placeholder="如: web-uid-123"
                required
                :disabled="pending"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
                @input="updateField('name', $event)"
              />
            </div>
            <div>
              <label for="frpLocalPort" class="block text-xs font-medium text-slate-600">本地端口 *</label>
              <input
                id="frpLocalPort"
                :value="localPort"
                type="number"
                min="1"
                placeholder="如: 8080"
                required
                :disabled="pending"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
                @input="updateField('localPort', $event)"
              />
            </div>
          </div>

          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label for="frpType" class="block text-xs font-medium text-slate-600">类型</label>
              <input
                id="frpType"
                :value="type"
                type="text"
                placeholder="tcp / http / https / udp"
                :disabled="pending"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
                @input="updateField('type', $event)"
              />
            </div>
            <div>
              <label for="frpRemotePort" class="block text-xs font-medium text-slate-600">远程端口</label>
              <input
                id="frpRemotePort"
                :value="remotePort"
                type="number"
                min="1024"
                max="65535"
                placeholder="如: 20080"
                :disabled="pending"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
                @input="updateField('remotePort', $event)"
              />
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white p-4">
          <div class="mb-3">
            <p class="text-xs font-semibold tracking-tight text-slate-900">域名（可选）</p>
            <p class="mt-1 text-xs text-slate-500">HTTP/HTTPS 可填写域名；TCP 通常留空。</p>
          </div>
          <label for="frpDomain" class="block text-xs font-medium text-slate-600">域名</label>
          <input
            id="frpDomain"
            :value="domain"
            type="text"
            placeholder="如: sub.example.com"
            :disabled="pending"
            class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
            @input="updateField('domain', $event)"
          />
        </div>

        <p v-if="inlineError" class="text-xs leading-5 text-rose-600">{{ inlineError }}</p>
      </div>
    </form>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="新增代理"
        submitting-text="提交中..."
        :disabled="!enabled"
        :submitting="pending"
        @cancel="emit('close')"
        @submit="emit('submit')"
      />
    </template>
  </BaseModal>
</template>

