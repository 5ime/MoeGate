<script setup>
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue';
import BaseModal from './components/BaseModal.vue';
import ContainersTab from './components/tabs/ContainersTab.vue';
import CreateTab from './components/tabs/CreateTab.vue';
import FrpTab from './components/tabs/FrpTab.vue';
import ImagesTab from './components/tabs/ImagesTab.vue';
import NetworksTab from './components/tabs/NetworksTab.vue';
import ImageSourcePreferencesModal from './components/system/ImageSourcePreferencesModal.vue';
import NetworkingPreferencesModal from './components/system/NetworkingPreferencesModal.vue';
import SystemTab from './components/tabs/SystemTab.vue';
import SystemPreferencesModal from './components/system/SystemPreferencesModal.vue';
import { API_PREFIX, apiRequest, getApiBase, setApiBase } from './api/client';
import {
  isLoggedIn,
  loadAlertPerfSettings,
  loadAlertWebhookSetting,
  loadFrpPanel,
  loadImageSourceSetting,
  loadNetworkingSetting,
  refreshImagesPanel,
  refreshNetworksPanel,
  loadSystemPanel,
  login,
  logout,
  refreshContainersPanel,
  saveAlertPerfSettings,
  saveAlertWebhookSetting,
  saveImageSourceSetting,
  saveNetworkingSetting,
  sendAlertWebhookTest,
  showMessage,
  store,
} from './stores/appStore';

const DEFAULT_POLL_INTERVAL_MS = 30000;
const POLL_STORAGE_KEY = 'pollIntervalMs';
const DEFAULT_TAB_KEY = 'containers';
const currentYear = new Date().getFullYear();

const tabs = [
  { key: 'containers', label: '容器', desc: '容器与 Compose 管理' },
  { key: 'create', label: '创建', desc: '快速创建与高级参数' },
  { key: 'images', label: '镜像', desc: '受管镜像与拉取清理' },
  { key: 'networks', label: '网络', desc: '受管容器网络与占用状态' },
  { key: 'frp', label: 'FRP', desc: '内网穿透与健康检查' },
  { key: 'system', label: '系统', desc: '运行状态与分布式信息' },
];

const tabLoaders = {
  containers: refreshContainersPanel,
  images: refreshImagesPanel,
  networks: refreshNetworksPanel,
  create: async () => {},
  frp: loadFrpPanel,
  system: loadSystemPanel,
};

const validTabKeys = new Set(tabs.map((tab) => tab.key));
const authApiKey = ref('');
const authApiBase = ref('');
const loginPending = ref(false);
const loginError = ref('');
const authApiKeyInput = ref(null);
const showSettings = ref(false);
const showImageSourcePreferences = ref(false);
const showNetworkingPreferences = ref(false);
const showSystemPreferences = ref(false);
const settingsApiBase = ref('');
const settingsPollSec = ref('');
const runtimeApiBase = ref('');
const runtimePollSec = ref('30');
const imageSourcePreferencesLoading = ref(false);
const imageSourcePreferencesSaving = ref(false);
const networkingPreferencesLoading = ref(false);
const networkingPreferencesSaving = ref(false);
const systemPreferencesLoading = ref(false);
const systemPreferencesSaving = ref(false);
const systemTestSending = ref(false);
const imageSourceInput = ref('');
const composeManagedSubnetPool = ref('172.30.0.0/16');
const composeManagedSubnetPrefix = ref('24');
const webhookUrl = ref('');
const webhookTimeout = ref('5');
const perfInterval = ref('300');
const cpuThreshold = ref('95');
const cpuIntervals = ref('3');
const memThreshold = ref('90');
const memIntervals = ref('3');
const cooldownSec = ref('900');
const initialLoading = ref(false);
// 初始加载遮罩：性能优先
// - 延迟显示：短任务不显示，避免闪烁与额外渲染
// - 最短展示：一旦显示，至少展示一小段时间，避免“闪一下”
// - 并发安全：多次触发时只以最后一次为准，避免竞态导致的错乱
let initialLoadingSeq = 0;
let initialLoadingTimer = null;
let initialLoadingShownAt = 0;
const INITIAL_LOADING_DELAY_MS = 140;
const INITIAL_LOADING_MIN_SHOW_MS = 220;

