import { computed, nextTick, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../stores/uiStore';

export const DEFAULT_POLL_INTERVAL_MS = 30000;
export const POLL_STORAGE_KEY = 'pollIntervalMs';
export const DEFAULT_TAB_KEY = 'containers';

export function useTabNavigation({
  loggedIn,
  tabLoaders,
  tabs,
}) {
  const uiStore = useUiStore();
  const { activeTab } = storeToRefs(uiStore);
  const validTabKeys = new Set(tabs.map((tab) => tab.key));
  let pollTimerId = null;

  const tabNavEl = ref(null);
  const tabEls = ref({});
  const tabIndicatorStyle = ref({
    opacity: 0,
    left: '0px',
    width: '0px',
    height: '38px',
  });

  const activeTabMeta = computed(() => tabs.find((tab) => tab.key === activeTab.value) || tabs[0]);

  function normalizeTabKey(tabKey) {
    return validTabKeys.has(tabKey) ? tabKey : DEFAULT_TAB_KEY;
  }

  function getTabFromHash() {
    return normalizeTabKey(window.location.hash.replace(/^#/, ''));
  }

  function updateHashForTab(tabKey, { replace = false } = {}) {
    const nextHash = `#${normalizeTabKey(tabKey)}`;
    if (window.location.hash === nextHash) return;
    if (replace) {
      const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
      window.history.replaceState(null, '', nextUrl);
      return;
    }
    window.location.hash = nextHash;
  }

  function getPollIntervalMs() {
    const raw = Number.parseInt(localStorage.getItem(POLL_STORAGE_KEY) || `${DEFAULT_POLL_INTERVAL_MS}`, 10);
    if (!Number.isFinite(raw) || raw <= 0) return DEFAULT_POLL_INTERVAL_MS;
    return raw;
  }

  function stopAutoRefresh() {
    if (pollTimerId !== null) {
      window.clearInterval(pollTimerId);
      pollTimerId = null;
    }
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    if (!loggedIn.value) return;
    pollTimerId = window.setInterval(() => {
      refreshActiveTab();
    }, getPollIntervalMs());
  }

  async function runTabLoader(tabKey) {
    if (!loggedIn.value) return;
    const loader = tabLoaders[normalizeTabKey(tabKey)] || tabLoaders[DEFAULT_TAB_KEY];
    try {
      await loader();
    } catch (error) {
      uiStore.showMessage(error.message || '标签页加载失败', 'error');
    }
  }

  async function activateTab(tabKey, { syncHash = true } = {}) {
    const nextTabKey = normalizeTabKey(tabKey);
    uiStore.setActiveTab(nextTabKey);
    if (syncHash) updateHashForTab(nextTabKey);
    await runTabLoader(nextTabKey);
  }

  async function switchTab(tabKey) {
    await activateTab(tabKey);
  }

  function setTabEl(key, el) {
    if (!key) return;
    if (el) tabEls.value[key] = el;
  }

  function updateTabIndicator() {
    nextTick(() => {
      const nav = tabNavEl.value;
      const el = tabEls.value?.[activeTab.value];
      if (!nav || !el) return;

      const width = el.offsetWidth;
      const height = el.offsetHeight;
      if (!Number.isFinite(width) || width <= 0) return;

      tabIndicatorStyle.value = {
        opacity: 1,
        left: `${el.offsetLeft}px`,
        width: `${width}px`,
        height: `${height}px`,
      };
    });
  }

  async function refreshActiveTab() {
    await runTabLoader(activeTab.value);
  }

  async function onHashChange() {
    const nextTabKey = getTabFromHash();
    if (nextTabKey === activeTab.value) return;
    await activateTab(nextTabKey, { syncHash: false });
  }

  function initTabFromHash() {
    uiStore.setActiveTab(getTabFromHash());
    updateHashForTab(activeTab.value, {
      replace:
        !window.location.hash
        || normalizeTabKey(window.location.hash.replace(/^#/, '')) !== window.location.hash.replace(/^#/, ''),
    });
  }

  return {
    activeTab: activeTabMeta,
    activeTabKey: activeTab,
    tabNavEl,
    tabEls,
    tabIndicatorStyle,
    normalizeTabKey,
    getTabFromHash,
    updateHashForTab,
    getPollIntervalMs,
    stopAutoRefresh,
    startAutoRefresh,
    runTabLoader,
    activateTab,
    switchTab,
    setTabEl,
    updateTabIndicator,
    refreshActiveTab,
    onHashChange,
    initTabFromHash,
  };
}
