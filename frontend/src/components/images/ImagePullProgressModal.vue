<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import BaseModal from '../BaseModal.vue';
import { API_PREFIX, getApiBase, getApiKey } from '../../api/client';

const props = defineProps({
  visible: Boolean,
  payload: Object,
});

const emit = defineEmits(['close', 'success']);

const logs = ref([]);
const status = ref('idle');
const errorMsg = ref('');
const logContainer = ref(null);

let abortController = null;

const modalTitle = computed(() => {
  if (status.value === 'building') return '正在拉取镜像...';
  if (status.value === 'success') return '拉取完成';
  if (status.value === 'error') return '拉取失败';
  return '拉取进度';
});

const modalIcon = computed(() => {
  if (status.value === 'building') return 'loading';
  if (status.value === 'success') return 'success';
  if (status.value === 'error') return 'error';
  return 'bolt';
});

function scrollToBottom() {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
}

watch(() => props.visible, async (visible) => {
  if (visible && props.payload) {
    logs.value = [];
    status.value = 'building';
    errorMsg.value = '';
    await nextTick();
    startStream(props.payload);
  }
});

onBeforeUnmount(() => {
  abort();
});

function abort() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
}

function handleClose() {
  abort();
  status.value = 'idle';
  emit('close');
}

async function startStream(body) {
  abort();
  abortController = new AbortController();

  try {
    const headers = { 'Content-Type': 'application/json' };
    const key = getApiKey();
    if (key) headers['X-API-Key'] = key;

    const resp = await fetch(`${getApiBase()}${API_PREFIX}/images/pull/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: abortController.signal,
    });

    if (!resp.ok) {
      const text = await resp.text();
      let msg = `HTTP ${resp.status}`;
      try { msg = JSON.parse(text)?.msg || msg; } catch {}
      status.value = 'error';
      errorMsg.value = msg;
      logs.value.push(`[错误] ${msg}`);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (!part.trim()) continue;
        const lines = part.split('\n');
        let eventType = 'log';
        let data = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim();
          else if (line.startsWith('data: ')) data = line.slice(6);
        }

        if (eventType === 'log') {
          logs.value.push(data);
          scrollToBottom();
        } else if (eventType === 'result') {
          status.value = 'success';
          logs.value.push('[完成] 受管镜像拉取成功');
          scrollToBottom();
          try {
            emit('success', JSON.parse(data));
          } catch {
            emit('success', null);
          }
        } else if (eventType === 'error') {
          status.value = 'error';
          try {
            const err = JSON.parse(data);
            errorMsg.value = err.msg || '未知错误';
          } catch {
            errorMsg.value = data || '未知错误';
          }
          logs.value.push(`[错误] ${errorMsg.value}`);
          scrollToBottom();
        }
      }
    }

    if (status.value === 'building') {
      status.value = 'error';
      errorMsg.value = '连接意外关闭';
      logs.value.push('[错误] 连接意外关闭');
    }
  } catch (error) {
    if (error?.name === 'AbortError') return;
    status.value = 'error';
    errorMsg.value = error.message || '网络错误';
    logs.value.push(`[错误] ${errorMsg.value}`);
  }
}
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="modalTitle"
    subtitle="实时拉取日志（自动滚动）"
    :icon="modalIcon"
    width="max-w-[880px]"
    close-text="关闭"
    @close="handleClose"
  >
    <div class="space-y-3">
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div>
            <p class="text-xs font-semibold tracking-tight text-slate-900">拉取输出</p>
            <p class="mt-1 text-xs text-slate-500">用于观察镜像下载层状态与最终完成结果。</p>
          </div>
          <span
            class="rounded-full border px-2 py-0.5 text-[11px] font-medium"
            :class="status === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : status === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
          >
            {{ status === 'building' ? '拉取中' : status === 'success' ? '成功' : status === 'error' ? '失败' : '—' }}
          </span>
        </div>

        <div
          ref="logContainer"
          class="build-log-container max-h-[56vh] min-h-[220px] overflow-y-auto rounded-[14px] border border-slate-200 bg-slate-950 p-4 font-mono text-[13px] leading-relaxed text-slate-300"
        >
          <div v-if="logs.length === 0" class="text-slate-500">等待拉取日志...</div>
          <div
            v-for="(line, idx) in logs"
            :key="idx"
            class="build-log-line whitespace-pre-wrap break-all"
            :class="{
              'text-emerald-400': line.startsWith('[完成]'),
              'text-red-400': line.startsWith('[错误]'),
              'text-sky-300': line.includes('Downloading') || line.includes('Pulling fs layer'),
            }"
          >{{ line }}</div>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="text-xs text-slate-500">{{ logs.length }} 行日志</span>
    </template>
  </BaseModal>
</template>