function stopInitialLoadingTimer() {
  if (initialLoadingTimer !== null) {
    window.clearTimeout(initialLoadingTimer);
    initialLoadingTimer = null;
  }
}

function startInitialLoading() {
  stopInitialLoadingTimer();
  const seq = ++initialLoadingSeq;
  initialLoadingShownAt = 0;
  // 延迟显示：只有在任务超过阈值时才真正把遮罩挂出来
  initialLoadingTimer = window.setTimeout(() => {
    if (seq !== initialLoadingSeq) return;
    initialLoading.value = true;
    initialLoadingShownAt = performance.now();
  }, INITIAL_LOADING_DELAY_MS);
  return seq;
}

async function stopInitialLoading(seq) {
  // 只允许最后一次触发关闭，避免并发 loader 抢状态
  if (seq !== initialLoadingSeq) return;
  stopInitialLoadingTimer();
  if (!initialLoading.value) return;

  const elapsed = performance.now() - (initialLoadingShownAt || performance.now());
  const remain = INITIAL_LOADING_MIN_SHOW_MS - elapsed;
  if (remain > 0) {
    await new Promise((r) => window.setTimeout(r, Math.ceil(remain)));
  }
  if (seq !== initialLoadingSeq) return;
  initialLoading.value = false;
}
let pollTimerId = null;

const loggedIn = computed(() => isLoggedIn());
const apiBaseDisplay = computed(() => runtimeApiBase.value || '当前站点');
const pollDisplay = computed(() => `${runtimePollSec.value} 秒`);
const activeTab = computed(() => tabs.find((tab) => tab.key === store.activeTab) || tabs[0]);
const tabComponentMap = {
  containers: ContainersTab,
  images: ImagesTab,
  networks: NetworksTab,
  create: CreateTab,
  frp: FrpTab,
  system: SystemTab,
};

const activeTabComponent = computed(() => tabComponentMap[normalizeTabKey(store.activeTab)] || ContainersTab);

const tabNavEl = ref(null);
const tabEls = ref({});
const tabIndicatorStyle = ref({
  opacity: 0,
  left: '0px',
  width: '0px',
  height: '38px',
});
const handleWindowResize = () => updateTabIndicator();

const activeTabProps = computed(() => {
  if (store.activeTab === 'containers') {
    return {
      containers: store.containers,
      total: store.stats.total,
      running: store.stats.running,
    };
  }
  return {};
});

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

function openSettings() {
  syncRuntimeSettings();
  settingsApiBase.value = runtimeApiBase.value;
  settingsPollSec.value = runtimePollSec.value;
  showSettings.value = true;
}

function closeSettings() {
  showSettings.value = false;
}

async function openSystemPreferences() {
  if (systemPreferencesLoading.value) return;

  systemPreferencesLoading.value = true;
  try {
    const [webhook, perf] = await Promise.all([
      loadAlertWebhookSetting(),
      loadAlertPerfSettings(),
    ]);
    webhookUrl.value = String(webhook?.webhookUrl || '');
    webhookTimeout.value = String(webhook?.webhookTimeout ?? 5);
    perfInterval.value = String(perf?.performanceLogInterval ?? 300);
    cpuThreshold.value = String(perf?.alertCpuThreshold ?? 95);
    cpuIntervals.value = String(perf?.alertCpuSustainedIntervals ?? 3);
    memThreshold.value = String(perf?.alertMemThreshold ?? 90);
    memIntervals.value = String(perf?.alertMemSustainedIntervals ?? 3);
    cooldownSec.value = String(perf?.alertCooldownSec ?? 900);
    showSystemPreferences.value = true;
  } catch (error) {
    showMessage(error.message || '加载系统偏好失败', 'error');
  } finally {
    systemPreferencesLoading.value = false;
  }
}

