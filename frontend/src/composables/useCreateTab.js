import { onMounted, reactive, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useContainersStore } from '../stores/containersStore';
import { useNetworksStore } from '../stores/networksStore';
import { useSettingsStore } from '../stores/settingsStore';
import { useUiStore } from '../stores/uiStore';
import { parseKeyValueLines } from './useKeyValueLines';

export function useCreateTab() {
  const settingsStore = useSettingsStore();
  const containersStore = useContainersStore();
  const networksStore = useNetworksStore();
  const uiStore = useUiStore();
  const { settings } = storeToRefs(settingsStore);

  const form = reactive({
    source: 'path',
    port_mode: 'random',
    path: '',
    image: '',
    uid: '',
    command: '',
    network: '',
    port_mappings_text: '',
    min_port: '',
    max_port: '',
    max_time: '',
    tag: '',
    memory_limit: '',
    cpu_limit: '',
    cpu_shares: '',
    envText: '',
  });

  const showBuildModal = ref(false);
  const buildPayload = ref(null);
  const showPreferencesModal = ref(false);
  const imageSourceInput = ref('');
  const composeManagedSubnetPool = ref('172.30.0.0/16');
  const composeManagedSubnetPrefix = ref('24');
  const maxContainersInput = ref('');
  const maxRenewTimesInput = ref('');
  const limitsLoading = ref(false);
  const limitsSaving = ref(false);

  function applyContainerDefaults(defaults = settings.value.containerDefaults) {
    const source = defaults || {};
    form.max_time = String(source.maxTime ?? 3600);
    form.min_port = String(source.minPort ?? 20000);
    form.max_port = String(source.maxPort ?? 30000);
    form.memory_limit = String(source.memoryLimit ?? '512m');
    form.cpu_limit = String(source.cpuLimit ?? 1.0);
    form.cpu_shares = String(source.cpuShares ?? 1024);
  }

  function parseEnvText(text) {
    const raw = String(text || '').trim();
    if (!raw) return {};
    return parseKeyValueLines(raw, {
      allowColon: true,
      invalidLineMessage: (line) => `${line} 环境变量格式错误`,
      emptyKeyMessage: (line) => `环境变量键不能为空: ${line}`,
    });
  }

  function submit() {
    const payload = { source: form.source };
    if (form.source === 'image') {
      payload.image = form.image.trim();
      if (!payload.image) {
        uiStore.showMessage('请填写镜像名称', 'error');
        return;
      }
    } else {
      payload.path = form.path.trim();
      if (!payload.path) {
        uiStore.showMessage('请填写容器路径', 'error');
        return;
      }
    }

    if (form.uid.trim()) payload.uid = form.uid.trim();
    if (form.command.trim()) payload.command = form.command.trim();
    if (form.network.trim()) payload.network = form.network.trim();
    if (form.port_mode === 'fixed') {
      if (!form.port_mappings_text.trim()) {
        uiStore.showMessage('请填写固定端口映射', 'error');
        return;
      }
      payload.port_mappings = form.port_mappings_text.trim();
    } else {
      if (form.min_port) payload.min_port = Number(form.min_port);
      if (form.max_port) payload.max_port = Number(form.max_port);
    }
    if (form.max_time) payload.max_time = Number(form.max_time);
    if (form.tag.trim()) payload.tag = form.tag.trim();
    if (form.memory_limit.trim()) payload.memory_limit = form.memory_limit.trim();
    if (form.cpu_limit) payload.cpu_limit = Number(form.cpu_limit);
    if (form.cpu_shares) payload.cpu_shares = Number(form.cpu_shares);

    try {
      if (form.envText.trim()) {
        payload.env = parseEnvText(form.envText);
      }
    } catch (error) {
      uiStore.showMessage(error.message || '环境变量格式错误', 'error');
      return;
    }

    buildPayload.value = payload;
    showBuildModal.value = true;
  }

  function resetForm() {
    form.source = 'path';
    form.port_mode = 'random';
    form.path = '';
    form.image = '';
    form.uid = '';
    form.command = '';
    form.network = '';
    form.port_mappings_text = '';
    form.min_port = String(settings.value.containerDefaults.minPort ?? 20000);
    form.max_port = String(settings.value.containerDefaults.maxPort ?? 30000);
    form.max_time = String(settings.value.containerDefaults.maxTime ?? 3600);
    form.tag = '';
    form.memory_limit = String(settings.value.containerDefaults.memoryLimit ?? '512m');
    form.cpu_limit = String(settings.value.containerDefaults.cpuLimit ?? 1.0);
    form.cpu_shares = String(settings.value.containerDefaults.cpuShares ?? 1024);
    form.envText = '';
  }

  async function loadContainerDefaults() {
    try {
      await settingsStore.loadContainerDefaultsSetting();
      applyContainerDefaults();
    } catch (error) {
      uiStore.showMessage(error.message || '加载容器默认配置失败，已使用内置默认值', 'warning');
      applyContainerDefaults();
    }
  }

  async function onBuildSuccess() {
    uiStore.showMessage('容器创建成功', 'success');
    await containersStore.loadContainers();
    resetForm();
  }

  function onBuildClose() {
    showBuildModal.value = false;
    buildPayload.value = null;
  }

  async function loadContainerLimits() {
    limitsLoading.value = true;
    try {
      const [limits, imageSource, networking] = await Promise.all([
        settingsStore.loadContainerLimitsSetting(),
        settingsStore.loadImageSourceSetting(),
        settingsStore.loadNetworkingSetting(),
      ]);
      maxContainersInput.value = String(limits.maxContainers ?? 30);
      maxRenewTimesInput.value = String(limits.maxRenewTimes ?? 3);
      imageSourceInput.value = String(imageSource || '');
      composeManagedSubnetPool.value = String(
        networking?.composeManagedSubnetPool || settings.value.networking.composeManagedSubnetPool || '172.30.0.0/16',
      );
      composeManagedSubnetPrefix.value = String(
        networking?.composeManagedSubnetPrefix ?? settings.value.networking.composeManagedSubnetPrefix ?? 24,
      );
    } catch (error) {
      uiStore.showMessage(error.message || '加载偏好设置失败', 'error');
    } finally {
      limitsLoading.value = false;
    }
  }

  async function savePreferences() {
    limitsSaving.value = true;
    try {
      const maxContainers = Number.parseInt(String(maxContainersInput.value || '').trim(), 10);
      const maxRenewTimes = Number.parseInt(String(maxRenewTimesInput.value || '').trim(), 10);
      if (!Number.isFinite(maxContainers) || maxContainers <= 0) {
        throw new Error('最大容器数需为正整数');
      }
      if (!Number.isFinite(maxRenewTimes) || maxRenewTimes < 0) {
        throw new Error('最大续期次数需为非负整数');
      }

      await Promise.all([
        settingsStore.saveImageSourceSetting(imageSourceInput.value),
        settingsStore.saveNetworkingSetting(composeManagedSubnetPool.value, composeManagedSubnetPrefix.value),
        settingsStore.saveContainerLimitsSetting(maxContainers, maxRenewTimes),
      ]);
      imageSourceInput.value = String(settings.value.imageSource || '');
      composeManagedSubnetPool.value = String(settings.value.networking.composeManagedSubnetPool || '172.30.0.0/16');
      composeManagedSubnetPrefix.value = String(settings.value.networking.composeManagedSubnetPrefix ?? 24);
      maxContainersInput.value = String(settings.value.containerLimits.maxContainers);
      maxRenewTimesInput.value = String(settings.value.containerLimits.maxRenewTimes);
      uiStore.showMessage('偏好设置已更新', 'success');
      closePreferencesModal();
    } catch (error) {
      uiStore.showMessage(error.message || '保存偏好设置失败', 'error');
    } finally {
      limitsSaving.value = false;
    }
  }

  async function openPreferencesModal() {
    showPreferencesModal.value = true;
    await loadContainerLimits();
  }

  function closePreferencesModal() {
    showPreferencesModal.value = false;
  }

  function validateEnvFormat() {
    const raw = String(form.envText || '').trim();
    if (!raw) {
      uiStore.showMessage('环境变量为空，默认不传递额外变量', 'info');
      return;
    }

    try {
      const parsed = parseEnvText(raw);
      uiStore.showMessage(`格式正确，共 ${Object.keys(parsed).length} 项环境变量`, 'success');
    } catch (error) {
      uiStore.showMessage(error.message || '环境变量格式错误，请检查填写内容', 'error');
    }
  }

  onMounted(async () => {
    await loadContainerDefaults();
    networksStore.loadManagedNetworks().catch(() => {});
  });

  return {
    buildPayload,
    closePreferencesModal,
    composeManagedSubnetPool,
    composeManagedSubnetPrefix,
    form,
    imageSourceInput,
    limitsLoading,
    limitsSaving,
    maxContainersInput,
    maxRenewTimesInput,
    onBuildClose,
    onBuildSuccess,
    openPreferencesModal,
    resetForm,
    savePreferences,
    showBuildModal,
    showPreferencesModal,
    submit,
    validateEnvFormat,
  };
}
