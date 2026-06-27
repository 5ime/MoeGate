export function createSettingsSlice() {
  return {
    settings: {
      imageSource: '',
      networking: {
        composeManagedSubnetPool: '172.30.0.0/16',
        composeManagedSubnetPrefix: 24,
      },
      alerts: {
        webhookUrl: '',
        webhookUrlSet: false,
        webhookUrlMasked: '',
        webhookTimeout: 5,
      },
      containerLimits: {
        maxContainers: 30,
        maxRenewTimes: 3,
      },
      containerDefaults: {
        maxTime: 3600,
        minPort: 20000,
        maxPort: 30000,
        memoryLimit: '512m',
        cpuLimit: 1.0,
        cpuShares: 1024,
      },
    },
  };
}