async function openImageSourcePreferences() {
  if (imageSourcePreferencesLoading.value) return;

  imageSourcePreferencesLoading.value = true;
  try {
    const imageSource = await loadImageSourceSetting();
    imageSourceInput.value = String(imageSource || '');
    showImageSourcePreferences.value = true;
  } catch (error) {
    showMessage(error.message || '加载镜像源设置失败', 'error');
  } finally {
    imageSourcePreferencesLoading.value = false;
  }
}

function closeImageSourcePreferences() {
  showImageSourcePreferences.value = false;
}

async function saveImageSourcePreferences() {
  imageSourcePreferencesSaving.value = true;
  try {
    const result = await saveImageSourceSetting(imageSourceInput.value);
    imageSourceInput.value = store.settings.imageSource;
    showMessage(String(result?.msg || '镜像源设置已保存'), 'success');
    closeImageSourcePreferences();
  } catch (error) {
    showMessage(error.message || '保存镜像源设置失败', 'error');
  } finally {
    imageSourcePreferencesSaving.value = false;
  }
}

async function openNetworkingPreferences() {
  if (networkingPreferencesLoading.value) return;

  networkingPreferencesLoading.value = true;
  try {
    const networking = await loadNetworkingSetting();
    composeManagedSubnetPool.value = String(networking?.composeManagedSubnetPool || store.settings.networking.composeManagedSubnetPool || '172.30.0.0/16');
    composeManagedSubnetPrefix.value = String(networking?.composeManagedSubnetPrefix ?? store.settings.networking.composeManagedSubnetPrefix ?? 24);
    showNetworkingPreferences.value = true;
  } catch (error) {
    showMessage(error.message || '加载 Compose 网络池设置失败', 'error');
  } finally {
    networkingPreferencesLoading.value = false;
  }
}

function closeNetworkingPreferences() {
  showNetworkingPreferences.value = false;
}

async function saveNetworkingPreferences() {
  networkingPreferencesSaving.value = true;
  try {
    const result = await saveNetworkingSetting(composeManagedSubnetPool.value, composeManagedSubnetPrefix.value);
    composeManagedSubnetPool.value = String(store.settings.networking.composeManagedSubnetPool || '172.30.0.0/16');
    composeManagedSubnetPrefix.value = String(store.settings.networking.composeManagedSubnetPrefix ?? 24);
    showMessage(String(result?.msg || 'Compose 网络池设置已保存'), 'success');
    closeNetworkingPreferences();
  } catch (error) {
    showMessage(error.message || '保存 Compose 网络池设置失败', 'error');
  } finally {
    networkingPreferencesSaving.value = false;
  }
}

function closeSystemPreferences() {
  showSystemPreferences.value = false;
}

async function saveSystemPreferences() {
  systemPreferencesSaving.value = true;
  try {
    const [webhookResult, perfResult] = await Promise.all([
      saveAlertWebhookSetting(webhookUrl.value, webhookTimeout.value),
      saveAlertPerfSettings({
        performanceLogInterval: Number(perfInterval.value),
        alertCpuThreshold: Number(cpuThreshold.value),
        alertCpuSustainedIntervals: Number(cpuIntervals.value),
        alertMemThreshold: Number(memThreshold.value),
        alertMemSustainedIntervals: Number(memIntervals.value),
        alertCooldownSec: Number(cooldownSec.value),
      }),
    ]);
    const msg = String((perfResult?.msg || webhookResult?.msg) || '系统偏好已保存');
    showMessage(msg, 'success');
    closeSystemPreferences();
    if (store.activeTab === 'system') {
      await loadSystemPanel().catch(() => {});
    }
  } catch (error) {
    showMessage(error.message || '保存系统偏好失败', 'error');
  } finally {
    systemPreferencesSaving.value = false;
  }
}

