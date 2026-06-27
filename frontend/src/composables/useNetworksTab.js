import { computed, inject, ref } from 'vue';
import { storeToRefs } from 'pinia';
import {
  createManagedNetwork,
  deleteManagedNetwork,
  loadManagedNetworkDetail,
  updateManagedNetwork,
  useNetworksStore,
} from '../stores/networksStore';
import { useUiStore } from '../stores/uiStore';
import { formatKeyValueLines, parseKeyValueLines, useConfirmAction, useFlashEffect, useInlineError } from './index';

function createEmptyForm() {
  return {
    name: '',
    driver: 'bridge',
    subnet: '',
    gateway: '',
    composeProjectId: '',
    internal: false,
    attachable: false,
    enableIpv6: false,
    labelsText: '',
  };
}

export function useNetworksTab() {
  const networksStore = useNetworksStore();
  const uiStore = useUiStore();
  const { networks: networksState } = storeToRefs(networksStore);

  const refreshing = ref(false);
  const saving = ref(false);
  const actionPending = ref(false);
  const detailLoading = ref(false);
  const networkingSettingsOpening = ref(false);
  const search = ref('');
  const usageFilter = ref('all');
  const formModal = ref({ open: false, mode: 'create', networkId: '', originalName: '' });
  const detailModal = ref({ open: false, title: '', data: null });
  const form = ref(createEmptyForm());
  const openNetworkingPreferences = inject('openNetworkingPreferences', null);

  const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
  const { flash, isFlashing } = useFlashEffect();
  const { errorText, setError, clearError, matchesKey } = useInlineError();

  const filterOptions = [
    { value: 'all', label: '全部' },
    { value: 'in-use', label: '占用中' },
    { value: 'idle', label: '空闲' },
    { value: 'compose', label: '已绑归属' },
  ];

  const networks = computed(() => {
    const keyword = String(search.value || '').trim().toLowerCase();
    return (networksState.value.items || []).filter((item) => {
      if (usageFilter.value === 'in-use' && !item?.is_in_use) return false;
      if (usageFilter.value === 'idle' && item?.is_in_use) return false;
      if (usageFilter.value === 'compose' && !item?.compose_project_id) return false;

      if (!keyword) return true;

      const text = [
        item?.name,
        item?.id,
        item?.driver,
        item?.subnet,
        item?.gateway,
        item?.compose_project_id,
        Object.keys(item?.labels || {}).join(' '),
        Object.values(item?.labels || {}).join(' '),
      ].join(' ').toLowerCase();

      return text.includes(keyword);
    });
  });

  function resetForm() {
    form.value = createEmptyForm();
  }

  function formatLabelLines(labels) {
    return formatKeyValueLines(labels);
  }

  function parseLabelLines(text) {
    return parseKeyValueLines(text, {
      allowColon: true,
      invalidLineMessage: (line) => `标签格式错误: ${line}`,
      emptyKeyMessage: (line) => `标签键不能为空: ${line}`,
    });
  }

  function validateLabelFormat() {
    const raw = String(form.value.labelsText || '').trim();
    if (!raw) {
      uiStore.showMessage('标签为空，默认只保留系统标签', 'info');
      return;
    }

    try {
      const labels = parseLabelLines(raw);
      uiStore.showMessage(`格式正确，共 ${Object.keys(labels).length} 项标签`, 'success');
    } catch (error) {
      uiStore.showMessage(error.message || '标签格式错误，请检查填写内容', 'error');
    }
  }

  function buildPayload() {
    return {
      name: String(form.value.name || '').trim(),
      driver: String(form.value.driver || 'bridge').trim() || 'bridge',
      subnet: String(form.value.subnet || '').trim() || null,
      gateway: String(form.value.gateway || '').trim() || null,
      compose_project_id: String(form.value.composeProjectId || '').trim() || null,
      internal: !!form.value.internal,
      attachable: !!form.value.attachable,
      enable_ipv6: !!form.value.enableIpv6,
      labels: parseLabelLines(form.value.labelsText),
    };
  }

  function openCreateModal() {
    clearError();
    formModal.value = { open: true, mode: 'create', networkId: '', originalName: '' };
    resetForm();
  }

  function openEditModal(network) {
    clearError();
    formModal.value = {
      open: true,
      mode: 'edit',
      networkId: network.id || network.name,
      originalName: network.name || '',
    };
    form.value = {
      name: String(network.name || ''),
      driver: String(network.driver || 'bridge'),
      subnet: String(network.subnet || ''),
      gateway: String(network.gateway || ''),
      composeProjectId: String(network.compose_project_id || ''),
      internal: !!network.internal,
      attachable: !!network.attachable,
      enableIpv6: !!network.enable_ipv6,
      labelsText: formatLabelLines(network.labels),
    };
  }

  function closeFormModal() {
    formModal.value = { open: false, mode: 'create', networkId: '', originalName: '' };
    resetForm();
  }

  function closeDetailModal() {
    detailModal.value = { open: false, title: '', data: null };
  }

  async function refresh() {
    try {
      refreshing.value = true;
      await networksStore.loadManagedNetworks();
    } catch (error) {
      uiStore.showMessage(error.message || '受管网络列表加载失败', 'error');
    } finally {
      refreshing.value = false;
    }
  }

  async function openNetworkingSettings() {
    if (networkingSettingsOpening.value) return;
    if (typeof openNetworkingPreferences !== 'function') {
      uiStore.showMessage('Compose 网络池入口不可用', 'error');
      return;
    }

    networkingSettingsOpening.value = true;
    try {
      await openNetworkingPreferences();
    } catch (error) {
      uiStore.showMessage(error.message || '打开 Compose 网络池失败', 'error');
    } finally {
      networkingSettingsOpening.value = false;
    }
  }

  async function submitForm() {
    try {
      clearError();
      saving.value = true;
      const payload = buildPayload();
      let result;
      if (formModal.value.mode === 'edit') {
        result = await updateManagedNetwork(formModal.value.networkId, payload);
      } else {
        result = await createManagedNetwork(payload);
      }
      await refresh();
      flash('network', result?.data?.id || result?.data?.name || payload.name);
      uiStore.showMessage(result?.msg || (formModal.value.mode === 'edit' ? '网络更新成功' : '网络创建成功'), 'success');
      closeFormModal();
    } catch (error) {
      setError('form', error.message || '网络保存失败');
      uiStore.showMessage(error.message || '网络保存失败', 'error');
    } finally {
      saving.value = false;
    }
  }

  async function openDetail(network) {
    try {
      clearError();
      detailLoading.value = true;
      detailModal.value = { open: true, title: '网络详情', data: null };
      const data = await loadManagedNetworkDetail(network.id || network.name);
      detailModal.value.data = data;
      flash('network', network.id || network.name);
    } catch (error) {
      closeDetailModal();
      setError(`network:${network.id || network.name}`, error.message || '加载网络详情失败');
      uiStore.showMessage(error.message || '加载网络详情失败', 'error');
    } finally {
      detailLoading.value = false;
    }
  }

  function confirmDelete(network) {
    requestConfirm(
      '删除受管网络',
      `确定要删除网络 ${network.name} 吗？该操作不可撤销。`,
      async () => {
        try {
          clearError();
          actionPending.value = true;
          const result = await deleteManagedNetwork(network.id || network.name);
          await refresh();
          uiStore.showMessage(result?.msg || '网络删除成功', 'success');
        } catch (error) {
          setError(`network:${network.id || network.name}`, error.message || '网络删除失败');
          uiStore.showMessage(error.message || '网络删除失败', 'error');
        } finally {
          actionPending.value = false;
        }
      },
      true,
    );
  }

  function shortId(value) {
    const text = String(value || '').trim();
    if (!text) return '-';
    if (text.length <= 24) return text;
    return `${text.slice(0, 12)}...${text.slice(-10)}`;
  }

  function formatLabelCount(labels) {
    return Object.keys(labels || {}).length;
  }

  function boolLabel(value) {
    return value ? '是' : '否';
  }

  function emptyStateText() {
    if (!networksState.value.stats.total) return '暂无受管网络';
    return '当前筛选条件下没有匹配的受管网络。';
  }

  return {
    refreshing,
    saving,
    actionPending,
    detailLoading,
    networkingSettingsOpening,
    search,
    usageFilter,
    formModal,
    detailModal,
    form,
    filterOptions,
    confirmModal,
    onConfirm,
    onCancelConfirm,
    isFlashing,
    errorText,
    matchesKey,
    networks,
    networksState,
    validateLabelFormat,
    openCreateModal,
    openEditModal,
    closeFormModal,
    closeDetailModal,
    refresh,
    openNetworkingSettings,
    submitForm,
    openDetail,
    confirmDelete,
    shortId,
    formatLabelCount,
    boolLabel,
    emptyStateText,
  };
}
