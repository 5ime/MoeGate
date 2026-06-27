<script setup>
import BaseModal from '../BaseModal.vue';

defineProps({
  visible: { type: Boolean, default: false },
  apiBase: { type: String, default: '' },
  pollSec: { type: String, default: '' },
});

const emit = defineEmits(['close', 'save', 'update:apiBase', 'update:pollSec']);
</script>

<template>
  <BaseModal :visible="visible" title="偏好设置" icon="bolt" width="max-w-[720px]" close-text="取消" @close="emit('close')">
    <div class="space-y-4">
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3">
          <p class="text-xs font-semibold tracking-tight text-slate-900">API Base</p>
          <p class="mt-1 text-xs text-slate-500">前后端分离部署时填写；留空则使用当前站点。</p>
        </div>
        <label for="apiBaseInput" class="block text-xs font-medium text-slate-600">地址</label>
        <input
          id="apiBaseInput"
          :value="apiBase"
          type="text"
          placeholder="例如：http://127.0.0.1:8080"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
          @input="emit('update:apiBase', $event.target.value)"
        />
      </div>

      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3">
          <p class="text-xs font-semibold tracking-tight text-slate-900">自动刷新</p>
          <p class="mt-1 text-xs text-slate-500">控制台自动刷新当前标签页的数据。</p>
        </div>
        <label for="pollIntervalInput" class="block text-xs font-medium text-slate-600">刷新间隔（秒）</label>
        <input
          id="pollIntervalInput"
          :value="pollSec"
          type="number"
          min="1"
          placeholder="默认 30"
          class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
          @input="emit('update:pollSec', $event.target.value)"
        />
        <p class="mt-2 text-xs text-slate-500">留空将恢复默认值。</p>
      </div>
    </div>

    <template #footer>
      <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="emit('close')">取消</button>
      <button id="saveSettingsBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="emit('save')">保存设置</button>
    </template>
  </BaseModal>
</template>
