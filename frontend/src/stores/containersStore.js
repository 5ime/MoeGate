import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest } from '../api/client';
import { useUiStore } from './uiStore';

export const useContainersStore = defineStore('containers', () => {
  const containers = ref([]);
  const stats = ref({
    total: 0,
    running: 0,
  });

  function reset() {
    containers.value = [];
    stats.value.total = 0;
    stats.value.running = 0;
  }

  async function loadContainers() {
    const result = await apiRequest('/containers');
    const list = result?.data?.containers || [];
    containers.value = list;
    stats.value.total = list.length;
    stats.value.running = list.filter((item) => String(item.status || '').toLowerCase() === 'running').length;
  }

  return {
    containers,
    stats,
    reset,
    loadContainers,
  };
});

export async function createContainer(payload) {
  const result = await apiRequest('/containers', {
    method: 'POST',
    body: payload,
    timeoutMs: 300000,
  });
  return result;
}

export async function loadContainerDetail(containerId) {
  const uiStore = useUiStore();
  const result = await apiRequest(`/containers/${encodeURIComponent(containerId)}`);
  const payload = result?.data || null;
  uiStore.openDetailPanel(`容器详情: ${containerId}`, payload);
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
  const uiStore = useUiStore();
  const result = await apiRequest(`/containers/project/${encodeURIComponent(projectId)}`);
  const payload = result?.data || null;
  uiStore.openDetailPanel(`Compose 项目详情: ${projectId}`, payload);
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
