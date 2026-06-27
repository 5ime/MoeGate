export function createContainersSlice() {
  return {
    containers: [],
    stats: {
      total: 0,
      running: 0,
    },
  };
}

export function resetContainersSlice(store) {
  store.containers = [];
  store.stats.total = 0;
  store.stats.running = 0;
}
