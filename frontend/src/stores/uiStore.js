import { ref } from 'vue';
import { defineStore } from 'pinia';

export const useUiStore = defineStore('ui', () => {
  const activeTab = ref('containers');
  const message = ref('');
  const messageType = ref('success');
  const detailPanel = ref({
    open: false,
    title: '',
    payload: null,
  });

  const MESSAGE_TIMEOUT_BY_TYPE = {
    success: 2400,
    error: 4200,
    warning: 3400,
    info: 3000,
  };

  let messageTimer = null;

  function reset() {
    message.value = '';
    messageType.value = 'success';
    detailPanel.value.open = false;
    detailPanel.value.title = '';
    detailPanel.value.payload = null;
  }

  function setActiveTab(tabKey) {
    activeTab.value = tabKey;
  }

  function showMessage(text, type = 'success', durationMs) {
    if (messageTimer !== null) {
      window.clearTimeout(messageTimer);
      messageTimer = null;
    }

    message.value = text;
    messageType.value = type;

    const timeout = Number.isFinite(durationMs)
      ? durationMs
      : (MESSAGE_TIMEOUT_BY_TYPE[type] ?? MESSAGE_TIMEOUT_BY_TYPE.info);

    messageTimer = window.setTimeout(() => {
      if (message.value === text) {
        message.value = '';
      }
      messageTimer = null;
    }, timeout);
  }

  function openDetailPanel(title, payload) {
    detailPanel.value.open = true;
    detailPanel.value.title = title;
    detailPanel.value.payload = payload;
  }

  function closeDetailPanel() {
    detailPanel.value.open = false;
    detailPanel.value.title = '';
    detailPanel.value.payload = null;
  }

  return {
    activeTab,
    message,
    messageType,
    detailPanel,
    reset,
    setActiveTab,
    showMessage,
    openDetailPanel,
    closeDetailPanel,
  };
});
