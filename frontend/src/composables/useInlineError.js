import { ref, onBeforeUnmount } from 'vue';

/**
 * 提取"行内错误提示 + 自动清除"的共用逻辑。
 */
export function useInlineError(clearAfterMs = 4500) {
  const errorKey = ref('');
  const errorText = ref('');
  let timer = null;

  function setError(key, message) {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    errorKey.value = key;
    errorText.value = message;
    timer = window.setTimeout(() => {
      errorKey.value = '';
      errorText.value = '';
      timer = null;
    }, clearAfterMs);
  }

  function clearError() {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    errorKey.value = '';
    errorText.value = '';
  }

  function matchesKey(key) {
    return errorText.value && errorKey.value === key;
  }

  onBeforeUnmount(() => {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
  });

  return { errorKey, errorText, setError, clearError, matchesKey };
}
