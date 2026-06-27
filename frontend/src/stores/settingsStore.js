import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest } from '../api/client';

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref({
    imageSource: '',
    networking: {
      composeManagedSubnetPool: '172.30.0.0/16',
      composeManagedSubnetPrefix: 24,
    },
    alerts: {
      webhookUrl: '',
      webhookUrlSet: false,
      webhookUrlMasked: '',
      webhookTimeout: 5,
    },
    containerLimits: {
      maxContainers: 30,
      maxRenewTimes: 3,
    },
    containerDefaults: {
      maxTime: 3600,
      minPort: 20000,
      maxPort: 30000,
      memoryLimit: '512m',
      cpuLimit: 1.0,
      cpuShares: 1024,
    },
  });

  async function loadImageSourceSetting() {
    const result = await apiRequest('/settings/image-source');
    const value = String(result?.data?.image_source || '');
    settings.value.imageSource = value;
    return value;
  }

  async function loadNetworkingSetting() {
    const result = await apiRequest('/settings/networking');
    const data = result?.data || {};
    const pool = String(data.compose_managed_subnet_pool || '172.30.0.0/16');
    const prefix = Number.isFinite(Number(data.compose_managed_subnet_prefix))
      ? Number(data.compose_managed_subnet_prefix)
      : 24;
    settings.value.networking.composeManagedSubnetPool = pool;
    settings.value.networking.composeManagedSubnetPrefix = prefix;
    return {
      composeManagedSubnetPool: pool,
      composeManagedSubnetPrefix: prefix,
    };
  }

  async function loadAlertWebhookSetting() {
    const result = await apiRequest('/settings/alerts/webhook');
    const masked = String(result?.data?.webhook_url || '');
    const timeout = Number.isFinite(Number(result?.data?.webhook_timeout))
      ? Number(result.data.webhook_timeout)
      : 5;
    settings.value.alerts.webhookUrl = '';
    settings.value.alerts.webhookUrlSet = !!result?.data?.webhook_url_set;
    settings.value.alerts.webhookUrlMasked = masked;
    settings.value.alerts.webhookTimeout = timeout;
    return {
      webhookUrl: '',
      webhookUrlSet: settings.value.alerts.webhookUrlSet,
      webhookUrlMasked: masked,
      webhookTimeout: timeout,
    };
  }

  async function saveAlertWebhookSetting(webhookUrl, webhookTimeout, options = {}) {
    const value = String(webhookUrl || '').trim();
    const timeout = Number.isFinite(Number(webhookTimeout)) ? Number(webhookTimeout) : 5;
    const body = { webhook_timeout: timeout };
    if (options.webhookUrlTouched) {
      body.webhook_url = value;
    }
    const result = await apiRequest('/settings/alerts/webhook', {
      method: 'PUT',
      body,
    });
    await loadAlertWebhookSetting();
    settings.value.alerts.webhookTimeout = timeout;
    return result;
  }

  async function sendAlertWebhookTest() {
    return apiRequest('/alerts/test', { method: 'POST', body: {} });
  }

  async function saveImageSourceSetting(imageSource) {
    const value = String(imageSource || '').trim();
    const result = await apiRequest('/settings/image-source', {
      method: 'PUT',
      body: { image_source: value },
    });
    settings.value.imageSource = value;
    return result;
  }

  async function saveNetworkingSetting(composeManagedSubnetPool, composeManagedSubnetPrefix) {
    const pool = String(composeManagedSubnetPool || '').trim();
    const prefix = Number(composeManagedSubnetPrefix);
    const result = await apiRequest('/settings/networking', {
      method: 'PUT',
      body: {
        compose_managed_subnet_pool: pool,
        compose_managed_subnet_prefix: prefix,
      },
    });
    settings.value.networking.composeManagedSubnetPool = pool;
    settings.value.networking.composeManagedSubnetPrefix = prefix;
    return result;
  }

  async function loadContainerLimitsSetting() {
    const result = await apiRequest('/settings/webui');
    const data = result?.data || {};
    settings.value.containerLimits.maxContainers = Number.isFinite(Number(data.max_containers)) ? Number(data.max_containers) : 30;
    settings.value.containerLimits.maxRenewTimes = Number.isFinite(Number(data.max_renew_times)) ? Number(data.max_renew_times) : 3;
    return settings.value.containerLimits;
  }

  async function saveContainerLimitsSetting(maxContainers, maxRenewTimes) {
    const current = await apiRequest('/settings/webui');
    const apiBase = String(current?.data?.api_base || '').trim();
    const pollIntervalSec = Number.isFinite(Number(current?.data?.poll_interval_sec))
      ? Number(current.data.poll_interval_sec)
      : 30;

    const result = await apiRequest('/settings/webui', {
      method: 'PUT',
      body: {
        api_base: apiBase,
        poll_interval_sec: pollIntervalSec,
        max_containers: maxContainers,
        max_renew_times: maxRenewTimes,
      },
    });

    settings.value.containerLimits.maxContainers = Number(maxContainers);
    settings.value.containerLimits.maxRenewTimes = Number(maxRenewTimes);
    return result;
  }

  async function loadContainerDefaultsSetting() {
    const result = await apiRequest('/settings/container-defaults');
    const data = result?.data || {};
    settings.value.containerDefaults.maxTime = Number.isFinite(Number(data.max_time)) ? Number(data.max_time) : 3600;
    settings.value.containerDefaults.minPort = Number.isFinite(Number(data.min_port)) ? Number(data.min_port) : 20000;
    settings.value.containerDefaults.maxPort = Number.isFinite(Number(data.max_port)) ? Number(data.max_port) : 30000;
    settings.value.containerDefaults.memoryLimit = String(data.memory_limit || '512m');
    settings.value.containerDefaults.cpuLimit = Number.isFinite(Number(data.cpu_limit)) ? Number(data.cpu_limit) : 1.0;
    settings.value.containerDefaults.cpuShares = Number.isFinite(Number(data.cpu_shares)) ? Number(data.cpu_shares) : 1024;
    return settings.value.containerDefaults;
  }

  return {
    settings,
    loadImageSourceSetting,
    loadNetworkingSetting,
    loadAlertWebhookSetting,
    saveAlertWebhookSetting,
    sendAlertWebhookTest,
    saveImageSourceSetting,
    saveNetworkingSetting,
    loadContainerLimitsSetting,
    saveContainerLimitsSetting,
    loadContainerDefaultsSetting,
  };
});
