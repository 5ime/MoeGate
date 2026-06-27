import { ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useSettingsStore } from '../stores/settingsStore';
import { useSystemStore } from '../stores/systemStore';
import { useUiStore } from '../stores/uiStore';

export function usePreferencesModals() {
  const settingsStore = useSettingsStore();
  const systemStore = useSystemStore();
  const uiStore = useUiStore();
  const { activeTab } = storeToRefs(uiStore);

  const showImageSourcePreferences = ref(false);
  const showNetworkingPreferences = ref(false);
  const showSystemPreferences = ref(false);
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
  const webhookUrlSet = ref(false);
  const webhookUrlMasked = ref('');
  const webhookUrlTouched = ref(false);
  const webhookTimeout = ref('5');

  async function openSystemPreferences() {
    if (systemPreferencesLoading.value) return;

    systemPreferencesLoading.value = true;
    try {
      const webhook = await settingsStore.loadAlertWebhookSetting();
      webhookUrl.value = String(webhook?.webhookUrl || '');
      webhookUrlSet.value = !!webhook?.webhookUrlSet;
      webhookUrlMasked.value = String(webhook?.webhookUrlMasked || '');
      webhookUrlTouched.value = false;
      webhookTimeout.value = String(webhook?.webhookTimeout ?? 5);
      showSystemPreferences.value = true;
    } catch (error) {
      uiStore.showMessage(error.message || '加载系统偏好失败', 'error');
    } finally {
      systemPreferencesLoading.value = false;
    }
  }

  function closeSystemPreferences() {
    showSystemPreferences.value = false;
  }

  async function saveSystemPreferences() {
    systemPreferencesSaving.value = true;
    try {
      const webhookResult = await settingsStore.saveAlertWebhookSetting(webhookUrl.value, webhookTimeout.value, {
        webhookUrlTouched: webhookUrlTouched.value,
      });
      const msg = String(webhookResult?.msg || '系统偏好已保存');
      uiStore.showMessage(msg, 'success');
      closeSystemPreferences();
      if (activeTab.value === 'system') {
        await systemStore.loadSystemPanel().catch(() => {});
      }
    } catch (error) {
      uiStore.showMessage(error.message || '保存系统偏好失败', 'error');
    } finally {
      systemPreferencesSaving.value = false;
    }
  }

  async function sendSystemWebhookTest() {
    systemTestSending.value = true;
    try {
      const result = await settingsStore.sendAlertWebhookTest();
      uiStore.showMessage(String(result?.msg || '测试消息已发送'), 'success');
    } catch (error) {
      uiStore.showMessage(error.message || '发送测试消息失败', 'error');
    } finally {
      systemTestSending.value = false;
    }
  }

  async function openImageSourcePreferences() {
    if (imageSourcePreferencesLoading.value) return;

    imageSourcePreferencesLoading.value = true;
    try {
      const imageSource = await settingsStore.loadImageSourceSetting();
      imageSourceInput.value = String(imageSource || '');
      showImageSourcePreferences.value = true;
    } catch (error) {
      uiStore.showMessage(error.message || '加载镜像源设置失败', 'error');
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
      const result = await settingsStore.saveImageSourceSetting(imageSourceInput.value);
      imageSourceInput.value = settingsStore.settings.imageSource;
      uiStore.showMessage(String(result?.msg || '镜像源设置已保存'), 'success');
      closeImageSourcePreferences();
    } catch (error) {
      uiStore.showMessage(error.message || '保存镜像源设置失败', 'error');
    } finally {
      imageSourcePreferencesSaving.value = false;
    }
  }

  async function openNetworkingPreferences() {
    if (networkingPreferencesLoading.value) return;

    networkingPreferencesLoading.value = true;
    try {
      const networking = await settingsStore.loadNetworkingSetting();
      composeManagedSubnetPool.value = String(
        networking?.composeManagedSubnetPool
        || settingsStore.settings.networking.composeManagedSubnetPool
        || '172.30.0.0/16',
      );
      composeManagedSubnetPrefix.value = String(
        networking?.composeManagedSubnetPrefix
        ?? settingsStore.settings.networking.composeManagedSubnetPrefix
        ?? 24,
      );
      showNetworkingPreferences.value = true;
    } catch (error) {
      uiStore.showMessage(error.message || '加载 Compose 网络池设置失败', 'error');
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
      const result = await settingsStore.saveNetworkingSetting(
        composeManagedSubnetPool.value,
        composeManagedSubnetPrefix.value,
      );
      composeManagedSubnetPool.value = String(
        settingsStore.settings.networking.composeManagedSubnetPool || '172.30.0.0/16',
      );
      composeManagedSubnetPrefix.value = String(
        settingsStore.settings.networking.composeManagedSubnetPrefix ?? 24,
      );
      uiStore.showMessage(String(result?.msg || 'Compose 网络池设置已保存'), 'success');
      closeNetworkingPreferences();
    } catch (error) {
      uiStore.showMessage(error.message || '保存 Compose 网络池设置失败', 'error');
    } finally {
      networkingPreferencesSaving.value = false;
    }
  }

  return {
    showImageSourcePreferences,
    showNetworkingPreferences,
    showSystemPreferences,
    imageSourcePreferencesLoading,
    imageSourcePreferencesSaving,
    networkingPreferencesLoading,
    networkingPreferencesSaving,
    systemPreferencesLoading,
    systemPreferencesSaving,
    systemTestSending,
    imageSourceInput,
    composeManagedSubnetPool,
    composeManagedSubnetPrefix,
    webhookUrl,
    webhookUrlSet,
    webhookUrlMasked,
    webhookUrlTouched,
    webhookTimeout,
    openSystemPreferences,
    closeSystemPreferences,
    saveSystemPreferences,
    sendSystemWebhookTest,
    openImageSourcePreferences,
    closeImageSourcePreferences,
    saveImageSourcePreferences,
    openNetworkingPreferences,
    closeNetworkingPreferences,
    saveNetworkingPreferences,
  };
}
