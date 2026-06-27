import { computed } from 'vue';

const FIELD_LABEL_MAP = {
  id: 'ID',
  name: '名称',
  status: '容器状态',
  uuid: 'UUID',
  image: '镜像',
  command: '启动命令',
  created: '创建时间',
  state: '状态详情',
  service: '服务',
  project: '项目',
  containerid: '容器ID',
  containeruuid: '容器UUID',
  containername: '容器名称',
  containerip: '容器IP',
  containerport: '容器端口',
  composeprojectid: 'Compose项目ID',
  hostip: '主机IP',
  hostport: '主机端口',
  localip: '本地IP',
  localport: '本地端口',
  remoteport: '远程端口',
  customdomains: '自定义域名',
  type: 'FRP类型',
  ports: '端口映射',
  networks: '网络',
  networkmode: '网络模式',
  mounts: '挂载',
  labels: '标签',
  env: '环境变量',
  restartpolicy: '重启策略',
  starttime: '启动时间',
  remainingtime: '剩余时间',
};

export function flattenObject(obj, prefix = '') {
  const entries = [];
  if (!obj || typeof obj !== 'object') return entries;
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (Array.isArray(v)) {
      if (v.length === 0) {
        entries.push({ key, value: '-' });
      } else if (v.some((item) => item && typeof item === 'object')) {
        v.forEach((item, i) => {
          if (item && typeof item === 'object') {
            entries.push(...flattenObject(item, `${key}[${i}]`));
          } else {
            entries.push({ key: `${key}[${i}]`, value: item });
          }
        });
      } else {
        entries.push({ key, value: v.join(', ') });
      }
    } else if (v && typeof v === 'object') {
      entries.push(...flattenObject(v, key));
    } else {
      entries.push({ key, value: v });
    }
  }
  return entries;
}

export function normalizeToken(token) {
  return String(token || '')
    .replace(/\[\d+\]/g, '')
    .replace(/[^a-zA-Z0-9_\-]/g, '')
    .toLowerCase();
}

export function formatTokenLabel(token) {
  const clean = String(token || '').replace(/\[\d+\]/g, '').trim();
  if (!clean) return '';
  if (/^\d+\/(tcp|udp)$/i.test(clean)) return `端口 ${clean}`;
  const mapKey = clean.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  if (FIELD_LABEL_MAP[mapKey]) return FIELD_LABEL_MAP[mapKey];
  const spaced = clean
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_\-]+/g, ' ')
    .trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatDetailValue(v) {
  if (v === null || v === undefined) return '-';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function sectionItemCount(section) {
  const arrayCount = (section.arrayGroups || []).reduce((sum, bucket) => sum + bucket.items.length, 0);
  return (section.items || []).length + arrayCount;
}

export function useObjectDetail(dataRef) {
  const detailEntries = computed(() => {
    const d = dataRef.value;
    if (!d || typeof d !== 'object') return [];
    return flattenObject(d);
  });

  const detailSections = computed(() => {
    const sections = new Map();
    for (const entry of detailEntries.value) {
      const [rawGroup = 'General'] = String(entry.key || '').split('.');
      const groupKey = normalizeToken(rawGroup) || 'general';
      if (!sections.has(groupKey)) {
        sections.set(groupKey, {
          key: groupKey,
          title: formatTokenLabel(rawGroup) || 'General',
          items: [],
          arrayGroups: new Map(),
        });
      }
      const section = sections.get(groupKey);
      const pathParts = String(entry.key || '').split('.');
      const leaf = pathParts[pathParts.length - 1] || entry.key;
      const normalizedItem = {
        key: entry.key,
        label: formatTokenLabel(leaf),
        value: entry.value,
      };

      const rootToken = pathParts[0] || '';
      const rootMatch = rootToken.match(/^(.+)\[(\d+)\]$/);
      if (rootMatch) {
        const listName = formatTokenLabel(rootMatch[1]) || 'Item';
        const index = Number(rootMatch[2]);
        const bucketKey = `${normalizeToken(rootMatch[1])}:${index}`;
        if (!section.arrayGroups.has(bucketKey)) {
          section.arrayGroups.set(bucketKey, {
            key: bucketKey,
            title: `${listName} #${Number.isNaN(index) ? '-' : index + 1}`,
            items: [],
            order: Number.isNaN(index) ? 9999 : index,
          });
        }
        section.arrayGroups.get(bucketKey).items.push(normalizedItem);
      } else {
        section.items.push(normalizedItem);
      }
    }
    return Array.from(sections.values()).map((section) => ({
      ...section,
      arrayGroups: Array.from(section.arrayGroups.values()).sort((a, b) => a.order - b.order),
    }));
  });

  return { detailEntries, detailSections };
}