async function sendSystemWebhookTest() {
  systemTestSending.value = true;
  try {
    const result = await sendAlertWebhookTest();
    showMessage(String(result?.msg || '测试消息已发送'), 'success');
  } catch (error) {
    showMessage(error.message || '发送测试消息失败', 'error');
  } finally {
    systemTestSending.value = false;
  }
}

provide('openImageSourcePreferences', openImageSourcePreferences);
provide('openNetworkingPreferences', openNetworkingPreferences);
provide('openSystemPreferences', openSystemPreferences);

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
    showMessage('设置已保存并持久化到服务端', 'success');
  } catch (error) {
    showMessage(error.message || '设置保存失败', 'error');
  }
}

async function verifyApiKey(apiKey) {
  const response = await fetch(`${getApiBase()}${API_PREFIX}/status`, {
    method: 'GET',
    headers: { 'X-API-Key': apiKey },
  });
  if (!response.ok) {
    const text = await response.text();
    let message = `HTTP ${response.status}`;
    try {
      const payload = text ? JSON.parse(text) : {};
      message = payload?.msg || payload?.message || message;
    } catch {
      message = text || message;
    }
    throw new Error(message);
  }
}

async function runTabLoader(tabKey) {
  if (!loggedIn.value) return;
  const loader = tabLoaders[normalizeTabKey(tabKey)] || tabLoaders[DEFAULT_TAB_KEY];
  try {
    await loader();
  } catch (error) {
    showMessage(error.message || '标签页加载失败', 'error');
  }
}

async function activateTab(tabKey, { syncHash = true } = {}) {
  const nextTabKey = normalizeTabKey(tabKey);
  store.activeTab = nextTabKey;
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
    const el = tabEls.value?.[store.activeTab];
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
  await runTabLoader(store.activeTab);
}

async function onLogin() {
  const apiKey = authApiKey.value.trim();
  const apiBase = String(authApiBase.value || '').trim();
  if (!apiKey) {
    loginError.value = '请输入 API Key';
    showMessage(loginError.value, 'error');
    await nextTick();
    authApiKeyInput.value?.focus();
    return;
  }

  loginError.value = '';
  loginPending.value = true;
  const loadSeq = startInitialLoading();
  try {
    setApiBase(apiBase);
    syncRuntimeSettings();
    await verifyApiKey(apiKey);
    login(apiKey);
    await loadPersistedWebUiSettings();
    syncRuntimeSettings();
    authApiKey.value = '';
    showMessage('登录成功', 'success');
    await runTabLoader(store.activeTab);
    startAutoRefresh();
  } catch (error) {
    loginError.value = error.message || 'API Key 验证失败';
    showMessage(loginError.value, 'error');
    await nextTick();
    authApiKeyInput.value?.focus();
    authApiKeyInput.value?.select?.();
  } finally {
    await stopInitialLoading(loadSeq);
    loginPending.value = false;
  }
}

function onApiKeyInput() {
  if (loginError.value) loginError.value = '';
}

function onLogout() {
  stopAutoRefresh();
  logout();
  showMessage('已退出登录', 'success');
}

async function onHashChange() {
  const nextTabKey = getTabFromHash();
  if (nextTabKey === store.activeTab) return;
  await activateTab(nextTabKey, { syncHash: false });
}

watch(
  () => store.activeTab,
  (tabKey) => {
    updateHashForTab(tabKey, { replace: !window.location.hash });
  }
);

watch(() => store.activeTab, async () => {
  updateTabIndicator();
});

