import { computed, ref } from 'vue';
import { useUiStore } from '../stores/uiStore';
import {
  downloadTrafficCapture,
  loadTrafficStatus,
  loadTrafficSummary,
  startTrafficCapture,
  stopTrafficCapture,
} from '../stores/trafficStore';

export function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return '0 B';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(2)} MB`;
}

export function useTrafficForensics() {
  const uiStore = useUiStore();

  const status = ref(null);
  const summary = ref(null);
  const message = ref('');
  const loadingStatus = ref(false);
  const loadingSummary = ref(false);
  const pendingAction = ref('');

  const parsed = computed(() => summary.value?.summary || null);
  const files = computed(() => status.value?.files || []);
  const hasFiles = computed(() => files.value.length > 0);

  function reset() {
    status.value = null;
    summary.value = null;
    message.value = '';
    pendingAction.value = '';
  }

  async function refreshStatus(containerId) {
    if (!containerId) return;
    loadingStatus.value = true;
    try {
      status.value = await loadTrafficStatus(containerId);
    } catch (error) {
      message.value = error.message || '获取取证状态失败';
    } finally {
      loadingStatus.value = false;
    }
  }

  async function loadSummary(containerId) {
    if (!containerId) return;
    loadingSummary.value = true;
    try {
      summary.value = await loadTrafficSummary(containerId);
      message.value = summary.value?.message || '';
    } catch (error) {
      message.value = error.message || '生成取证摘要失败';
    } finally {
      loadingSummary.value = false;
    }
  }

  async function toggleCapture(containerId, action) {
    if (!containerId) return;
    pendingAction.value = action;
    try {
      if (action === 'start') {
        await startTrafficCapture(containerId);
        uiStore.showMessage('流量取证已开启（仅本次运行有效）', 'success');
      } else {
        await stopTrafficCapture(containerId);
        uiStore.showMessage('流量取证已停止，已落盘 pcap 保留', 'success');
      }
      await refreshStatus(containerId);
    } catch (error) {
      uiStore.showMessage(error.message || '操作失败', 'error');
    } finally {
      pendingAction.value = '';
    }
  }

  async function download(containerId, filename) {
    pendingAction.value = filename;
    try {
      await downloadTrafficCapture(containerId, filename);
    } catch (error) {
      uiStore.showMessage(error.message || '下载失败', 'error');
    } finally {
      pendingAction.value = '';
    }
  }

  return {
    status,
    summary,
    parsed,
    files,
    hasFiles,
    message,
    loadingStatus,
    loadingSummary,
    pendingAction,
    reset,
    refreshStatus,
    loadSummary,
    toggleCapture,
    download,
  };
}
