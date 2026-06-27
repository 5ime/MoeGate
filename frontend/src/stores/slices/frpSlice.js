export function createFrpSlice() {
  return {
    frp: {
      enabled: false,
      settings: {
        serverAddr: '',
        serverPort: 7000,
        vhostHttpPort: null,
        adminIp: '127.0.0.1',
        adminPort: 7400,
        adminUser: '',
        adminPassword: '',
        adminPasswordSet: false,
        useDomain: false,
        domainSuffix: '',
      },
      healthText: '未检查',
      health: {
        enabled: false,
        overallOk: false,
        serverReachable: false,
        adminReachable: false,
      },
      proxies: [],
      configText: '',
    },
  };
}

export function resetFrpSlice(store) {
  store.frp.enabled = false;
  store.frp.healthText = '未检查';
  store.frp.health.enabled = false;
  store.frp.health.overallOk = false;
  store.frp.health.serverReachable = false;
  store.frp.health.adminReachable = false;
  store.frp.proxies = [];
  store.frp.configText = '';
}
