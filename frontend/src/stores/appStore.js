import { reactive } from 'vue';
import { apiRequest, clearApiKey, getApiBase, getApiKey, saveApiKey, API_PREFIX } from '../api/client';

const TREND_LIMIT = 20;
const MESSAGE_TIMEOUT_BY_TYPE = {
  success: 2400,
  error: 4200,
  warning: 3400,
  info: 3000,
};
let messageTimer = null;
let metricsInFlightController = null;
let metricsLastText = null;

export const store = reactive({
  apiKey: getApiKey(),
  activeTab: 'containers',
  message: '',
  messageType: 'success',
  containers: [],
  images: {
    items: [],
    stats: {
      total: 0,
      dangling: 0,
      inUse: 0,
      unused: 0,
      totalSizeText: '0 B',
    },
  },
  networks: {
    items: [],
    stats: {
      total: 0,
      inUse: 0,
      idle: 0,
      composeBound: 0,
    },
  },
  stats: {
    total: 0,
    running: 0,
  },
  systemStatus: null,
  metricsText: '',
  frp: {
    enabled: false,
    settings: {
      serverAddr: '',
      serverPort: 7000,
      vhostHttpPort: null,
      adminIp: '127.0.0.1',
      adminPort: 7400,
      adminUser: '',
      adminPassword: '',
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
  },
  settings: {
    imageSource: '',
    alerts: {
      webhookUrl: '',
      webhookTimeout: 5,
      performanceLogInterval: 300,
      alertCpuThreshold: 95,
      alertCpuSustainedIntervals: 3,
      alertMemThreshold: 90,
      alertMemSustainedIntervals: 3,
      alertCooldownSec: 900,
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
  },
  detailPanel: {
    open: false,
    title: '',
    payload: null,
  },
  trend: {
    cpu: [],
    mem: [],
    ts: [],
  },
});

function parsePercent(value) {
  if (typeof value === 'number') return value;
  if (typeof value !== 'string') return null;
  const n = Number.parseFloat(value.replace('%', '').trim());
  return Number.isFinite(n) ? n : null;
}

function pushTrendSample(cpu, mem, ts = Date.now()) {
  if (cpu !== null) store.trend.cpu.push(cpu);
  if (mem !== null) store.trend.mem.push(mem);
  store.trend.ts.push(ts);

  if (store.trend.cpu.length > TREND_LIMIT) {
    store.trend.cpu.splice(0, store.trend.cpu.length - TREND_LIMIT);
  }
  if (store.trend.mem.length > TREND_LIMIT) {
    store.trend.mem.splice(0, store.trend.mem.length - TREND_LIMIT);
  }
  if (store.trend.ts.length > TREND_LIMIT) {
    store.trend.ts.splice(0, store.trend.ts.length - TREND_LIMIT);
  }
}

export function showMessage(message, type = 'success', durationMs) {
  if (messageTimer !== null) {
    window.clearTimeout(messageTimer);
    messageTimer = null;
  }

  store.message = message;
  store.messageType = type;

  const timeout = Number.isFinite(durationMs)
    ? durationMs
    : (MESSAGE_TIMEOUT_BY_TYPE[type] ?? MESSAGE_TIMEOUT_BY_TYPE.info);

  messageTimer = window.setTimeout(() => {
    if (store.message === message) {
      store.message = '';
    }
    messageTimer = null;
  }, timeout);
}

export function isLoggedIn() {
  return !!store.apiKey;
}

export function login(apiKey) {
  saveApiKey(apiKey);
  store.apiKey = apiKey;
}

export function logout() {
  clearApiKey();
  store.apiKey = '';
  store.containers = [];
  store.images.items = [];
  store.images.stats.total = 0;
  store.images.stats.dangling = 0;
  store.images.stats.inUse = 0;
  store.images.stats.unused = 0;
  store.images.stats.totalSizeText = '0 B';
  store.networks.items = [];
  store.networks.stats.total = 0;
  store.networks.stats.inUse = 0;
  store.networks.stats.idle = 0;
  store.networks.stats.composeBound = 0;
  store.stats.total = 0;
  store.stats.running = 0;
  store.systemStatus = null;
  store.metricsText = '';
  store.frp.enabled = false;
  store.frp.healthText = '未检查';
  store.frp.health.enabled = false;
  store.frp.health.overallOk = false;
  store.frp.health.serverReachable = false;
  store.frp.health.adminReachable = false;
  store.frp.proxies = [];
  store.frp.configText = '';
  closeDetailPanel();
}

export function openDetailPanel(title, payload) {
  store.detailPanel.open = true;
  store.detailPanel.title = title;
  store.detailPanel.payload = payload;
}

export function closeDetailPanel() {
  store.detailPanel.open = false;
  store.detailPanel.title = '';
  store.detailPanel.payload = null;
}

export async function loadContainers() {
  const result = await apiRequest('/containers');
  const list = result?.data?.containers || [];
  store.containers = list;
  store.stats.total = list.length;
  store.stats.running = list.filter((item) => String(item.status || '').toLowerCase() === 'running').length;
}

export async function loadImages() {
  const result = await apiRequest('/images');
  const data = result?.data || {};
  const items = data.images || [];
  store.images.items = items;
  store.images.stats.total = Number(data.total ?? items.length) || 0;
  store.images.stats.dangling = Number(data.dangling ?? items.filter((item) => !!item?.is_dangling).length) || 0;
  store.images.stats.inUse = Number(data.in_use ?? items.filter((item) => Number(item?.containers_using || 0) > 0).length) || 0;
  store.images.stats.unused = Number(data.unused ?? items.filter((item) => Number(item?.containers_using || 0) <= 0).length) || 0;
  store.images.stats.totalSizeText = String(data.total_size_text || '0 B');
  return items;
}

export async function loadImageDetail(imageRef) {
  const result = await apiRequest(`/images/detail/${encodeURIComponent(imageRef)}`);
  return result?.data || null;
}

export async function pullManagedImage(image) {
  return apiRequest('/images/pull', {
    method: 'POST',
    body: { image },
    timeoutMs: 300000,
  });
}

export async function deleteManagedImage(imageRef, force = false) {
  return apiRequest(`/images/${encodeURIComponent(imageRef)}${force ? '?force=1' : ''}`, {
    method: 'DELETE',
    timeoutMs: 120000,
  });
}

export async function pruneManagedImages() {
  return apiRequest('/images/prune', {
    method: 'POST',
    body: {},
    timeoutMs: 180000,
  });
}

export async function loadManagedNetworks() {
  const result = await apiRequest('/networks');
  const items = result?.data?.networks || [];
  store.networks.items = items;
  store.networks.stats.total = Number(result?.data?.total ?? items.length) || 0;
  store.networks.stats.inUse = Number(result?.data?.in_use ?? items.filter((item) => item?.is_in_use).length) || 0;
  store.networks.stats.idle = Number(result?.data?.idle ?? items.filter((item) => !item?.is_in_use).length) || 0;
  store.networks.stats.composeBound = items.filter((item) => !!item?.compose_project_id).length;
  return items;
}

export async function loadManagedNetworkDetail(networkId) {
  const result = await apiRequest(`/networks/${encodeURIComponent(networkId)}`);
  return result?.data || null;
}

export async function createManagedNetwork(payload) {
  return apiRequest('/networks', {
    method: 'POST',
    body: payload,
    timeoutMs: 60000,
  });
}

export async function updateManagedNetwork(networkId, payload) {
  return apiRequest(`/networks/${encodeURIComponent(networkId)}`, {
    method: 'PUT',
    body: payload,
    timeoutMs: 60000,
  });
}

export async function deleteManagedNetwork(networkId) {
  return apiRequest(`/networks/${encodeURIComponent(networkId)}`, {
    method: 'DELETE',
    timeoutMs: 60000,
  });
}

export async function createContainer(payload) {
  const result = await apiRequest('/containers', {
    method: 'POST',
    body: payload,
    timeoutMs: 300000,
  });
  return result;
}

export async function loadContainerDetail(containerId) {
  const result = await apiRequest(`/containers/${encodeURIComponent(containerId)}`);
  const payload = result?.data || null;
  openDetailPanel(`容器详情: ${containerId}`, payload);
  return payload;
}

export async function restartContainer(containerId) {
  return apiRequest(`/containers/${encodeURIComponent(containerId)}`, {
    method: 'PATCH',
    timeoutMs: 60000,
  });
}

export async function deleteContainer(containerId) {
  return apiRequest(`/containers/${encodeURIComponent(containerId)}`, {
    method: 'DELETE',
    timeoutMs: 60000,
  });
}

export async function getContainerDestroyStatus(containerId) {
  return apiRequest(`/containers/${encodeURIComponent(containerId)}/destroy-status`, {
    method: 'GET',
    timeoutMs: 15000,
  });
}

export async function getComposeProjectDestroyStatus(projectId) {
  return apiRequest(`/containers/project/${encodeURIComponent(projectId)}/destroy-status`, {
    method: 'GET',
    timeoutMs: 15000,
  });
}

export async function waitContainerDestroyStatus(containerId, {
  pollIntervalMs = 2000,
  timeoutMs = 90000,
} = {}) {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const result = await getContainerDestroyStatus(containerId);
    const status = String(result?.data?.status || '').toLowerCase();

    if (status === 'success') {
      return result?.data || { container_id: containerId, status: 'success' };
    }
    if (status === 'failed') {
      const msg = result?.data?.error || '后台删除失败';
      throw new Error(msg);
    }

    await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
  }

  throw new Error('删除任务仍在进行中，请稍后刷新列表查看状态');
}

export async function renewContainer(containerId) {
  return apiRequest(`/containers/${encodeURIComponent(containerId)}/renew`, {
    method: 'POST',
  });
}

export async function loadComposeProjectDetail(projectId) {
  const result = await apiRequest(`/containers/project/${encodeURIComponent(projectId)}`);
  const payload = result?.data || null;
  openDetailPanel(`Compose 项目详情: ${projectId}`, payload);
  return payload;
}

export async function restartComposeProject(projectId) {
  return apiRequest(`/containers/project/${encodeURIComponent(projectId)}`, {
    method: 'PATCH',
    timeoutMs: 120000,
  });
}

export async function deleteComposeProject(projectId) {
  return apiRequest(`/containers/project/${encodeURIComponent(projectId)}`, {
    method: 'DELETE',
    timeoutMs: 120000,
  });
}

export async function waitComposeProjectDestroyStatus(projectDeleteResponse, {
  pollIntervalMs = 2000,
  timeoutMs = 120000,
} = {}) {
  const projectId = projectDeleteResponse?.data?.compose_project_id;
  if (!projectId) {
    throw new Error('缺少 compose_project_id，无法跟踪项目删除状态');
  }

  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const result = await getComposeProjectDestroyStatus(projectId);
    const status = String(result?.data?.status || '').toLowerCase();

    if (status === 'success') {
      return result?.data || { compose_project_id: projectId, status: 'success' };
    }
    if (status === 'failed') {
      const msg = result?.data?.network_cleanup_task?.error || '后台删除失败';
      throw new Error(msg);
    }

    await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
  }

  throw new Error('项目删除任务仍在进行中，请稍后刷新列表查看状态');
}

