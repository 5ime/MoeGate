import { computed, ref } from 'vue';
import { API_PREFIX, getApiBase, getAuthHeaders } from '../api/client';
import { loadContainerLogs } from '../stores/logsStore';

export const LOG_TAIL_OPTIONS = [100, 200, 500, 1000];

// 跟随模式最多保留的行数，避免长时间挂着把内存吃满
const MAX_FOLLOW_LINES = 5000;

export function useContainerLogs() {
  const logs = ref(null);
  const loading = ref(false);
  const error = ref('');
  const tail = ref(200);
  const withTimestamps = ref(false);

  const followLines = ref([]);
  const following = ref(false);
  const followError = ref('');
  const followNotice = ref('');

  let abortController = null;
  let scrollHandler = null;

  const lines = computed(() => [...(logs.value?.lines || []), ...followLines.value]);
  const truncated = computed(() => !!logs.value?.truncated);
  const lineCount = computed(() => lines.value.length);
  const isEmpty = computed(() => !loading.value && !error.value && lines.value.length === 0);

  function setScrollHandler(handler) {
    scrollHandler = handler;
  }

  function appendFollowLine(line) {
    followLines.value.push(line);
    if (followLines.value.length > MAX_FOLLOW_LINES) {
      followLines.value.splice(0, followLines.value.length - MAX_FOLLOW_LINES);
    }
    scrollHandler?.();
  }

  function stopFollow() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    following.value = false;
  }

  function reset() {
    stopFollow();
    logs.value = null;
    followLines.value = [];
    error.value = '';
    followError.value = '';
    followNotice.value = '';
    loading.value = false;
  }

  async function refresh(containerId) {
    if (!containerId) return;
    stopFollow();
    followLines.value = [];
    loading.value = true;
    error.value = '';
    followError.value = '';
    followNotice.value = '';
    try {
      logs.value = await loadContainerLogs(containerId, {
        tail: tail.value,
        timestamps: withTimestamps.value,
      });
    } catch (err) {
      error.value = err?.message || '获取容器日志失败';
      logs.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function startFollow(containerId) {
    if (!containerId) return;
    stopFollow();
    followError.value = '';
    followNotice.value = '';
    // 存量日志改由 SSE 的 backlog 提供，避免与已加载快照重复
    logs.value = null;
    followLines.value = [];
    following.value = true;

    const controller = new AbortController();
    abortController = controller;
    const params = new URLSearchParams();
    params.set('tail', String(tail.value));
    if (withTimestamps.value) params.set('timestamps', 'true');

    try {
      const response = await fetch(
        `${getApiBase()}${API_PREFIX}/containers/${encodeURIComponent(containerId)}/logs/stream?${params.toString()}`,
        {
          method: 'GET',
          headers: { ...getAuthHeaders({ includeCsrf: false }) },
          credentials: 'include',
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
          const data = await response.json();
          message = data?.msg || message;
        } catch {
          // 非 JSON 响应，保留默认提示
        }
        throw new Error(message);
      }

      const reader = response.body.getReader();
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
          let eventType = 'log';
          let data = '';
          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) data = line.slice(6);
          }
          if (eventType === 'log') {
            for (const text of data.split('\n')) appendFollowLine(text);
            continue;
          }
          if (eventType === 'error') {
            let message = '跟随日志失败';
            try {
              message = JSON.parse(data)?.msg || message;
            } catch {
              message = data || message;
            }
            followError.value = message;
            controller.abort();
            break;
          }
        }
      }
    } catch (err) {
      if (err?.name !== 'AbortError') {
        followError.value = err?.message || '跟随日志失败';
      }
    } finally {
      if (abortController === controller) abortController = null;
      following.value = false;
      // 非用户主动停止且无报错：服务端正常收尾（达到时长/行数上限）
      if (!controller.signal.aborted && !followError.value) {
        followNotice.value = '跟随已结束（达到时长或行数上限），可再次点击「跟随」继续';
      }
    }
  }

  return {
    logs,
    lines,
    lineCount,
    truncated,
    loading,
    error,
    tail,
    withTimestamps,
    isEmpty,
    following,
    followError,
    followNotice,
    setScrollHandler,
    reset,
    refresh,
    startFollow,
    stopFollow,
  };
}
