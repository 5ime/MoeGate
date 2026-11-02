import { apiRequest } from '../api/client';

function containerLogsBase(containerId) {
  return `/containers/${encodeURIComponent(containerId)}/logs`;
}

export async function loadContainerLogs(containerId, { tail = 200, timestamps = false, since = '' } = {}) {
  const params = new URLSearchParams();
  params.set('tail', String(tail));
  if (timestamps) params.set('timestamps', 'true');
  if (since !== '' && since !== null && since !== undefined) params.set('since', String(since));

  const result = await apiRequest(`${containerLogsBase(containerId)}?${params.toString()}`, {
    timeoutMs: 20000,
  });
  return result?.data || null;
}
