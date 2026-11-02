import { API_PREFIX, apiRequest, getApiBase, getAuthHeaders } from '../api/client';

function containerBase(containerId) {
  return `/containers/${encodeURIComponent(containerId)}/traffic`;
}

export async function loadTrafficStatus(containerId) {
  const result = await apiRequest(containerBase(containerId));
  return result?.data || null;
}

export async function loadTrafficSummary(containerId, { maxPackets = 20000, maxHttp = 200 } = {}) {
  const query = `?max_packets=${encodeURIComponent(maxPackets)}&max_http=${encodeURIComponent(maxHttp)}`;
  const result = await apiRequest(`${containerBase(containerId)}/summary${query}`, { timeoutMs: 60000 });
  return result?.data || null;
}

export async function startTrafficCapture(containerId) {
  const result = await apiRequest(`${containerBase(containerId)}/start`, {
    method: 'POST',
    timeoutMs: 60000,
  });
  return result?.data || null;
}

export async function stopTrafficCapture(containerId) {
  const result = await apiRequest(`${containerBase(containerId)}/stop`, { method: 'POST' });
  return result?.data || null;
}

/**
 * 下载 pcap：走 fetch + blob，而不是 <a href>，
 * 这样会话 Cookie / CSRF 逻辑与其它接口一致，也不受 /api 基址差异影响。
 */
export async function downloadTrafficCapture(containerId, filename) {
  const url = `${getApiBase()}${API_PREFIX}${containerBase(containerId)}/${encodeURIComponent(filename)}`;
  const response = await fetch(url, {
    credentials: 'include',
    headers: getAuthHeaders({ includeCsrf: false }),
  });

  if (!response.ok) {
    let message = `下载失败（HTTP ${response.status}）`;
    try {
      const data = await response.json();
      message = data?.msg || message;
    } catch {
      // 非 JSON 响应（如 Nginx 413），保留默认提示
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 4000);
  return blob.size;
}
