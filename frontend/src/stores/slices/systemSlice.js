export function createSystemSlice() {
  return {
    systemStatus: null,
    metricsText: '',
    trend: {
      cpu: [],
      mem: [],
      ts: [],
    },
  };
}

export function resetSystemSlice(store) {
  store.systemStatus = null;
  store.metricsText = '';
  store.trend.cpu = [];
  store.trend.mem = [];
  store.trend.ts = [];
}
