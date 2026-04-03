<script setup>
import { computed, ref, nextTick, watch, onBeforeUnmount } from 'vue';
import BaseModal from './BaseModal.vue';
import { API_PREFIX, getApiBase, getApiKey } from '../api/client';

const props = defineProps({
  visible: Boolean,
  payload: Object,
});

const emit = defineEmits(['close', 'success']);

const logs = ref([]);
const status = ref('idle');       // idle | building | success | error
const errorMsg = ref('');
const logContainer = ref(null);
const buildPhase = ref('building'); // building | finalizing

let abortController = null;

const modalTitle = computed(() => {
  if (status.value === 'building') {
    return buildPhase.value === 'finalizing' ? '服务已启动，正在完成配置...' : '正在构建...';
  }
  if (status.value === 'success') return '构建完成';
  if (status.value === 'error') return '构建失败';
  return '构建进度';
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

watch(() => props.visible, async (val) => {
  if (val && props.payload) {
    logs.value = [];
    status.value = 'building';
    buildPhase.value = 'building';
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
  buildPhase.value = 'building';
  emit('close');
}

function isServiceStartedLog(line) {
  const text = String(line || '').toLowerCase();
  return text.includes('所有服务启动完成')
    || text.includes('services started')
    || text.includes('service started')
    || text.includes('container started')
    || text.includes('启动完成');
}

async function startStream(body) {
  abort();
  abortController = new AbortController();

  try {
    const headers = { 'Content-Type': 'application/json' };
    const key = getApiKey();
    if (key) headers['X-API-Key'] = key;

    const resp = await fetch(`${getApiBase()}${API_PREFIX}/containers/stream`, {
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
          if (status.value === 'building' && isServiceStartedLog(data)) {
            buildPhase.value = 'finalizing';
          }
          scrollToBottom();
        } else if (eventType === 'result') {
          status.value = 'success';
          buildPhase.value = 'building';
          logs.value.push('[完成] 容器创建成功');
          scrollToBottom();
          try {
            emit('success', JSON.parse(data));
          } catch {
            emit('success', null);
          }
        } else if (eventType === 'error') {
          status.value = 'error';
          buildPhase.value = 'building';
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
  } catch (e) {
    if (e.name === 'AbortError') return;
    status.value = 'error';
    errorMsg.value = e.message || '网络错误';
    logs.value.push(`[错误] ${errorMsg.value}`);
  }
}
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="modalTitle"
    subtitle="实时构建日志（自动滚动）"
    :icon="modalIcon"
    width="max-w-[880px]"
    close-text="关闭"
    @close="handleClose"
  >
    <div class="space-y-3">
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div>
            <p class="text-xs font-semibold tracking-tight text-slate-900">构建输出</p>
            <p class="mt-1 text-xs text-slate-500">用于排查 Docker 构建/启动问题。</p>
          </div>
          <span
            class="rounded-full border px-2 py-0.5 text-[11px] font-medium"
            :class="status === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : status === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
          >
            {{ status === 'building' ? (buildPhase === 'finalizing' ? '完成配置中' : '构建中') : status === 'success' ? '成功' : status === 'error' ? '失败' : '—' }}
          </span>
        </div>

        <div
          ref="logContainer"
          class="build-log-container max-h-[56vh] min-h-[220px] overflow-y-auto rounded-[14px] border border-slate-200 bg-slate-950 p-4 font-mono text-[13px] leading-relaxed text-slate-300"
        >
          <div v-if="logs.length === 0" class="text-slate-500">等待构建日志...</div>
          <div
            v-for="(line, idx) in logs"
            :key="idx"
            class="build-log-line whitespace-pre-wrap break-all"
            :class="{
              'text-emerald-400': line.startsWith('[完成]'),
              'text-red-400': line.startsWith('[错误]'),
              'text-amber-300': line.startsWith('Step ') || line.startsWith('step '),
            }"
          >{{ line }}</div>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="text-xs text-slate-500">
        {{ logs.length }} 行日志
      </span>
    </template>
  </BaseModal>
</template>
