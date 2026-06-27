import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest } from '../api/client';

export const useFrpStore = defineStore('frp', () => {
  const frp = ref({
    enabled: false,
    settings: {
      serverAddr: '',
      serverPort: 7000,
      vhostHttpPort: null,
      adminIp: '127.0.0.1',
      adminPort: 7400,
      adminUser: '',
      adminPassword: '',
      adminPasswordSet: false,
      useDomain: false,
      domainSuffix: '',
    },
    healthText: '未检查',
    health: {
      enabled: false,
      overallOk: false,
      serverReachable: false,
      adminReachable: false,
    },
    proxies: [],
    configText: '',
  });

  function reset() {
    frp.value.enabled = false;
    frp.value.healthText = '未检查';
    frp.value.health.enabled = false;
    frp.value.health.overallOk = false;
    frp.value.health.serverReachable = false;
    frp.value.health.adminReachable = false;
    frp.value.proxies = [];
    frp.value.configText = '';
  }

  async function loadFrpSettings() {
    const result = await apiRequest('/frp/settings');
    const data = result?.data || {};
    frp.value.enabled = !!data.enabled;
    frp.value.settings.serverAddr = String(data.server_addr || '');
    frp.value.settings.serverPort = Number.isFinite(Number(data.server_port)) ? Number(data.server_port) : 7000;
    frp.value.settings.vhostHttpPort = data.vhost_http_port == null ? null : Number(data.vhost_http_port);
    frp.value.settings.adminIp = String(data.admin_ip || '127.0.0.1');
    frp.value.settings.adminPort = Number.isFinite(Number(data.admin_port)) ? Number(data.admin_port) : 7400;
    frp.value.settings.adminUser = String(data.admin_user || '');
    frp.value.settings.adminPassword = '';
    frp.value.settings.adminPasswordSet = !!data.admin_password_set;
    frp.value.settings.useDomain = !!data.use_domain;
    frp.value.settings.domainSuffix = String(data.domain_suffix || '');
    return data;
  }

  async function loadFrpHealth() {
    if (!frp.value.enabled) {
      frp.value.healthText = '未启用';
      frp.value.health.enabled = false;
      frp.value.health.overallOk = false;
      frp.value.health.serverReachable = false;
      frp.value.health.adminReachable = false;
      return;
    }
    try {
      const result = await apiRequest('/frp/health');
      const data = result?.data || {};
      const serverOk = !!data?.server?.reachable;
      const adminOk = !!data?.admin?.reachable;
      const enabled = !!data?.enabled;
      const overallOk = !!data?.overall_ok;
      frp.value.health.enabled = enabled;
      frp.value.health.overallOk = overallOk;
      frp.value.health.serverReachable = serverOk;
      frp.value.health.adminReachable = adminOk;
      frp.value.healthText = `服务端 ${serverOk ? '可达' : '不可达'} / 管理端 ${adminOk ? '可达' : '不可达'}`;
      return frp.value.healthText;
    } catch (error) {
      frp.value.health.enabled = false;
      frp.value.health.overallOk = false;
      frp.value.health.serverReachable = false;
      frp.value.health.adminReachable = false;
      frp.value.healthText = `检查失败: ${error.message || '未知错误'}`;
      return frp.value.healthText;
    }
  }

  async function loadFrpProxies() {
    const result = await apiRequest('/frp/proxies');
    frp.value.proxies = result?.data?.proxies || [];
    return frp.value.proxies;
  }

  async function loadFrpPanel() {
    await loadFrpSettings();
    if (!frp.value.enabled) {
      await loadFrpHealth();
      frp.value.proxies = [];
      frp.value.configText = '';
      return;
    }
    await Promise.allSettled([loadFrpHealth(), loadFrpProxies()]);
  }

  async function saveFrpSettings(enabled) {
    const result = await apiRequest('/frp/settings', {
      method: 'PUT',
      body: { enabled },
    });
    await loadFrpSettings();
    return result;
  }

  async function saveFrpPreferences(preferences) {
    const payload = {
      server_addr: String(preferences?.serverAddr || '').trim(),
      server_port: Number(preferences?.serverPort),
      vhost_http_port: preferences?.vhostHttpPort === '' || preferences?.vhostHttpPort == null
        ? null
        : Number(preferences?.vhostHttpPort),
      admin_ip: String(preferences?.adminIp || '').trim(),
      admin_port: Number(preferences?.adminPort),
      admin_user: String(preferences?.adminUser || '').trim(),
      use_domain: !!preferences?.useDomain,
      domain_suffix: String(preferences?.domainSuffix || '').trim(),
    };
    const nextPassword = String(preferences?.adminPassword || '').trim();
    if (nextPassword) {
      payload.admin_password = nextPassword;
    }
    const result = await apiRequest('/frp/settings', {
      method: 'PUT',
      body: payload,
    });
    await loadFrpSettings();
    return result;
  }

  async function loadFrpConfig() {
    const result = await apiRequest('/frp/config');
    const cfg = result?.data?.config;
    frp.value.configText = typeof cfg === 'string' ? cfg : JSON.stringify(cfg || {}, null, 2);
    return frp.value.configText;
  }

  return {
    frp,
    reset,
    loadFrpSettings,
    loadFrpHealth,
    loadFrpProxies,
    loadFrpPanel,
    saveFrpSettings,
    saveFrpPreferences,
    loadFrpConfig,
  };
});

export async function createFrpProxy(payload) {
  return apiRequest('/frp/proxies', {
    method: 'POST',
    body: payload,
  });
}

export async function loadFrpProxy(name) {
  const result = await apiRequest(`/frp/proxies/${encodeURIComponent(name)}`);
  return result?.data?.proxy || null;
}

export async function updateFrpProxy(name, payload) {
  return apiRequest(`/frp/proxies/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: payload,
  });
}

export async function deleteFrpProxy(name) {
  return apiRequest(`/frp/proxies/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export async function reloadFrpConfig() {
  return apiRequest('/frp/reload', {
    method: 'POST',
  });
}
