export const API_PREFIX = '/api/v1';
const CSRF_COOKIE_NAME = 'moegate_csrf';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

export function getApiBase() {
  const stored = localStorage.getItem('apiBase');
  return (stored && stored.trim()) || getConfiguredDefaultApiBase() || window.location.origin;
}

function getConfiguredDefaultApiBase() {
  const envBase = String(import.meta.env?.VITE_API_BASE || '').trim();
  if (!envBase) return '';
  return envBase.replace(/\/+$/, '');
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

export function getCsrfToken() {
  if (typeof document === 'undefined') return '';
  const prefix = `${CSRF_COOKIE_NAME}=`;
  return document.cookie
    .split(';')
    .map((part) => part.trim())
    .filter((part) => part.startsWith(prefix))
    .map((part) => decodeURIComponent(part.slice(prefix.length)))[0] || '';
}

export function getAuthHeaders({ includeCsrf = true } = {}) {
  const headers = {};
  if (includeCsrf) {
    const csrf = getCsrfToken();
    if (csrf) headers[CSRF_HEADER_NAME] = csrf;
  }
  return headers;
}

let unauthorizedHandler = null;

export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

function notifyUnauthorized(response) {
  if (response?.status === 401 && typeof unauthorizedHandler === 'function') {
    unauthorizedHandler();
  }
}

async function parseJsonResponse(response) {
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {};
  }
  if (!response.ok) {
    notifyUnauthorized(response);
    const msg = normalizeApiErrorMessage(data?.msg || data?.message || `HTTP ${response.status}`);
    throw new Error(msg);
  }
  return data;
}

export async function checkSession() {
  const response = await fetch(`${getApiBase()}${API_PREFIX}/auth/session`, {
    credentials: 'include',
  });
  return parseJsonResponse(response);
}

export async function loginWithCookie(apiKey) {
  const response = await fetch(`${getApiBase()}${API_PREFIX}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
  });
  return parseJsonResponse(response);
}

export async function logoutSession() {
  const response = await fetch(`${getApiBase()}${API_PREFIX}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: getAuthHeaders(),
  });
  return parseJsonResponse(response);
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
  const headers = { 'Content-Type': 'application/json', ...getAuthHeaders() };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${getApiBase()}${API_PREFIX}${endpoint}`, {
      method,
      headers,
      credentials: 'include',
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
      notifyUnauthorized(response);
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