export async function renewComposeProject(projectId) {
  return apiRequest(`/containers/project/${encodeURIComponent(projectId)}/renew`, {
    method: 'POST',
  });
}

export async function loadSystemStatus() {
  const result = await apiRequest('/status');
  store.systemStatus = result?.data || null;
  const cpu = parsePercent(store.systemStatus?.cpu_usage);
  const mem = parsePercent(store.systemStatus?.memory_usage);
  pushTrendSample(cpu, mem);
  return store.systemStatus;
}

export async function loadMetrics() {
  // /metrics 为 text/plain，直接使用原生 fetch 获取文本。
  const key = getApiKey();
  const headers = {};
  if (key) headers['X-API-Key'] = key;
  // 避免并发/重复拉取：新的请求会取消旧的，减少带宽与无意义更新
  if (metricsInFlightController) {
    try { metricsInFlightController.abort(); } catch {}
  }
  const controller = new AbortController();
  metricsInFlightController = controller;
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${getApiBase()}${API_PREFIX}/metrics`, { headers, signal: controller.signal });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(text || `HTTP ${response.status}`);
    }
    // 大文本优化：内容没变化就不要触发 <pre> 重绘
    if (text !== metricsLastText) {
      metricsLastText = text;
      store.metricsText = text;
    }
    return text;
  } finally {
    clearTimeout(timer);
    if (metricsInFlightController === controller) {
      metricsInFlightController = null;
    }
  }
}

export async function refreshContainersPanel() {
  await Promise.allSettled([loadContainers(), loadSystemStatus()]);
}

export async function refreshImagesPanel() {
  await loadImages();
}

export async function refreshNetworksPanel() {
  await loadManagedNetworks();
}

export async function loadSystemPanel() {
  // 性能优先：先把“系统状态/分布式状态”画出来，metrics 低优先级延后到空闲时段
  await Promise.allSettled([loadSystemStatus()]);

  // 页面在后台时不拉 metrics，避免无意义网络与渲染
  if (typeof document !== 'undefined' && document.hidden) return;

  const schedule = (fn) => {
    if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => fn(), { timeout: 1200 });
      return;
    }
    window.setTimeout(fn, 0);
  };
  schedule(() => {
    loadMetrics().catch(() => {});
  });
}

export async function loadFrpSettings() {
  const result = await apiRequest('/frp/settings');
  const data = result?.data || {};
  store.frp.enabled = !!data.enabled;
  store.frp.settings.serverAddr = String(data.server_addr || '');
  store.frp.settings.serverPort = Number.isFinite(Number(data.server_port)) ? Number(data.server_port) : 7000;
  store.frp.settings.vhostHttpPort = data.vhost_http_port == null ? null : Number(data.vhost_http_port);
  store.frp.settings.adminIp = String(data.admin_ip || '127.0.0.1');
  store.frp.settings.adminPort = Number.isFinite(Number(data.admin_port)) ? Number(data.admin_port) : 7400;
  store.frp.settings.adminUser = String(data.admin_user || '');
  store.frp.settings.adminPassword = String(data.admin_password || '');
  store.frp.settings.useDomain = !!data.use_domain;
  store.frp.settings.domainSuffix = String(data.domain_suffix || '');
  return data;
}

export async function loadImageSourceSetting() {
  const result = await apiRequest('/settings/image-source');
  const value = String(result?.data?.image_source || '');
  store.settings.imageSource = value;
  return value;
}

export async function loadAlertWebhookSetting() {
  const result = await apiRequest('/settings/alerts/webhook');
  const value = String(result?.data?.webhook_url || '');
  const timeout = Number.isFinite(Number(result?.data?.webhook_timeout))
    ? Number(result.data.webhook_timeout)
    : 5;
  store.settings.alerts.webhookUrl = value;
  store.settings.alerts.webhookTimeout = timeout;
  return { webhookUrl: value, webhookTimeout: timeout };
}

export async function loadAlertPerfSettings() {
  const result = await apiRequest('/settings/alerts/perf');
  const data = result?.data || {};
  store.settings.alerts.performanceLogInterval = Number.isFinite(Number(data.performance_log_interval))
    ? Number(data.performance_log_interval) : 300;
  store.settings.alerts.alertCpuThreshold = Number.isFinite(Number(data.alert_cpu_threshold))
    ? Number(data.alert_cpu_threshold) : 95;
  store.settings.alerts.alertCpuSustainedIntervals = Number.isFinite(Number(data.alert_cpu_sustained_intervals))
    ? Number(data.alert_cpu_sustained_intervals) : 3;
  store.settings.alerts.alertMemThreshold = Number.isFinite(Number(data.alert_mem_threshold))
    ? Number(data.alert_mem_threshold) : 90;
  store.settings.alerts.alertMemSustainedIntervals = Number.isFinite(Number(data.alert_mem_sustained_intervals))
    ? Number(data.alert_mem_sustained_intervals) : 3;
  store.settings.alerts.alertCooldownSec = Number.isFinite(Number(data.alert_cooldown_sec))
    ? Number(data.alert_cooldown_sec) : 900;
  return store.settings.alerts;
}

export async function saveAlertPerfSettings(perf) {
  const payload = {
    performance_log_interval: Number(perf.performanceLogInterval),
    alert_cpu_threshold: Number(perf.alertCpuThreshold),
    alert_cpu_sustained_intervals: Number(perf.alertCpuSustainedIntervals),
    alert_mem_threshold: Number(perf.alertMemThreshold),
    alert_mem_sustained_intervals: Number(perf.alertMemSustainedIntervals),
    alert_cooldown_sec: Number(perf.alertCooldownSec),
  };
  const result = await apiRequest('/settings/alerts/perf', { method: 'PUT', body: payload });
  await loadAlertPerfSettings();
  return result;
}

export async function saveAlertWebhookSetting(webhookUrl, webhookTimeout) {
  const value = String(webhookUrl || '').trim();
  const timeout = Number.isFinite(Number(webhookTimeout)) ? Number(webhookTimeout) : 5;
  const result = await apiRequest('/settings/alerts/webhook', {
    method: 'PUT',
    body: { webhook_url: value, webhook_timeout: timeout },
  });
  store.settings.alerts.webhookUrl = value;
  store.settings.alerts.webhookTimeout = timeout;
  return result;
}

export async function sendAlertWebhookTest() {
  return apiRequest('/alerts/test', { method: 'POST', body: {} });
}

export async function saveImageSourceSetting(imageSource) {
  const value = String(imageSource || '').trim();
  const result = await apiRequest('/settings/image-source', {
    method: 'PUT',
    body: { image_source: value },
  });
  store.settings.imageSource = value;
  return result;
}

export async function loadContainerLimitsSetting() {
  const result = await apiRequest('/settings/webui');
  const data = result?.data || {};
  store.settings.containerLimits.maxContainers = Number.isFinite(Number(data.max_containers)) ? Number(data.max_containers) : 30;
  store.settings.containerLimits.maxRenewTimes = Number.isFinite(Number(data.max_renew_times)) ? Number(data.max_renew_times) : 3;
  return store.settings.containerLimits;
}

export async function saveContainerLimitsSetting(maxContainers, maxRenewTimes) {
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

  store.settings.containerLimits.maxContainers = Number(maxContainers);
  store.settings.containerLimits.maxRenewTimes = Number(maxRenewTimes);
  return result;
}

export async function loadContainerDefaultsSetting() {
  const result = await apiRequest('/settings/container-defaults');
  const data = result?.data || {};
  store.settings.containerDefaults.maxTime = Number.isFinite(Number(data.max_time)) ? Number(data.max_time) : 3600;
  store.settings.containerDefaults.minPort = Number.isFinite(Number(data.min_port)) ? Number(data.min_port) : 20000;
  store.settings.containerDefaults.maxPort = Number.isFinite(Number(data.max_port)) ? Number(data.max_port) : 30000;
  store.settings.containerDefaults.memoryLimit = String(data.memory_limit || '512m');
  store.settings.containerDefaults.cpuLimit = Number.isFinite(Number(data.cpu_limit)) ? Number(data.cpu_limit) : 1.0;
  store.settings.containerDefaults.cpuShares = Number.isFinite(Number(data.cpu_shares)) ? Number(data.cpu_shares) : 1024;
  return store.settings.containerDefaults;
}

export async function saveFrpSettings(enabled) {
  const result = await apiRequest('/frp/settings', {
    method: 'PUT',
    body: { enabled },
  });
  await loadFrpSettings();
  return result;
}

export async function saveFrpPreferences(preferences) {
  const payload = {
    server_addr: String(preferences?.serverAddr || '').trim(),
    server_port: Number(preferences?.serverPort),
    vhost_http_port: preferences?.vhostHttpPort === '' || preferences?.vhostHttpPort == null
      ? null
      : Number(preferences?.vhostHttpPort),
    admin_ip: String(preferences?.adminIp || '').trim(),
    admin_port: Number(preferences?.adminPort),
    admin_user: String(preferences?.adminUser || '').trim(),
    admin_password: String(preferences?.adminPassword || '').trim(),
    use_domain: !!preferences?.useDomain,
    domain_suffix: String(preferences?.domainSuffix || '').trim(),
  };
  const result = await apiRequest('/frp/settings', {
    method: 'PUT',
    body: payload,
  });
  await loadFrpSettings();
  return result;
}

export async function loadFrpHealth() {
  // FRP 未启用时不做健康检查，避免前端无意义地请求 /frp/health
  if (!store.frp.enabled) {
    store.frp.healthText = '未启用';
    store.frp.health.enabled = false;
    store.frp.health.overallOk = false;
    store.frp.health.serverReachable = false;
    store.frp.health.adminReachable = false;
    return;
  }
  try {
    const result = await apiRequest('/frp/health');
    const data = result?.data || {};
    const serverOk = !!data?.server?.reachable;
    const adminOk = !!data?.admin?.reachable;
    const enabled = !!data?.enabled;
    const overallOk = !!data?.overall_ok;
    store.frp.health.enabled = enabled;
    store.frp.health.overallOk = overallOk;
    store.frp.health.serverReachable = serverOk;
    store.frp.health.adminReachable = adminOk;
    store.frp.healthText = `服务端 ${serverOk ? '可达' : '不可达'} / 管理端 ${adminOk ? '可达' : '不可达'}`;
    return store.frp.healthText;
  } catch (error) {
    store.frp.health.enabled = false;
    store.frp.health.overallOk = false;
    store.frp.health.serverReachable = false;
    store.frp.health.adminReachable = false;
    store.frp.healthText = `检查失败: ${error.message || '未知错误'}`;
    return store.frp.healthText;
  }
}

export async function loadFrpProxies() {
  const result = await apiRequest('/frp/proxies');
  store.frp.proxies = result?.data?.proxies || [];
  return store.frp.proxies;
}

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

export async function loadFrpConfig() {
  const result = await apiRequest('/frp/config');
  const cfg = result?.data?.config;
  store.frp.configText = typeof cfg === 'string' ? cfg : JSON.stringify(cfg || {}, null, 2);
  return store.frp.configText;
}

export async function loadFrpPanel() {
  // 先加载 settings，避免并发导致 enabled 还没更新就去请求 health/proxies
  await loadFrpSettings();
  if (!store.frp.enabled) {
    await loadFrpHealth();
    store.frp.proxies = [];
    store.frp.configText = '';
    return;
  }
  await Promise.allSettled([loadFrpHealth(), loadFrpProxies()]);
}
