import { computed, nextTick, reactive, ref } from 'vue';
import { storeToRefs } from 'pinia';
import {
  createFrpProxy,
  deleteFrpProxy,
  loadFrpProxy,
  reloadFrpConfig,
  updateFrpProxy,
  useFrpStore,
} from '../stores/frpStore';
import { useUiStore } from '../stores/uiStore';
import { useConfirmAction, useFlashEffect, useInlineError } from './index';

export function useFrpTab() {
  const frpStore = useFrpStore();
  const uiStore = useUiStore();
  const { frp } = storeToRefs(frpStore);

  const form = reactive({
    name: '',
    localPort: '',
    remotePort: '',
    type: 'tcp',
    domain: '',
  });

  const editingName = ref('');
  const editForm = reactive({
    type: 'tcp',
    localPort: '',
    remotePort: '',
    domain: '',
  });
  const switchSaving = ref(false);
  const refreshing = ref(false);
  const proxyKeyword = ref('');
  const createPending = ref(false);
  const reloadPending = ref(false);
  const configPending = ref(false);
  const editPending = ref(false);
  const deletingName = ref('');
  const preferencesModal = ref(false);
  const createModal = ref(false);
  const preferencesLoading = ref(false);
  const preferencesSaving = ref(false);
  const adminPasswordSet = ref(false);
  const createInlineError = ref('');
  const editInlineError = ref('');
  const preferencesForm = reactive({
    serverAddr: '',
    serverPort: '7000',
    vhostHttpPort: '',
    adminIp: '127.0.0.1',
    adminPort: '7400',
    adminUser: '',
    adminPassword: '',
    useDomain: false,
    domainSuffix: '',
  });

  const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
  const { flash, isFlashing } = useFlashEffect();
  const { errorText: proxyErrorText, setError: setProxyError, matchesKey: matchesProxyKey } = useInlineError();

  const configModal = ref(false);

  const healthState = computed(() => {
    const health = frp.value.health || {};
    if (health.overallOk) {
      return { label: '状态良好' };
    }
    if (health.serverReachable === false || health.adminReachable === false) {
      return { label: '异常' };
    }
    return { label: '待检查' };
  });

  const filteredProxies = computed(() => {
    const list = frp.value.proxies || [];
    const kw = proxyKeyword.value.trim().toLowerCase();
    if (!kw) return list;
    return list.filter((proxy) => {
      const name = String(proxy.name || '').toLowerCase();
      const type = String(proxy.type || proxy.proxy_type || '').toLowerCase();
      const domain = String(proxy.domain || '').toLowerCase();
      const localPort = String(proxy.localPort ?? proxy.local_port ?? '');
      const remotePort = String(proxy.remotePort ?? proxy.remote_port ?? '');
      return name.includes(kw) || type.includes(kw) || domain.includes(kw) || localPort.includes(kw) || remotePort.includes(kw);
    });
  });

  function resetCreateForm() {
    form.name = '';
    form.localPort = '';
    form.remotePort = '';
    form.type = 'tcp';
    form.domain = '';
    createInlineError.value = '';
  }

  async function refresh() {
    try {
      refreshing.value = true;
      await frpStore.loadFrpPanel();
    } catch (error) {
      uiStore.showMessage(error.message || 'FRP 加载失败', 'error');
    } finally {
      refreshing.value = false;
    }
  }

  async function applySwitch(event) {
    switchSaving.value = true;
    try {
      await frpStore.saveFrpSettings(!!event.target.checked);
      uiStore.showMessage('FRP 开关已更新', 'success');
      await refresh();
    } catch (error) {
      uiStore.showMessage(error.message || '开关更新失败', 'error');
    } finally {
      switchSaving.value = false;
    }
  }

  function syncPreferencesFormFromStore() {
    preferencesForm.serverAddr = String(frp.value.settings.serverAddr || '');
    preferencesForm.serverPort = String(frp.value.settings.serverPort || 7000);
    preferencesForm.vhostHttpPort = frp.value.settings.vhostHttpPort == null ? '' : String(frp.value.settings.vhostHttpPort);
    preferencesForm.adminIp = String(frp.value.settings.adminIp || '127.0.0.1');
    preferencesForm.adminPort = String(frp.value.settings.adminPort || 7400);
    preferencesForm.adminUser = String(frp.value.settings.adminUser || '');
    preferencesForm.adminPassword = '';
    adminPasswordSet.value = !!frp.value.settings.adminPasswordSet;
    preferencesForm.useDomain = !!frp.value.settings.useDomain;
    preferencesForm.domainSuffix = String(frp.value.settings.domainSuffix || '');
  }

  async function openPreferences() {
    preferencesLoading.value = true;
    try {
      await frpStore.loadFrpSettings();
      syncPreferencesFormFromStore();
      preferencesModal.value = true;
    } catch (error) {
      uiStore.showMessage(error.message || '加载 FRP 偏好设置失败', 'error');
    } finally {
      preferencesLoading.value = false;
    }
  }

  function closePreferences() {
    preferencesModal.value = false;
  }

  async function savePreferences() {
    preferencesSaving.value = true;
    try {
      await frpStore.saveFrpPreferences(preferencesForm);
      uiStore.showMessage('FRP 偏好设置已保存', 'success');
      preferencesModal.value = false;
      await refresh();
    } catch (error) {
      uiStore.showMessage(error.message || '保存 FRP 偏好设置失败', 'error');
    } finally {
      preferencesSaving.value = false;
    }
  }

  async function submitProxy() {
    createPending.value = true;
    createInlineError.value = '';
    try {
      if (!form.name.trim() || !form.localPort) {
        uiStore.showMessage('请填写名称和本地端口', 'error');
        return;
      }
      const payload = {
        name: form.name.trim(),
        localPort: Number(form.localPort),
      };
      if (form.remotePort) payload.remotePort = Number(form.remotePort);
      if (form.type.trim()) payload.type = form.type.trim();
      if (form.domain.trim()) payload.domain = form.domain.trim();

      await createFrpProxy(payload);
      flash('proxy', payload.name);
      uiStore.showMessage('FRP 代理创建成功', 'success');
      resetCreateForm();
      createModal.value = false;
      await refresh();
    } catch (error) {
      createInlineError.value = error.message || '创建代理失败';
      uiStore.showMessage(error.message || '创建代理失败', 'error');
    } finally {
      createPending.value = false;
    }
  }

  async function reloadConfig() {
    reloadPending.value = true;
    try {
      await reloadFrpConfig();
      uiStore.showMessage('FRP 配置已重载', 'success');
      await refresh();
    } catch (error) {
      uiStore.showMessage(error.message || '重载失败', 'error');
    } finally {
      reloadPending.value = false;
    }
  }

  async function viewConfig() {
    if (!frp.value.enabled) return;
    configPending.value = true;
    try {
      await frpStore.loadFrpConfig();
      configModal.value = true;
      uiStore.showMessage('已获取 FRP 配置', 'success');
    } catch (error) {
      uiStore.showMessage(error.message || '获取配置失败', 'error');
    } finally {
      configPending.value = false;
    }
  }

  async function openEdit(proxyName) {
    editInlineError.value = '';
    try {
      const proxy = await loadFrpProxy(proxyName);
      if (!proxy) {
        uiStore.showMessage('未找到 FRP 代理详情', 'error');
        return;
      }
      editingName.value = proxy.name || proxyName;
      editForm.type = proxy.type || proxy.proxy_type || 'tcp';
      editForm.localPort = String(proxy.localPort ?? proxy.local_port ?? '');
      editForm.remotePort = String(proxy.remotePort ?? proxy.remote_port ?? '');
      const firstCustomDomain = Array.isArray(proxy.customDomains) ? proxy.customDomains[0] : '';
      editForm.domain = proxy.domain || firstCustomDomain || '';
    } catch (error) {
      uiStore.showMessage(error.message || '加载代理详情失败', 'error');
    }
  }

  function cancelEdit() {
    editingName.value = '';
    editForm.type = 'tcp';
    editForm.localPort = '';
    editForm.remotePort = '';
    editForm.domain = '';
  }

  async function saveEdit() {
    if (!editingName.value) return;
    editPending.value = true;
    editInlineError.value = '';
    try {
      const payload = {};
      if (editForm.type.trim()) payload.type = editForm.type.trim();
      if (editForm.localPort) payload.localPort = Number(editForm.localPort);
      if (editForm.remotePort) payload.remotePort = Number(editForm.remotePort);
      const typeLower = String(editForm.type || '').trim().toLowerCase();
      if (typeLower === 'http' || typeLower === 'https') {
        if (editForm.domain.trim()) payload.customDomains = [editForm.domain.trim()];
      }

      await updateFrpProxy(editingName.value, payload);
      flash('proxy', editingName.value);
      uiStore.showMessage('FRP 代理更新成功', 'success');
      cancelEdit();
      await refresh();
    } catch (error) {
      editInlineError.value = error.message || '更新代理失败';
      uiStore.showMessage(error.message || '更新代理失败', 'error');
    } finally {
      editPending.value = false;
    }
  }

  async function removeProxy(proxyName) {
    requestConfirm('删除代理', `确定要删除代理 ${proxyName} 吗？`, async () => {
      deletingName.value = proxyName;
      try {
        await deleteFrpProxy(proxyName);
        if (editingName.value === proxyName) {
          cancelEdit();
        }
        uiStore.showMessage('FRP 代理删除成功', 'success');
        await refresh();
      } catch (error) {
        setProxyError(`proxy:${proxyName}`, error.message || '删除代理失败');
        uiStore.showMessage(error.message || '删除代理失败', 'error');
      } finally {
        deletingName.value = '';
      }
    }, true);
  }

  return {
    adminPasswordSet,
    applySwitch,
    cancelEdit,
    closePreferences,
    configModal,
    configPending,
    confirmModal,
    createInlineError,
    createModal,
    createPending,
    deletingName,
    editForm,
    editInlineError,
    editPending,
    editingName,
    filteredProxies,
    flash,
    form,
    frp,
    healthState,
    isFlashing,
    matchesProxyKey,
    onCancelConfirm,
    onConfirm,
    openEdit,
    openPreferences,
    preferencesForm,
    preferencesLoading,
    preferencesModal,
    preferencesSaving,
    proxyErrorText,
    proxyKeyword,
    refresh,
    refreshing,
    reloadConfig,
    reloadPending,
    removeProxy,
    resetCreateForm,
    saveEdit,
    savePreferences,
    submitProxy,
    switchSaving,
    viewConfig,
  };
}
