export function createNetworksSlice() {
  return {
    networks: {
      items: [],
      stats: {
        total: 0,
        inUse: 0,
        idle: 0,
        composeBound: 0,
      },
    },
  };
}

export function resetNetworksSlice(store) {
  store.networks.items = [];
  store.networks.stats.total = 0;
  store.networks.stats.inUse = 0;
  store.networks.stats.idle = 0;
  store.networks.stats.composeBound = 0;
}
