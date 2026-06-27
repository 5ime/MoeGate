<script setup>
import { ref } from 'vue';

defineProps({
  visible: { type: Boolean, default: false },
  loginPending: { type: Boolean, default: false },
  loginError: { type: String, default: '' },
  authApiKey: { type: String, default: '' },
  authApiBase: { type: String, default: '' },
  authApiKeyVisible: { type: Boolean, default: false },
  authStorageHint: { type: String, default: '' },
});

const emit = defineEmits([
  'submit',
  'update:authApiKey',
  'update:authApiBase',
  'update:authApiKeyVisible',
  'input-api-key',
]);

const authApiKeyInput = ref(null);

function focusApiKey() {
  authApiKeyInput.value?.focus();
  authApiKeyInput.value?.select?.();
}

defineExpose({ focusApiKey });
</script>

<template>
  <div id="authOverlay" v-show="visible" class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/30 p-5 backdrop-blur-md">
    <div class="login-panel w-full max-w-[500px] rounded-[22px] border border-slate-200/80 bg-white p-8 shadow-[0_10px_40px_-16px_rgba(10,12,18,0.2)]">
      <div class="mb-5 flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[linear-gradient(150deg,#0f1013,#2a2d33)] text-lg font-semibold text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]">M</div>
        <div>
          <div class="text-lg font-bold tracking-tight text-slate-900">MoeGate 控制台</div>
          <div class="text-[13px] text-slate-500">请输入 API Key 登录</div>
        </div>
      </div>
      <form id="loginForm" class="mb-2 mt-2 flex flex-col gap-3" @submit.prevent="emit('submit')">
        <label for="authApiBase" class="text-sm font-medium text-slate-900">API Base</label>
        <input
          id="authApiBase"
          :value="authApiBase"
          type="text"
          placeholder="留空使用当前站点"
          :disabled="loginPending"
          class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100"
          @input="emit('update:authApiBase', $event.target.value)"
        />
        <p class="-mt-1 text-xs leading-5 text-slate-500">分离部署首次访问时请先填写后端 API 地址；填写后会保存在当前浏览器。</p>
        <label for="authApiKey" class="text-sm font-medium text-slate-900">API Key</label>
        <div class="relative">
          <input
            id="authApiKey"
            ref="authApiKeyInput"
            :value="authApiKey"
            :type="authApiKeyVisible ? 'text' : 'password'"
            placeholder="粘贴后提交"
            required
            :disabled="loginPending"
            :class="[
              'w-full rounded-xl border bg-white py-3 pl-4 pr-12 text-sm text-slate-900 transition focus:outline-none focus:ring-4',
              loginError ? 'border-slate-300 focus:border-slate-500 focus:ring-slate-100' : 'border-slate-200 focus:border-slate-400 focus:ring-slate-100'
            ]"
            @input="emit('update:authApiKey', $event.target.value); emit('input-api-key')"
          />
          <button
            type="button"
            class="absolute inset-y-0 right-0 inline-flex w-11 items-center justify-center text-xs font-medium text-slate-500 transition hover:text-slate-900"
            :aria-label="authApiKeyVisible ? '隐藏 API Key' : '显示 API Key'"
            :disabled="loginPending"
            @click="emit('update:authApiKeyVisible', !authApiKeyVisible)"
          >
            {{ authApiKeyVisible ? '隐藏' : '显示' }}
          </button>
        </div>
        <p v-if="loginError" class="-mt-1 text-xs text-rose-600">{{ loginError }}</p>
        <button type="submit" class="inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-6 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="loginPending">{{ loginPending ? '验证中...' : '登录' }}</button>
      </form>
      <div class="mt-2.5 text-center text-xs text-slate-400">{{ authStorageHint }}</div>
    </div>
  </div>
</template>
