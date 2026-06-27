import { computed, onMounted, onUnmounted, provide, watch } from 'vue';
import { storeToRefs } from 'pinia';
import ContainersTab from '../components/tabs/ContainersTab.vue';
import CreateTab from '../components/tabs/CreateTab.vue';
import FrpTab from '../components/tabs/FrpTab.vue';
import ImagesTab from '../components/tabs/ImagesTab.vue';
import NetworksTab from '../components/tabs/NetworksTab.vue';
import SystemTab from '../components/tabs/SystemTab.vue';
import { onUnauthorized } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { useContainersStore } from '../stores/containersStore';
import { useFrpStore } from '../stores/frpStore';
import { useImagesStore } from '../stores/imagesStore';
import { useNetworksStore } from '../stores/networksStore';
import { useSystemStore } from '../stores/systemStore';
import { useUiStore } from '../stores/uiStore';
import { useAppAuth } from './useAppAuth';
import { useInitialLoading } from './useInitialLoading';
import { usePreferencesModals } from './usePreferencesModals';
import { useTabNavigation } from './useTabNavigation';

const TABS = [
  { key: 'containers', label: '容器', desc: '容器与 Compose 管理' },
  { key: 'create', label: '创建', desc: '快速创建与高级参数' },
  { key: 'images', label: '镜像', desc: '受管镜像与拉取清理' },
  { key: 'networks', label: '网络', desc: '受管容器网络与占用状态' },
  { key: 'frp', label: 'FRP', desc: '内网穿透与健康检查' },
  { key: 'system', label: '系统', desc: '运行状态与分布式信息' },
];

export function useAppShell() {
  const authStore = useAuthStore();
  const uiStore = useUiStore();
  const containersStore = useContainersStore();
  const imagesStore = useImagesStore();
  const networksStore = useNetworksStore();
  const frpStore = useFrpStore();
  const systemStore = useSystemStore();
  const { message, messageType } = storeToRefs(uiStore);
  const { containers, stats: containerStats } = storeToRefs(containersStore);

  const TAB_LOADERS = {
    containers: () => systemStore.refreshContainersPanel(),
    images: () => imagesStore.refreshImagesPanel(),
    networks: () => networksStore.refreshNetworksPanel(),
    create: async () => {},
    frp: () => frpStore.loadFrpPanel(),
    system: () => systemStore.loadSystemPanel(),
  };

  const TAB_COMPONENT_MAP = {
    containers: ContainersTab,
    images: ImagesTab,
    networks: NetworksTab,
    create: CreateTab,
    frp: FrpTab,
    system: SystemTab,
  };

  const loggedIn = computed(() => authStore.isLoggedIn());

  const {
    activeTab,
    activeTabKey,
    tabNavEl,
    tabIndicatorStyle,
    normalizeTabKey,
    getPollIntervalMs,
    stopAutoRefresh,
    startAutoRefresh,
    runTabLoader,
    setTabEl,
    updateTabIndicator,
    onHashChange,
    initTabFromHash,
    updateHashForTab,
    switchTab,
  } = useTabNavigation({
    loggedIn,
    tabLoaders: TAB_LOADERS,
    tabs: TABS,
  });

  const { initialLoading, startInitialLoading, stopInitialLoading } = useInitialLoading();

  const auth = useAppAuth({
    getPollIntervalMs,
    startAutoRefresh,
    stopAutoRefresh,
    runTabLoader,
    startInitialLoading,
    stopInitialLoading,
  });

  const preferences = usePreferencesModals();

  const activeTabComponent = computed(
    () => TAB_COMPONENT_MAP[normalizeTabKey(activeTabKey.value)] || ContainersTab,
  );

  const activeTabProps = computed(() => {
    if (activeTabKey.value === 'containers') {
      return {
        containers: containers.value,
        total: containerStats.value.total,
        running: containerStats.value.running,
      };
    }
    return {};
  });

  provide('switchTab', switchTab);
  provide('openImageSourcePreferences', preferences.openImageSourcePreferences);
  provide('openNetworkingPreferences', preferences.openNetworkingPreferences);
  provide('openSystemPreferences', preferences.openSystemPreferences);

  watch(
    activeTabKey,
    (tabKey) => {
      updateHashForTab(tabKey, { replace: !window.location.hash });
    },
  );

  watch(activeTabKey, async () => {
    updateTabIndicator();
  });

  const handleWindowResize = () => updateTabIndicator();

  onMounted(async () => {
    onUnauthorized(async () => {
      if (!loggedIn.value) return;
      await authStore.logout();
      uiStore.showMessage('登录已过期，请重新登录', 'warning');
    });

    window.addEventListener('resize', handleWindowResize);
    auth.syncRuntimeSettings();
    auth.authApiBase.value = auth.runtimeApiBase.value;
    initTabFromHash();
    window.addEventListener('hashchange', onHashChange);
    await authStore.restoreSession();
    if (!loggedIn.value) return;
    const loadSeq = startInitialLoading();
    try {
      await auth.loadPersistedWebUiSettings();
    } catch (error) {
      uiStore.showMessage(error.message || '加载持久化设置失败，已使用本地设置', 'warning');
    }
    auth.syncRuntimeSettings();
    await runTabLoader(activeTabKey.value);
    startAutoRefresh();
    await stopInitialLoading(loadSeq);
    updateTabIndicator();
  });

  onUnmounted(() => {
    stopAutoRefresh();
    window.removeEventListener('hashchange', onHashChange);
    window.removeEventListener('resize', handleWindowResize);
  });

  return {
    currentYear: new Date().getFullYear(),
    tabs: TABS,
    activeTab,
    activeTabKey,
    message,
    messageType,
    loggedIn,
    tabNavEl,
    tabIndicatorStyle,
    setTabEl,
    switchTab,
    activeTabComponent,
    activeTabProps,
    initialLoading,
    ...auth,
    ...preferences,
  };
}
