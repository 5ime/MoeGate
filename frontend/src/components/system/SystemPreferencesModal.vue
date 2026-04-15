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
  webhookTimeout: { type: String, default: '5' },
  perfInterval: { type: String, default: '300' },
  cpuThreshold: { type: String, default: '95' },
  cpuIntervals: { type: String, default: '3' },
  memThreshold: { type: String, default: '90' },
  memIntervals: { type: String, default: '3' },
  cooldownSec: { type: String, default: '900' },
});

const emit = defineEmits([
  'close',
  'save',
  'send-test',
  'update:webhookUrl',
  'update:webhookTimeout',
  'update:perfInterval',
  'update:cpuThreshold',
  'update:cpuIntervals',
  'update:memThreshold',
  'update:memIntervals',
  'update:cooldownSec',
]);

const webhookEnabled = computed(() => Boolean(String(props.webhookUrl || '').trim()));

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="偏好设置"
    subtitle="Webhook 与资源告警策略统一在此维护"
    icon="bolt"
    width="max-w-[760px]"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div>
        <SectionCard title="Webhook" description="填写后默认启用资源告警，并可用于容器异常通知。">
          <template #header>
            <span
              class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
              :class="String(webhookUrl || '').trim() ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
            >{{ String(webhookUrl || '').trim() ? '已启用' : '未启用' }}</span>
          </template>

          <label class="block text-xs font-medium text-slate-600">Webhook URL</label>
          <input
            :value="webhookUrl"
            class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            placeholder="例如：https://example.com/webhook 或飞书机器人 webhook"
            @input="updateField('webhookUrl', $event)"
          />
          <p class="mt-2 text-xs leading-5 text-slate-500">留空则关闭推送。</p>

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
                :disabled="testSending || !String(webhookUrl || '').trim()"
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

      <div>
        <div class="relative">
          <SectionCard title="资源告警策略" description="CPU/内存任一达到“持续区间”条件即推送；冷却时间内只推送一次。">

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
              <label class="block text-xs font-medium text-slate-600">采样间隔（秒）</label>
              <input
                :value="perfInterval"
                type="number"
                min="1"
                step="1"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                @input="updateField('perfInterval', $event)"
              />
              <p class="mt-2 text-[11px] leading-4 text-slate-500">越小越灵敏，也更频繁采样。</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
              <label class="block text-xs font-medium text-slate-600">冷却时间（秒）</label>
              <input
                :value="cooldownSec"
                type="number"
                min="0"
                step="1"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                @input="updateField('cooldownSec', $event)"
              />
              <p class="mt-2 text-[11px] leading-4 text-slate-500">避免告警风暴；0 表示不冷却。</p>
            </div>
          </div>

          <div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-200 p-3">
              <div class="mb-2 flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-900">CPU</span>
                <span class="text-[11px] text-slate-500">阈值 + 持续区间</span>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600">阈值（%）</label>
                  <input
                    :value="cpuThreshold"
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                    @input="updateField('cpuThreshold', $event)"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600">持续区间</label>
                  <input
                    :value="cpuIntervals"
                    type="number"
                    min="1"
                    step="1"
                    class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                    @input="updateField('cpuIntervals', $event)"
                  />
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-slate-200 p-3">
              <div class="mb-2 flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-900">内存</span>
                <span class="text-[11px] text-slate-500">阈值 + 持续区间</span>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600">阈值（%）</label>
                  <input
                    :value="memThreshold"
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                    @input="updateField('memThreshold', $event)"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600">持续区间</label>
                  <input
                    :value="memIntervals"
                    type="number"
                    min="1"
                    step="1"
                    class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                    @input="updateField('memIntervals', $event)"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="mt-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
            <p class="text-xs text-slate-600">
              触发时间约为 <span class="font-semibold text-slate-900">采样间隔 × 持续区间</span>。
              若要快速验证推送，建议先把持续区间设为 <span class="font-semibold text-slate-900">1</span>。
            </p>
          </div>
          </SectionCard>

          <div
            v-if="!webhookEnabled"
            class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
          >请先填写 Webhook URL</div>
        </div>
      </div>
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

