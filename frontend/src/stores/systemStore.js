import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest, getApiBase, getAuthHeaders, API_PREFIX } from '../api/client';
import { useContainersStore } from './containersStore';

const TREND_LIMIT = 20;
let metricsInFlightController = null;
let metricsLastText = null;

function parsePercent(value) {
  if (typeof value === 'number') return value;
  if (typeof value !== 'string') return null;
  const n = Number.parseFloat(value.replace('%', '').trim());
  return Number.isFinite(n) ? n : null;
}

export const useSystemStore = defineStore('system', () => {
  const systemStatus = ref(null);
  const metricsText = ref('');
  const trend = ref({
    cpu: [],
    mem: [],
    ts: [],
  });

  function reset() {
    systemStatus.value = null;
    metricsText.value = '';
    trend.value.cpu = [];
    trend.value.mem = [];
    trend.value.ts = [];
  }

  function pushTrendSample(cpu, mem, ts = Date.now()) {
    if (cpu !== null) trend.value.cpu.push(cpu);
    if (mem !== null) trend.value.mem.push(mem);
    trend.value.ts.push(ts);

    if (trend.value.cpu.length > TREND_LIMIT) {
      trend.value.cpu.splice(0, trend.value.cpu.length - TREND_LIMIT);
    }
    if (trend.value.mem.length > TREND_LIMIT) {
      trend.value.mem.splice(0, trend.value.mem.length - TREND_LIMIT);
    }
    if (trend.value.ts.length > TREND_LIMIT) {
      trend.value.ts.splice(0, trend.value.ts.length - TREND_LIMIT);
    }
  }

  async function loadSystemStatus() {
    const result = await apiRequest('/status');
    systemStatus.value = result?.data || null;
    const cpu = parsePercent(systemStatus.value?.cpu_usage);
    const mem = parsePercent(systemStatus.value?.memory_usage);
    pushTrendSample(cpu, mem);
    return systemStatus.value;
  }

  async function loadMetrics() {
    const headers = { ...getAuthHeaders() };
    if (metricsInFlightController) {
      try { metricsInFlightController.abort(); } catch {}
    }
    const controller = new AbortController();
    metricsInFlightController = controller;
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${getApiBase()}${API_PREFIX}/metrics`, {
        headers,
        credentials: 'include',
        signal: controller.signal,
      });
      const text = await response.text();
      if (!response.ok) {
        throw new Error(text || `HTTP ${response.status}`);
      }
      if (text !== metricsLastText) {
        metricsLastText = text;
        metricsText.value = text;
      }
      return text;
    } finally {
      clearTimeout(timer);
      if (metricsInFlightController === controller) {
        metricsInFlightController = null;
      }
    }
  }

  async function loadSystemPanel() {
    await Promise.allSettled([loadSystemStatus()]);

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

  async function refreshContainersPanel() {
    const containersStore = useContainersStore();
    await Promise.allSettled([containersStore.loadContainers(), loadSystemStatus()]);
  }

  return {
    systemStatus,
    metricsText,
    trend,
    reset,
    loadSystemStatus,
    loadMetrics,
    loadSystemPanel,
    refreshContainersPanel,
  };
});
