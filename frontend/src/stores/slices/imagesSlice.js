export function createImagesSlice() {
  return {
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
  };
}

export function resetImagesSlice(store) {
  store.images.items = [];
  store.images.stats.total = 0;
  store.images.stats.dangling = 0;
  store.images.stats.inUse = 0;
  store.images.stats.unused = 0;
  store.images.stats.totalSizeText = '0 B';
}
