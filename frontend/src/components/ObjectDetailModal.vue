<script setup>
import { computed } from 'vue';
import BaseModal from './BaseModal.vue';
import SectionCard from './ui/SectionCard.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  data: { type: [Object, Array, String, Number, Boolean], default: null },
  mode: { type: String, default: '' }, // 'container' | 'project' | ...
  width: { type: String, default: 'max-w-[980px]' },
});

const emit = defineEmits(['close']);

function flattenObject(obj, prefix = '') {
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

function normalizeToken(token) {
  return String(token || '')
    .replace(/\[\d+\]/g, '')
    .replace(/[^a-zA-Z0-9_\-]/g, '')
    .toLowerCase();
}

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

function formatTokenLabel(token) {
  const clean = String(token || '').replace(/\[\d+\]/g, '').trim();
  if (!clean) return '';
  // 端口键（例如：9000/tcp、53/udp）显示为中文
  if (/^\d+\/(tcp|udp)$/i.test(clean)) return `端口 ${clean}`;
  const mapKey = clean.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  if (FIELD_LABEL_MAP[mapKey]) return FIELD_LABEL_MAP[mapKey];
  const spaced = clean
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_\-]+/g, ' ')
    .trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function formatValue(v) {
  if (v === null || v === undefined) return '-';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

const detailEntries = computed(() => {
  const d = props.data;
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

function sectionItemCount(section) {
  const arrayCount = (section.arrayGroups || []).reduce((sum, bucket) => sum + bucket.items.length, 0);
  return (section.items || []).length + arrayCount;
}
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="title"
    :icon="loading ? 'loading' : 'bolt'"
    :width="width"
    @close="emit('close')"
  >
    <div class="max-h-[70vh] overflow-y-auto">
      <div v-if="loading" class="flex items-center justify-center py-12">
        <svg class="h-5 w-5 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span class="ml-2 text-sm text-slate-500">加载中...</span>
      </div>

      <template v-else-if="data && typeof data === 'object'">
        <div class="space-y-3">
          <SectionCard variant="muted">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">数据摘要</p>
            <p class="mt-1 text-sm text-slate-700">共 {{ detailEntries.length }} 个字段，按 {{ detailSections.length }} 个分组展示</p>
          </SectionCard>

          <SectionCard v-if="mode === 'container'" title="容器信息">
            <template #header>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailEntries.length }} 项</span>
            </template>

            <div
              v-for="entry in detailEntries.filter((e) => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) === '容器ID')"
              :key="entry.key"
              class="mb-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3"
            >
              <p class="text-xs font-semibold text-slate-700" :title="entry.key">容器ID</p>
              <div class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                {{ formatValue(entry.value) }}
              </div>
            </div>

            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div
                v-for="entry in detailEntries.filter((e) => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) !== '容器ID')"
                :key="entry.key"
                class="rounded-xl border border-slate-200 bg-slate-50/60 p-3"
              >
                <p class="text-xs font-semibold text-slate-700" :title="entry.key">
                  {{ formatTokenLabel(entry.key.split('.').slice(-1)[0] || entry.key) }}
                </p>
                <div class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ formatValue(entry.value) }}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            v-else
            v-for="section in detailSections"
            :key="section.key"
            :title="section.title"
          >
            <template #header>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ sectionItemCount(section) }} 项</span>
            </template>

            <div v-if="section.items.length" class="divide-y divide-slate-100">
              <div v-for="entry in section.items" :key="entry.key">
                <div class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ formatValue(entry.value) }}
                </div>
              </div>
            </div>

            <div v-if="section.arrayGroups.length" class="mt-3 space-y-3">
              <div
                v-for="bucket in section.arrayGroups"
                :key="bucket.key"
                class="overflow-hidden rounded-xl border border-slate-200 bg-white"
              >
                <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
                  <p class="text-xs font-semibold text-slate-800">{{ bucket.title }}</p>
                  <span class="text-[11px] font-medium text-slate-500">{{ bucket.items.length }} 项</span>
                </div>
                <div class="divide-y divide-slate-100">
                  <div
                    v-for="entry in bucket.items.filter((e) => e.label === '容器ID')"
                    :key="entry.key"
                    class="px-3 py-2.5"
                  >
                    <div class="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                      <p class="text-xs font-semibold text-slate-700" :title="entry.key">{{ entry.label }}</p>
                      <div class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                        {{ formatValue(entry.value) }}
                      </div>
                    </div>
                  </div>

                  <div class="px-3 py-2.5">
                    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div
                        v-for="entry in bucket.items.filter((e) => e.label !== '容器ID')"
                        :key="entry.key"
                        class="rounded-xl border border-slate-200 bg-slate-50/60 p-3"
                      >
                        <p class="text-xs font-semibold text-slate-700" :title="entry.key">{{ entry.label }}</p>
                        <div class="mt-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                          {{ formatValue(entry.value) }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      </template>

      <div v-else class="py-12 text-center text-sm text-slate-400">暂无数据</div>
    </div>
  </BaseModal>
</template>