onMounted(async () => {
  window.addEventListener('resize', handleWindowResize);
  syncRuntimeSettings();
  authApiBase.value = runtimeApiBase.value;
  store.activeTab = getTabFromHash();
  updateHashForTab(store.activeTab, {
    replace:
      !window.location.hash ||
      normalizeTabKey(window.location.hash.replace(/^#/, '')) !== window.location.hash.replace(/^#/, ''),
  });
  window.addEventListener('hashchange', onHashChange);
  if (!loggedIn.value) return;
  const loadSeq = startInitialLoading();
  try {
    await loadPersistedWebUiSettings();
  } catch (error) {
    showMessage(error.message || '加载持久化设置失败，已使用本地设置', 'warning');
  }
  syncRuntimeSettings();
  await runTabLoader(store.activeTab);
  startAutoRefresh();
  await stopInitialLoading(loadSeq);
  updateTabIndicator();
});

onUnmounted(() => {
  stopAutoRefresh();
  window.removeEventListener('hashchange', onHashChange);
  window.removeEventListener('resize', handleWindowResize);
});
</script>

<template>
  <div class="relative min-h-screen px-4 py-6 md:px-6 md:py-8">
    <div class="pointer-events-none fixed inset-x-[-20%] top-[-30%] z-0 h-[380px] bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.75),rgba(255,255,255,0))]"></div>
    <div v-if="initialLoading" class="fixed inset-0 z-[9500] flex items-center justify-center bg-[radial-gradient(circle_at_50%_42%,rgba(255,255,255,0.18),rgba(255,255,255,0)_48%),linear-gradient(165deg,rgba(12,13,17,0.44),rgba(17,18,20,0.35))] backdrop-blur-[8px] saturate-[108%]" role="status" aria-live="polite" aria-label="正在加载">
      <div class="text-center">
        <div class="relative mx-auto h-[54px] w-[54px] max-md:h-[46px] max-md:w-[46px]" aria-hidden="true">
          <span class="absolute inset-0 rounded-full border-[1.5px] border-white/80 animate-[loadingRingSpin_1.45s_cubic-bezier(0.65,0,0.35,1)_infinite]"></span>
          <span class="absolute inset-[8px] rounded-full border-[1.2px] border-white/80 opacity-60 animate-[loadingRingSpin_1.85s_cubic-bezier(0.65,0,0.35,1)_infinite] [animation-direction:reverse]"></span>
          <span class="absolute left-1/2 top-1/2 h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/95 animate-[loadingCorePulse_1.05s_ease-in-out_infinite] max-md:h-[6px] max-md:w-[6px]"></span>
        </div>
        <p class="mt-[10px] whitespace-nowrap text-[12px] font-medium uppercase tracking-[0.16em] text-white/90 max-md:tracking-[0.12em]">正在准备控制台</p>
      </div>
    </div>

    <div id="authOverlay" v-show="!loggedIn" class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/30 p-5 backdrop-blur-md">
      <div class="login-panel w-full max-w-[500px] rounded-[22px] border border-slate-200/80 bg-white p-8 shadow-[0_10px_40px_-16px_rgba(10,12,18,0.2)]">
        <div class="mb-5 flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[linear-gradient(150deg,#0f1013,#2a2d33)] text-lg font-semibold text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]">M</div>
          <div>
            <div class="text-lg font-bold tracking-tight text-slate-900">MoeGate 控制台</div>
            <div class="text-[13px] text-slate-500">请输入 API Key 登录</div>
          </div>
        </div>
        <form id="loginForm" class="mb-2 mt-2 flex flex-col gap-3" @submit.prevent="onLogin">
          <label for="authApiBase" class="text-sm font-medium text-slate-900">API Base</label>
          <input
            id="authApiBase"
            v-model="authApiBase"
            type="text"
            placeholder="留空使用当前站点"
            :disabled="loginPending"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100"
          />
          <p class="-mt-1 text-xs leading-5 text-slate-500">分离部署首次访问时请先填写后端 API 地址；填写后会保存在当前浏览器。</p>
          <label for="authApiKey" class="text-sm font-medium text-slate-900">API Key</label>
          <input
            id="authApiKey"
            ref="authApiKeyInput"
            v-model="authApiKey"
            type="password"
            placeholder="粘贴后提交"
            required
            :disabled="loginPending"
            :class="[
              'w-full rounded-xl border bg-white px-4 py-3 text-sm text-slate-900 transition focus:outline-none focus:ring-4',
              loginError ? 'border-slate-300 focus:border-slate-500 focus:ring-slate-100' : 'border-slate-200 focus:border-slate-400 focus:ring-slate-100'
            ]"
            @input="onApiKeyInput"
          />
          <p v-if="loginError" class="-mt-1 text-xs text-rose-600">{{ loginError }}</p>
          <button type="submit" class="inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-6 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="loginPending">{{ loginPending ? '验证中...' : '登录' }}</button>
        </form>
        <div class="mt-2.5 text-center text-xs text-slate-400">API Key 仅保存在当前浏览器本地存储</div>
      </div>
    </div>

    <div class="relative z-[1] mx-auto max-w-[1260px] rounded-[24px] border border-slate-200 bg-white shadow-[0_8px_30px_-12px_rgba(10,12,18,0.15)]">
      <header class="border-b border-slate-100 px-6 py-6 md:px-8">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 class="text-[30px] font-semibold tracking-tight text-slate-900">MoeGate 控制台</h1>
            <p class="mt-1 text-sm text-slate-500">{{ activeTab.desc }}</p>
            <div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">API Base: {{ apiBaseDisplay }}</span>
              <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">自动刷新: {{ pollDisplay }}</span>
            </div>
          </div>
          <div class="flex w-full flex-wrap items-center gap-3 lg:w-auto">
            <button id="openSettingsBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="openSettings">设置</button>
            <button id="logoutBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="onLogout">退出登录</button>
          </div>
        </div>
      </header>

      <div class="tab-nav-wrap border-b border-slate-100 px-6 md:px-8">
        <div class="flex flex-wrap items-center justify-between gap-2 py-3">
          <div ref="tabNavEl" class="relative isolate flex gap-2 overflow-x-auto py-0">
          <div
            class="pointer-events-none absolute top-1/2 -z-10 rounded-[12px] border border-slate-300 bg-white shadow-[0_10px_24px_-18px_rgba(12,14,18,0.4)] transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :style="{ opacity: tabIndicatorStyle.opacity, left: tabIndicatorStyle.left, width: tabIndicatorStyle.width, height: tabIndicatorStyle.height, transform: 'translateY(-50%)' }"
            aria-hidden="true"
          ></div>
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :data-tab="tab.key"
            class="relative z-10 inline-flex h-[38px] items-center justify-center rounded-[12px] border border-transparent bg-transparent px-3.5 text-sm font-medium text-slate-500 transition hover:border-slate-200 hover:bg-slate-50 hover:text-slate-900"
            :class="store.activeTab === tab.key ? 'text-slate-900' : ''"
            :ref="(el) => setTabEl(tab.key, el)"
            @click="switchTab(tab.key)"
          >
            {{ tab.label }}
          </button>
          </div>
        </div>
      </div>

      <transition name="tab-page" mode="out-in">
        <div :key="store.activeTab" class="p-6 md:p-9">
          <component :is="activeTabComponent" v-bind="activeTabProps" />
        </div>
      </transition>
    </div>

    <footer class="mx-auto mt-6 max-w-[1260px] px-2 text-[11px] text-slate-500">
      <div class="flex flex-col gap-2 border-t border-slate-100 pt-3 md:flex-row md:items-center md:justify-between">
        <div class="text-center md:text-left">
          <div class="flex flex-wrap items-center justify-center gap-1.5 md:justify-start">
            <span class="font-medium">
              &copy; {{ currentYear }}
              <a
                href="https://github.com/5ime/moegate"
                target="_blank"
                rel="noreferrer"
                class="ml-1 underline-offset-2 hover:underline"
              >
                MoeGate
              </a>
            </span>
            <span>·</span>
            <span class="uppercase tracking-[0.12em] text-[10px]">Console</span>
            <span
              v-if="store.systemStatus?.app_version"
              class="ml-1 inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600"
            >v{{ store.systemStatus.app_version }}</span>
          </div>
          <p class="mt-1 text-[10px] text-slate-500/80">
            轻量级 Docker 容器控制台，专注简单、稳定、可视化。
          </p>
        </div>
        <div class="flex flex-col items-center gap-1 text-[10px] md:items-end md:text-right">
          <div class="flex flex-wrap items-center justify-center gap-1.5 md:justify-end">
            <span class="font-medium">开发者</span>
            <span>·</span>
            <a
              href="https://5ime.cn"
              target="_blank"
              rel="noreferrer"
              class="underline-offset-2 hover:underline"
            >
              <span class="font-medium">iami233</span>
            </a>
          </div>
          <p class="text-[10px] text-slate-500/80">
            永远相信美好的事情即将发生
          </p>
        </div>
      </div>
    </footer>

    <BaseModal :visible="showSettings" title="偏好设置" icon="bolt" width="max-w-[720px]" close-text="取消" @close="closeSettings">
      <div class="space-y-4">
        <div class="rounded-2xl border border-slate-200 bg-white p-4">
          <div class="mb-3">
            <p class="text-xs font-semibold tracking-tight text-slate-900">API Base</p>
            <p class="mt-1 text-xs text-slate-500">前后端分离部署时填写；留空则使用当前站点。</p>
          </div>
          <label for="apiBaseInput" class="block text-xs font-medium text-slate-600">地址</label>
          <input
            id="apiBaseInput"
            v-model="settingsApiBase"
            type="text"
            placeholder="例如：http://127.0.0.1:8080"
            class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
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
            v-model="settingsPollSec"
            type="number"
            min="1"
            placeholder="默认 30"
            class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
          />
          <p class="mt-2 text-xs text-slate-500">留空将恢复默认值。</p>
        </div>
      </div>

      <template #footer>
          <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="closeSettings">取消</button>
          <button id="saveSettingsBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="saveSettings">保存设置</button>
      </template>
    </BaseModal>

    <ImageSourcePreferencesModal
      :visible="showImageSourcePreferences"
      :saving="imageSourcePreferencesSaving"
      v-model:image-source="imageSourceInput"
      @close="closeImageSourcePreferences"
      @save="saveImageSourcePreferences"
    />

    <NetworkingPreferencesModal
      :visible="showNetworkingPreferences"
      :saving="networkingPreferencesSaving"
      v-model:compose-managed-subnet-pool="composeManagedSubnetPool"
      v-model:compose-managed-subnet-prefix="composeManagedSubnetPrefix"
      @close="closeNetworkingPreferences"
      @save="saveNetworkingPreferences"
    />

    <SystemPreferencesModal
      :visible="showSystemPreferences"
      :saving="systemPreferencesSaving"
      :test-sending="systemTestSending"
      v-model:webhook-url="webhookUrl"
      v-model:webhook-timeout="webhookTimeout"
      v-model:perf-interval="perfInterval"
      v-model:cpu-threshold="cpuThreshold"
      v-model:cpu-intervals="cpuIntervals"
      v-model:mem-threshold="memThreshold"
      v-model:mem-intervals="memIntervals"
      v-model:cooldown-sec="cooldownSec"
      @close="closeSystemPreferences"
      @save="saveSystemPreferences"
      @send-test="sendSystemWebhookTest"
    />

    <Teleport to="body">
      <transition name="toast">
        <div
          v-if="store.message"
          class="toast-notification"
          :class="`toast-${store.messageType || 'info'}`"
        >
          <div class="toast-icon">
            <svg v-if="store.messageType === 'success'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <svg v-else-if="store.messageType === 'error'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            <svg v-else-if="store.messageType === 'warning'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <span class="toast-text">{{ store.message }}</span>
        </div>
      </transition>
    </Teleport>
  </div>
</template>
