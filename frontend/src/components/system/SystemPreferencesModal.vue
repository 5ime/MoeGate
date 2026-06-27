<script setup>
import { computed } from 'vue';
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  testSending: { type: Boolean, default: false },
  webhookUrl: { type: String, default: '' },
  webhookUrlSet: { type: Boolean, default: false },
  webhookUrlMasked: { type: String, default: '' },
  webhookTimeout: { type: String, default: '5' },
});

const emit = defineEmits([
  'close',
  'save',
  'send-test',
  'webhook-url-touched',
  'update:webhookUrl',
  'update:webhookTimeout',
]);

const webhookEnabled = computed(() => props.webhookUrlSet || Boolean(String(props.webhookUrl || '').trim()));

function updateField(field, event) {
  if (field === 'webhookUrl') {
    emit('webhook-url-touched');
  }
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="偏好设置"
    subtitle="Webhook 告警统一在此维护"
    icon="bolt"
    width="max-w-[760px]"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="Webhook" description="填写后默认启用资源告警，并可用于容器异常通知。">
        <template #header>
          <span
            class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
            :class="webhookEnabled ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
          >{{ webhookEnabled ? '已启用' : '未启用' }}</span>
        </template>

        <label class="block text-xs font-medium text-slate-600">Webhook URL</label>
        <input
          :value="webhookUrl"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          :placeholder="webhookUrlSet ? `已配置：${webhookUrlMasked || '***'}（输入新 URL 可覆盖）` : '例如：https://example.com/webhook 或飞书机器人 webhook'"
          @input="updateField('webhookUrl', $event)"
        />
        <p class="mt-2 text-xs leading-5 text-slate-500">
          {{ webhookUrlSet ? '留空并保存可保持当前 URL；输入新地址可覆盖，输入空白可关闭推送。' : '留空则关闭推送。' }}
        </p>

        <div class="relative mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label class="block text-xs font-medium text-slate-600">超时（秒）</label>
            <input
              :value="webhookTimeout"
              type="number"
              min="1"
              step="1"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              @input="updateField('webhookTimeout', $event)"
            />
          </div>
          <div class="flex items-end">
            <button
              class="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-[12px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="testSending || !webhookEnabled"
              type="button"
              @click="emit('send-test')"
            >{{ testSending ? '发送中...' : '发送测试' }}</button>
          </div>

          <div
            v-if="!webhookEnabled"
            class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
          >请先填写 Webhook URL</div>
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
