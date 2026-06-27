import { ref } from 'vue';
import { defineStore } from 'pinia';
import { apiRequest } from '../api/client';

export const useImagesStore = defineStore('images', () => {
  const images = ref({
    items: [],
    stats: {
      total: 0,
      dangling: 0,
      inUse: 0,
      unused: 0,
      totalSizeText: '0 B',
    },
  });

  function reset() {
    images.value.items = [];
    images.value.stats.total = 0;
    images.value.stats.dangling = 0;
    images.value.stats.inUse = 0;
    images.value.stats.unused = 0;
    images.value.stats.totalSizeText = '0 B';
  }

  async function loadImages() {
    const result = await apiRequest('/images');
    const data = result?.data || {};
    const items = data.images || [];
    images.value.items = items;
    images.value.stats.total = Number(data.total ?? items.length) || 0;
    images.value.stats.dangling = Number(data.dangling ?? items.filter((item) => !!item?.is_dangling).length) || 0;
    images.value.stats.inUse = Number(data.in_use ?? items.filter((item) => Number(item?.containers_using || 0) > 0).length) || 0;
    images.value.stats.unused = Number(data.unused ?? items.filter((item) => Number(item?.containers_using || 0) <= 0).length) || 0;
    images.value.stats.totalSizeText = String(data.total_size_text || '0 B');
    return items;
  }

  async function refreshImagesPanel() {
    await loadImages();
  }

  return {
    images,
    reset,
    loadImages,
    refreshImagesPanel,
  };
});

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
