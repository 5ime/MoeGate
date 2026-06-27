import { computed, nextTick, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { apiRequest, getApiBase, setApiBase } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { useUiStore } from '../stores/uiStore';
import { useConfirmAction } from './useConfirmAction';
import { DEFAULT_POLL_INTERVAL_MS, POLL_STORAGE_KEY } from './useTabNavigation';

export function useAppAuth({
  getPollIntervalMs,
  startAutoRefresh,
  stopAutoRefresh,
  runTabLoader,
  startInitialLoading,
  stopInitialLoading,
}) {
  const authStore = useAuthStore();
  const uiStore = useUiStore();
  const { activeTab } = storeToRefs(uiStore);

  const authApiKey = ref('');
  const authApiKeyVisible = ref(false);
  const authApiBase = ref('');
  const loginPending = ref(false);
  const loginError = ref('');
  const loginOverlayRef = ref(null);
  const showSettings = ref(false);
  const settingsApiBase = ref('');
  const settingsPollSec = ref('');
  const runtimeApiBase = ref('');
  const runtimePollSec = ref('30');
  const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();

  const authStorageHint = computed(() => (
    '登录成功后 API Key 写入 HttpOnly Cookie，不会保存在 localStorage'
  ));
  const apiBaseDisplay = computed(() => runtimeApiBase.value || '当前站点');
  const pollDisplay = computed(() => `${runtimePollSec.value} 秒`);

  async function loadPersistedWebUiSettings() {
    const result = await apiRequest('/settings/webui');
    const persistedApiBase = String(result?.data?.api_base || '').trim();
    const persistedPollSec = Number.parseInt(String(result?.data?.poll_interval_sec || ''), 10);

    if (persistedApiBase) {
      setApiBase(persistedApiBase);
    }
    if (Number.isFinite(persistedPollSec) && persistedPollSec > 0) {
      localStorage.setItem(POLL_STORAGE_KEY, String(persistedPollSec * 1000));
    }
  }

  function syncRuntimeSettings() {
    const apiBase = getApiBase();
    runtimeApiBase.value = apiBase === window.location.origin ? '' : apiBase;
    runtimePollSec.value = String(Math.floor(getPollIntervalMs() / 1000));
  }

  function openSettings() {
    syncRuntimeSettings();
    settingsApiBase.value = runtimeApiBase.value;
    settingsPollSec.value = runtimePollSec.value;
    showSettings.value = true;
  }

  function closeSettings() {
    showSettings.value = false;
  }

  async function saveSettings() {
    try {
      const apiBaseText = String(settingsApiBase.value || '').trim();
      const secText = String(settingsPollSec.value || '').trim();
      let sec = Math.floor(DEFAULT_POLL_INTERVAL_MS / 1000);

      if (!secText) {
        localStorage.removeItem(POLL_STORAGE_KEY);
      } else {
        sec = Number.parseInt(secText, 10);
        if (!Number.isFinite(sec) || sec <= 0) {
          throw new Error('自动刷新间隔需为正整数秒');
        }
        localStorage.setItem(POLL_STORAGE_KEY, String(sec * 1000));
      }

      await apiRequest('/settings/webui', {
        method: 'PUT',
        body: {
          api_base: apiBaseText,
          poll_interval_sec: sec,
        },
      });

      setApiBase(apiBaseText);
      syncRuntimeSettings();
      startAutoRefresh();
      closeSettings();
      uiStore.showMessage('设置已保存并持久化到服务端', 'success');
    } catch (error) {
      uiStore.showMessage(error.message || '设置保存失败', 'error');
    }
  }

  async function onLogin() {
    const apiKey = authApiKey.value.trim();
    const apiBase = String(authApiBase.value || '').trim();
    if (!apiKey) {
      loginError.value = '请输入 API Key';
      uiStore.showMessage(loginError.value, 'error');
      await nextTick();
      loginOverlayRef.value?.focusApiKey();
      return;
    }

    loginError.value = '';
    loginPending.value = true;
    const loadSeq = startInitialLoading();
    try {
      setApiBase(apiBase);
      syncRuntimeSettings();
      await authStore.login(apiKey);
      await loadPersistedWebUiSettings();
      syncRuntimeSettings();
      authApiKey.value = '';
      authApiKeyVisible.value = false;
      uiStore.showMessage('登录成功', 'success');
      await runTabLoader(activeTab.value);
      startAutoRefresh();
    } catch (error) {
      loginError.value = error.message || 'API Key 验证失败';
      uiStore.showMessage(loginError.value, 'error');
      await nextTick();
      loginOverlayRef.value?.focusApiKey();
    } finally {
      await stopInitialLoading(loadSeq);
      loginPending.value = false;
    }
  }

  function onApiKeyInput() {
    if (loginError.value) loginError.value = '';
  }

  async function performLogout() {
    stopAutoRefresh();
    await authStore.logout();
    uiStore.showMessage('已退出登录', 'success');
  }

  function onLogout() {
    requestConfirm(
      '退出登录',
      '确定退出登录？当前会话将被清除。',
      performLogout,
      true,
    );
  }

  return {
    apiBaseDisplay,
    authApiBase,
    authApiKey,
    authApiKeyVisible,
    authStorageHint,
    closeSettings,
    confirmModal,
    loadPersistedWebUiSettings,
    loginError,
    loginOverlayRef,
    loginPending,
    onApiKeyInput,
    onCancelConfirm,
    onConfirm,
    onLogin,
    onLogout,
    openSettings,
    pollDisplay,
    runtimeApiBase,
    runtimePollSec,
    saveSettings,
    settingsApiBase,
    settingsPollSec,
    showSettings,
    syncRuntimeSettings,
  };
}
