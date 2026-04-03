import { ref } from 'vue';

/**
 * 提取确认弹窗 + 异步操作的共用逻辑。
 * ContainersTab / FrpTab 各自维护了相同的 confirmModal 状态和 3 个方法，
 * 统一到此 composable 中消除重复。
 */
export function useConfirmAction() {
  const confirmModal = ref({
    open: false,
    title: '',
    message: '',
    danger: false,
    loading: false,
    action: null,
  });

  function requestConfirm(title, message, action, danger = false) {
    confirmModal.value = { open: true, title, message, danger, loading: false, action };
  }

  async function onConfirm() {
    if (!confirmModal.value.action) return;
    confirmModal.value.loading = true;
    try {
      await confirmModal.value.action();
    } finally {
      resetConfirm();
    }
  }

  function onCancelConfirm() {
    resetConfirm();
  }

  function resetConfirm() {
    confirmModal.value = { open: false, title: '', message: '', danger: false, loading: false, action: null };
  }

  return { confirmModal, requestConfirm, onConfirm, onCancelConfirm };
}
