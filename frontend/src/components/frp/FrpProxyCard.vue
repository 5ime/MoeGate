<script setup>
import SectionCard from '../ui/SectionCard.vue';

const props = defineProps({
  proxy: { type: Object, required: true },
  flashing: { type: Boolean, default: false },
  canEdit: { type: Boolean, default: true },
  canDelete: { type: Boolean, default: true },
  deleting: { type: Boolean, default: false },
  inlineError: { type: String, default: '' },
});

const emit = defineEmits(['edit', 'delete']);

function proxyType(proxy) {
  return proxy?.type || proxy?.proxy_type || 'tcp';
}

function proxyName(proxy) {
  return proxy?.name || '';
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '-';
  return value;
}

function localPort(proxy) {
  return displayValue(proxy?.localPort ?? proxy?.local_port);
}

function remotePort(proxy) {
  return displayValue(proxy?.remotePort ?? proxy?.remote_port);
}

function domain(proxy) {
  const customDomain = Array.isArray(proxy?.customDomains) ? proxy.customDomains[0] : '';
  return displayValue(proxy?.domain || customDomain);
}

function onEdit() {
  emit('edit', proxyName(props.proxy));
}

function onDelete() {
  emit('delete', proxyName(props.proxy));
}
</script>

<template>
  <SectionCard
    class="p-5 shadow-sm transition"
    :class="flashing ? 'entity-flash' : ''"
  >
    <div class="mb-4 flex items-start justify-between border-b border-slate-100 pb-3">
      <div class="min-w-0 flex-1">
        <div class="break-words text-lg font-semibold tracking-tight text-slate-900">{{ proxy.name || '未命名代理' }}</div>
      </div>
      <span class="ml-3 flex-shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider border-slate-200 bg-slate-50 text-slate-700">
        {{ proxyType(proxy) }}
      </span>
    </div>

    <div class="my-4 grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
      <div class="flex items-start justify-between">
        <span class="text-[12px] font-medium text-slate-500">本地端口</span>
        <span class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800">{{ localPort(proxy) }}</span>
      </div>
      <div class="flex items-start justify-between">
        <span class="text-[12px] font-medium text-slate-500">远程端口</span>
        <span class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800">{{ remotePort(proxy) }}</span>
      </div>
      <div class="flex items-start justify-between">
        <span class="text-[12px] font-medium text-slate-500">域名</span>
        <span
          class="max-w-[60%] break-all text-right text-[12px] font-semibold text-slate-800"
          :title="domain(proxy)"
        >{{ domain(proxy) }}</span>
      </div>
    </div>

    <div class="border-t border-slate-100 pt-3.5">
      <div class="flex items-center gap-2">
        <button
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="!canEdit"
          @click="onEdit"
        >编辑</button>
        <span class="flex-1"></span>
        <button
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="!canDelete || deleting"
          @click="onDelete"
        >{{ deleting ? '删除中...' : '删除' }}</button>
      </div>
      <p v-if="inlineError" class="mt-2 text-xs leading-5 text-rose-600">{{ inlineError }}</p>
    </div>
  </SectionCard>
</template>

