import { ref } from 'vue';

export const INITIAL_LOADING_DELAY_MS = 140;
export const INITIAL_LOADING_MIN_SHOW_MS = 220;

export function useInitialLoading({
  delayMs = INITIAL_LOADING_DELAY_MS,
  minShowMs = INITIAL_LOADING_MIN_SHOW_MS,
  timerFn = (fn, ms) => window.setTimeout(fn, ms),
  clearTimerFn = (id) => window.clearTimeout(id),
  nowFn = () => performance.now(),
  sleepFn = (ms) => new Promise((resolve) => timerFn(resolve, ms)),
} = {}) {
  const initialLoading = ref(false);
  let initialLoadingSeq = 0;
  let initialLoadingTimer = null;
  let initialLoadingShownAt = 0;

  function stopInitialLoadingTimer() {
    if (initialLoadingTimer !== null) {
      clearTimerFn(initialLoadingTimer);
      initialLoadingTimer = null;
    }
  }

  function startInitialLoading() {
    stopInitialLoadingTimer();
    const seq = ++initialLoadingSeq;
    initialLoadingShownAt = 0;
    initialLoadingTimer = timerFn(() => {
      if (seq !== initialLoadingSeq) return;
      initialLoading.value = true;
      initialLoadingShownAt = nowFn();
    }, delayMs);
    return seq;
  }

  async function stopInitialLoading(seq) {
    if (seq !== initialLoadingSeq) return;
    stopInitialLoadingTimer();
    if (!initialLoading.value) return;

    const elapsed = nowFn() - (initialLoadingShownAt || nowFn());
    const remain = minShowMs - elapsed;
    if (remain > 0) {
      await sleepFn(Math.ceil(remain));
    }
    if (seq !== initialLoadingSeq) return;
    initialLoading.value = false;
  }

  return {
    initialLoading,
    startInitialLoading,
    stopInitialLoading,
  };
}
