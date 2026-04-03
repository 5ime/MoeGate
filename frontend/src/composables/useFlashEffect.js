import { ref, onBeforeUnmount } from 'vue';

/**
 * 提取"操作成功后卡片短暂闪烁"的共用逻辑。
 * 支持同时跟踪多种 key（如 containerId、projectId、proxyName 等）。
 */
export function useFlashEffect(durationMs = 1150) {
  const flashKeys = ref({});
  let timers = {};

  function flash(key, value) {
    if (!key || !value) return;
    if (timers[key]) {
      window.clearTimeout(timers[key]);
    }
    flashKeys.value = { ...flashKeys.value, [key]: value };
    timers[key] = window.setTimeout(() => {
      const next = { ...flashKeys.value };
      delete next[key];
      flashKeys.value = next;
      delete timers[key];
    }, durationMs);
  }

  function isFlashing(key, value) {
    return flashKeys.value[key] === value;
  }

  onBeforeUnmount(() => {
    for (const t of Object.values(timers)) {
      window.clearTimeout(t);
    }
    timers = {};
  });

  return { flash, isFlashing };
}
