export const API_PREFIX = '/api/v1';

export function getApiBase() {
  const stored = localStorage.getItem('apiBase');
  return (stored && stored.trim()) || window.location.origin;
}

export function setApiBase(base) {
  const value = String(base || '').trim();
  if (!value) {
    localStorage.removeItem('apiBase');
    return '';
  }
  if (!/^https?:\/\//i.test(value)) {
    throw new Error('API Base 必须以 http:// 或 https:// 开头');
  }
  const normalized = value.replace(/\/+$/, '');
  localStorage.setItem('apiBase', normalized);
  return normalized;
}

export function getApiKey() {
  return localStorage.getItem('apiKey') || '';
}

export function saveApiKey(key) {
  localStorage.setItem('apiKey', key);
}

export function clearApiKey() {
  localStorage.removeItem('apiKey');
}

function normalizeApiErrorMessage(message) {
  const text = String(message || '').trim();
  if (!text) return '';

  const lowered = text.toLowerCase();
  if (
    lowered.includes('all predefined address pools have been fully subnetted')
    || lowered.includes('could not find an available, non-overlapping ipv4 address pool')
  ) {
    return 'Docker 网络地址池已耗尽，请删除未使用的 Compose 项目或清理无用网络后重试';
  }

  return text;
}

export async function apiRequest(endpoint, { method = 'GET', body = null, timeoutMs = 15000 } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) headers['X-API-Key'] = key;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${getApiBase()}${API_PREFIX}${endpoint}`, {
      method,
      headers,
      signal: controller.signal,
      body: body && method !== 'GET' ? JSON.stringify(body) : null,
    });

    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = {};
    }

    if (!response.ok) {
      const msg = normalizeApiErrorMessage(data?.msg || data?.message || `HTTP ${response.status}`);
      throw new Error(msg);
    }

    return data;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('请求超时，请稍后重试');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
