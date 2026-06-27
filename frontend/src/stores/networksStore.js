import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest } from '../api/client';

export const useNetworksStore = defineStore('networks', () => {
  const networks = ref({
    items: [],
    stats: {
      total: 0,
      inUse: 0,
      idle: 0,
      composeBound: 0,
    },
  });

  function reset() {
    networks.value.items = [];
    networks.value.stats.total = 0;
    networks.value.stats.inUse = 0;
    networks.value.stats.idle = 0;
    networks.value.stats.composeBound = 0;
  }

  async function loadManagedNetworks() {
    const result = await apiRequest('/networks');
    const items = result?.data?.networks || [];
    networks.value.items = items;
    networks.value.stats.total = Number(result?.data?.total ?? items.length) || 0;
    networks.value.stats.inUse = Number(result?.data?.in_use ?? items.filter((item) => item?.is_in_use).length) || 0;
    networks.value.stats.idle = Number(result?.data?.idle ?? items.filter((item) => !item?.is_in_use).length) || 0;
    networks.value.stats.composeBound = items.filter((item) => !!item?.compose_project_id).length;
    return items;
  }

  async function refreshNetworksPanel() {
    await loadManagedNetworks();
  }

  return {
    networks,
    reset,
    loadManagedNetworks,
    refreshNetworksPanel,
  };
});

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
