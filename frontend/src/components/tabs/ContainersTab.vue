<script setup>
import { computed, ref } from 'vue';
import BaseModal from '../BaseModal.vue';
import ConfirmModal from '../ConfirmModal.vue';
import { useConfirmAction, useFlashEffect, useInlineError } from '../../composables';
import {
  deleteComposeProject,
  deleteContainer,
  waitComposeProjectDestroyStatus,
  waitContainerDestroyStatus,
  loadComposeProjectDetail,
  loadContainerDetail,
  loadContainers,
  renewComposeProject,
  renewContainer,
  restartComposeProject,
  restartContainer,
  showMessage,
  store,
} from '../../stores/appStore';

const props = defineProps({
  containers: { type: Array, required: true },
  total: { type: Number, required: true },
  running: { type: Number, required: true },
});

const actionPending = ref(false);
const search = ref('');
const sort = ref('default');
const expandedProjects = ref({});

const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
const { flash, isFlashing } = useFlashEffect();
const { errorText, setError, clearError, matchesKey } = useInlineError();

// Detail modal state
const detailModal = ref({ open: false, title: '', data: null, loading: false, mode: '' });

function getStatusClass(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'running') return 'status-running';
  if (s === 'exited') return 'status-exited';
  return 'status-created';
}

const filteredContainers = computed(() => {
  let list = [...(props.containers || [])];
  const keyword = search.value.trim().toLowerCase();
  if (keyword) {
    list = list.filter((item) => {
      const name = (item.name || '').toLowerCase();
      const id = (item.id || '').toLowerCase();
      const pid = (item.compose_project_id || '').toLowerCase();
      return name.includes(keyword) || id.includes(keyword) || pid.includes(keyword);
    });
  }

  if (sort.value === 'nameAsc') list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  if (sort.value === 'nameDesc') list.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
  if (sort.value === 'status') list.sort((a, b) => (a.status || '').localeCompare(b.status || ''));
  return list;
});

const hasSearchKeyword = computed(() => search.value.trim().length > 0);

const composeGroupMeta = computed(() => {
  const map = new Map();
  for (const item of filteredContainers.value) {
    const projectId = item.compose_project_id;
    if (!projectId) continue;
    if (!map.has(projectId)) {
      map.set(projectId, {
        count: 1,
        leaderKey: getContainerKey(item),
      });
      continue;
    }
    map.get(projectId).count += 1;
  }
  return map;
});

const visibleContainers = computed(() => {
  return filteredContainers.value.filter((item) => {
    const projectId = item.compose_project_id;
    if (!projectId) return true;
    if (hasSearchKeyword.value) return true;
    if (isProjectLeader(item)) return true;
    return isProjectExpanded(projectId);
  });
});

function getContainerKey(item) {
  return item.id || item.name || '';
}

function isProjectLeader(item) {
  const projectId = item.compose_project_id;
  if (!projectId) return true;
  const meta = composeGroupMeta.value.get(projectId);
  return !!meta && meta.leaderKey === getContainerKey(item);
}

function isProjectExpanded(projectId) {
  return !!expandedProjects.value[projectId];
}

function toggleProject(projectId) {
  expandedProjects.value = {
    ...expandedProjects.value,
    [projectId]: !isProjectExpanded(projectId),
  };
}

function hiddenProjectContainerCount(projectId) {
  const meta = composeGroupMeta.value.get(projectId);
  if (!meta) return 0;
  return Math.max(meta.count - 1, 0);
}

const composeContainerCount = computed(() => {
  return (props.containers || []).filter((item) => !!item.compose_project_id).length;
});

const composeProjectCount = computed(() => {
  const projectIds = new Set(
    (props.containers || [])
      .map((item) => item.compose_project_id)
      .filter((projectId) => !!projectId)
  );
  return projectIds.size;
});

const standaloneContainerCount = computed(() => {
  return (props.containers || []).filter((item) => !item.compose_project_id).length;
});

// Detail modal helpers
const detailEntries = computed(() => {
  const d = detailModal.value.data;
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

function flattenObject(obj, prefix = '') {
  const entries = [];
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (Array.isArray(v)) {
      if (v.length === 0) {
        entries.push({ key, value: '-' });
      } else if (v.some(item => item && typeof item === 'object')) {
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

function formatValue(v) {
  if (v === null || v === undefined) return '-';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
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
  image: '镜像',
  command: '启动命令',
  created: '创建时间',
  state: '状态详情',
  service: '服务',
  project: '项目',
  containerid: '容器ID',
  containername: '容器名称',
  containerip: '容器IP',
  containerport: '容器端口',
  composeprojectid: 'Compose项目ID',
  hostip: '主机IP',
  hostport: '主机端口',
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
  const mapKey = clean.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  if (FIELD_LABEL_MAP[mapKey]) return FIELD_LABEL_MAP[mapKey];
  const spaced = clean
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_\-]+/g, ' ')
    .trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function sectionItemCount(section) {
  const arrayCount = (section.arrayGroups || []).reduce((sum, bucket) => sum + bucket.items.length, 0);
  return (section.items || []).length + arrayCount;
}

function formatContainerId(id) {
  const value = String(id || '').trim();
  if (!value) return '-';
  if (value.length <= 28) return value;
  return `${value.slice(0, 12)}...${value.slice(-12)}`;
}

async function refreshAll() {
  await loadContainers();
}

async function viewContainer(containerId) {
  try {
    clearError();
    detailModal.value = { open: true, title: `容器详情`, data: null, loading: true, mode: 'container' };
    const data = await loadContainerDetail(containerId);
    detailModal.value.data = data;
    detailModal.value.loading = false;
    flash('container', containerId);
  } catch (error) {
    detailModal.value.loading = false;
    detailModal.value.open = false;
    setError(`container:${containerId}`, error.message || '加载容器详情失败');
    showMessage(error.message || '加载容器详情失败', 'error');
  }
}

async function viewProject(projectId) {
  try {
    clearError();
    detailModal.value = { open: true, title: `Compose 项目详情`, data: null, loading: true, mode: 'project' };
    const data = await loadComposeProjectDetail(projectId);
    detailModal.value.data = data;
    detailModal.value.loading = false;
    flash('project', projectId);
  } catch (error) {
    detailModal.value.loading = false;
    detailModal.value.open = false;
    setError(`project:${projectId}`, error.message || '加载 Compose 项目详情失败');
    showMessage(error.message || '加载 Compose 项目详情失败', 'error');
  }
}

function closeDetail() {
  detailModal.value = { open: false, title: '', data: null, loading: false, mode: '' };
}

function containerAction({ title, message, danger = false, id, type, apiFn, successMsg, failMsg, shouldFlash = true }) {
  requestConfirm(title, message, async () => {
    try {
      clearError();
      actionPending.value = true;
      await apiFn(id);
      await refreshAll();
      if (shouldFlash) flash(type, id);
      showMessage(successMsg, 'success');
    } catch (error) {
      setError(`${type}:${id}`, error.message || failMsg);
      showMessage(error.message || failMsg, 'error');
    } finally {
      actionPending.value = false;
    }
  }, danger);
}

function restartManagedContainer(id) {
  containerAction({ title: '重启容器', message: '确定要重启这个容器吗？', id, type: 'container', apiFn: restartContainer, successMsg: '容器重启成功', failMsg: '容器重启失败' });
}

function renewManagedContainer(id) {
  containerAction({ title: '续期容器', message: '确定要续期这个容器吗？', id, type: 'container', apiFn: renewContainer, successMsg: '容器续期成功', failMsg: '容器续期失败' });
}

async function monitorContainerDeletion(id) {
  try {
    await waitContainerDestroyStatus(id);
    await refreshAll();
    showMessage('容器删除成功', 'success');
  } catch (error) {
    setError(`container:${id}`, error.message || '容器删除失败');
    showMessage(error.message || '容器删除失败', 'error');
    await refreshAll();
  }
}

function removeManagedContainer(id) {
  requestConfirm('删除容器', '确定要删除这个容器吗？此操作不可恢复。', async () => {
    try {
      clearError();
      actionPending.value = true;
      await deleteContainer(id);
      showMessage('删除任务已提交，正在后台执行...', 'info');
      void monitorContainerDeletion(id);
    } catch (error) {
      setError(`container:${id}`, error.message || '容器删除失败');
      showMessage(error.message || '容器删除失败', 'error');
      await refreshAll();
    } finally {
      actionPending.value = false;
    }
  }, true);
}

function restartProject(id) {
  containerAction({ title: '重启 Compose 项目', message: '确定要重启整个 Compose 项目吗？', id, type: 'project', apiFn: restartComposeProject, successMsg: 'Compose 项目重启成功', failMsg: 'Compose 项目重启失败' });
}

function renewProject(id) {
  containerAction({ title: '续期 Compose 项目', message: '确定要续期整个 Compose 项目吗？', id, type: 'project', apiFn: renewComposeProject, successMsg: 'Compose 项目续期成功', failMsg: 'Compose 项目续期失败' });
}

async function monitorProjectDeletion(id, result) {
  try {
    await waitComposeProjectDestroyStatus(result);
    await refreshAll();
    showMessage('Compose 项目删除成功', 'success');
  } catch (error) {
    setError(`project:${id}`, error.message || 'Compose 项目删除失败');
    showMessage(error.message || 'Compose 项目删除失败', 'error');
    await refreshAll();
  }
}

function removeProject(id) {
  requestConfirm('删除 Compose 项目', '确定要删除整个 Compose 项目吗？此操作不可恢复。', async () => {
    try {
      clearError();
      actionPending.value = true;
      const result = await deleteComposeProject(id);
      showMessage('Compose 删除任务已提交，正在后台执行...', 'info');
      void monitorProjectDeletion(id, result);
    } catch (error) {
      setError(`project:${id}`, error.message || 'Compose 项目删除失败');
      showMessage(error.message || 'Compose 项目删除失败', 'error');
      await refreshAll();
    } finally {
      actionPending.value = false;
    }
  }, true);
}
</script>

<template>
  <section class="space-y-6">
    <div class="rounded-md border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">容器总览</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">运行概况</h2>
        </div>
        <button
          id="gotoSystemBtn"
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
          @click="store.activeTab = 'system'"
        >
          查看系统监控
        </button>
      </div>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">总容器数</span>
          <span id="totalContainers" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ total }}</span>
        </div>
        <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">运行中</span>
          <span id="runningContainers" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ running }}</span>
        </div>
        <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">独立容器数</span>
          <span class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ standaloneContainerCount }}</span>
        </div>
        <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Docker Compose</span>
          <div class="mt-1 flex items-baseline gap-2">
            <span class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ composeContainerCount }}</span>
            <span class="text-xs font-medium text-slate-500">容器</span>
            <span class="text-slate-300">/</span>
            <span class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ composeProjectCount }}</span>
            <span class="text-xs font-medium text-slate-500">项目</span>
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-md border border-slate-200 p-4 md:p-5">
      <div class="flex items-center gap-3 max-md:flex-col max-md:items-stretch">
        <input v-model="search" id="containerSearch" type="text" placeholder="搜索名称/ID/项目..." class="min-w-[240px] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-4 focus:ring-slate-100 max-md:min-w-0 max-md:w-full" />
        <div class="relative min-w-[120px] max-md:min-w-0 max-md:w-full">
          <select
            v-model="sort"
            id="containerSort"
            class="h-[38px] w-full appearance-none rounded-lg border border-slate-200 bg-white pl-3 pr-9 text-sm font-medium text-slate-800 transition hover:border-slate-300 focus:border-slate-500 focus:outline-none focus:ring-4 focus:ring-slate-100"
          >
            <option value="default">默认排序</option>
            <option value="status">状态优先</option>
            <option value="nameAsc">名称（A 到 Z）</option>
            <option value="nameDesc">名称（Z 到 A）</option>
          </select>
          <svg class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </div>
      </div>
    </div>

    <div
      id="containersList"
      class="columns-1 md:columns-2 xl:columns-2 gap-5 [column-gap:1.25rem]"
      v-if="visibleContainers.length"
    >
      <div
        class="mb-5 break-inside-avoid rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition "
        :class="isFlashing('container', item.id) || isFlashing('project', item.compose_project_id) ? 'entity-flash' : ''"
        v-for="item in visibleContainers"
        :key="item.id || item.name"
      >
        <div class="mb-4 flex items-start justify-between border-b border-slate-100 pb-3">
          <div class="min-w-0 flex-1">
            <div class="break-words text-lg font-semibold tracking-tight text-slate-900">{{ item.name || item.id || '未知容器' }}</div>
            <div class="mt-1.5 font-mono text-xs tracking-wide text-slate-400" :title="item.id || '-'">ID: {{ formatContainerId(item.id) }}</div>
          </div>
          <span
            class="ml-3 flex-shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider"
            :class="getStatusClass(item.status) === 'status-running'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : getStatusClass(item.status) === 'status-exited'
                ? 'border-rose-200 bg-rose-50 text-rose-700'
                : 'border-slate-200 bg-slate-50 text-slate-700'"
          >{{ item.status || 'unknown' }}</span>
        </div>

        <div class="my-4 grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
          <div class="flex items-start justify-between" v-if="item.compose_project_id">
            <span class="text-[12px] font-medium text-slate-500">Compose 项目</span>
            <span class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.compose_project_id }}</span>
          </div>
          <div class="flex items-start justify-between" v-if="item.start_time">
            <span class="text-[12px] font-medium text-slate-500">启动时间</span>
            <span class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.start_time }}</span>
          </div>
          <div class="flex items-start justify-between" v-if="item.remaining_time !== undefined">
            <span class="text-[12px] font-medium text-slate-500">剩余时间</span>
            <span class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.remaining_time }} 秒</span>
          </div>
          <div class="flex items-start justify-between">
            <span class="text-[12px] font-medium text-slate-500">端口映射</span>
            <div class="flex max-w-[60%] flex-col items-end gap-1.5" v-if="item.ports && Object.keys(item.ports).length">
              <div class="rounded border border-slate-200 bg-white px-2.5 py-1 font-mono text-[11px] text-slate-900" v-for="(target, source) in item.ports" :key="source">
                {{ source }} -> {{ Array.isArray(target) ? (target[0] && target[0].HostPort) : target }}
              </div>
            </div>
            <div class="max-w-[60%] break-words text-right text-[12px] font-semibold text-slate-800" v-else>无端口映射</div>
          </div>
        </div>

        <div class="border-t border-slate-100 pt-3.5">
          <div class="flex items-center gap-2">
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="viewContainer(item.id)">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
              详情
            </button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="restartManagedContainer(item.id)" title="重启容器">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              重启
            </button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="renewManagedContainer(item.id)" title="续期容器">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              续期
            </button>
            <span class="flex-1"></span>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="removeManagedContainer(item.id)" title="删除容器">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              删除
            </button>
          </div>
          <div v-if="item.compose_project_id && isProjectLeader(item)" class="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
            <span class="mr-1 text-[11px] font-medium uppercase tracking-wider text-slate-400">项目</span>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="viewProject(item.compose_project_id)" title="项目详情">详情</button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="restartProject(item.compose_project_id)" title="重启项目">重启</button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="renewProject(item.compose_project_id)" title="续期项目">续期</button>
            <button
              v-if="!hasSearchKeyword && hiddenProjectContainerCount(item.compose_project_id) > 0"
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              type="button"
              :disabled="actionPending"
              @click="toggleProject(item.compose_project_id)"
            >
              {{ isProjectExpanded(item.compose_project_id) ? '收起其余容器' : `展开其余 ${hiddenProjectContainerCount(item.compose_project_id)} 个容器` }}
            </button>
            <span class="flex-1"></span>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="removeProject(item.compose_project_id)" title="删除项目">删除</button>
          </div>
        </div>

        <p
          v-if="errorText && (matchesKey(`container:${item.id}`) || (item.compose_project_id && isProjectLeader(item) && matchesKey(`project:${item.compose_project_id}`)))"
          class="mt-2 text-xs leading-5 text-slate-600"
        >
          {{ errorText }}
        </p>
      </div>
    </div>

    <div v-else class="rounded-[16px] border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-700">暂无容器</div>

    <BaseModal
      :visible="detailModal.open"
      :title="detailModal.title"
      :icon="detailModal.loading ? 'loading' : 'bolt'"
      width="max-w-[980px]"
      @close="closeDetail"
    >
      <div class="max-h-[70vh] overflow-y-auto">
        <div v-if="detailModal.loading" class="flex items-center justify-center py-12">
          <svg class="h-5 w-5 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          <span class="ml-2 text-sm text-slate-500">加载中...</span>
        </div>
        <template v-else-if="detailModal.data">
          <div class="space-y-3">
            <div class="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">数据摘要</p>
              <p class="mt-1 text-sm text-slate-700">共 {{ detailEntries.length }} 个字段，按 {{ detailSections.length }} 个分组展示</p>
            </div>

            <div v-if="detailModal.mode === 'container'" class="overflow-hidden rounded-2xl border border-slate-200 bg-white p-4">
              <div class="mb-2 flex items-center justify-between">
                <h4 class="text-sm font-semibold tracking-tight text-slate-900">容器信息</h4>
                <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ detailEntries.length }} 项</span>
              </div>

              <!-- 容器ID 独占一行展示 -->
              <div
                v-for="entry in detailEntries.filter(e => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) === '容器ID')"
                :key="entry.key"
                class="mb-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3"
              >
                <p class="text-xs font-semibold text-slate-700" :title="entry.key">容器ID</p>
                <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                  {{ formatValue(entry.value) }}
                </div>
              </div>

              <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div
                  v-for="entry in detailEntries.filter(e => formatTokenLabel((e.key.split('.').slice(-1)[0] || e.key)) !== '容器ID')"
                  :key="entry.key"
                  class="rounded-xl border border-slate-200 bg-slate-50/60 p-3"
                >
                  <p class="text-xs font-semibold text-slate-700" :title="entry.key">
                    {{ formatTokenLabel(entry.key.split('.').slice(-1)[0] || entry.key) }}
                  </p>
                  <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                    {{ formatValue(entry.value) }}
                  </div>
                </div>
              </div>
            </div>

            <div v-else v-for="section in detailSections" :key="section.key" class="overflow-hidden rounded-2xl border border-slate-200 bg-white p-4">
              <div class="mb-2 flex items-center justify-between">
                <h4 class="text-sm font-semibold tracking-tight text-slate-900">{{ section.title }}</h4>
                <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">{{ sectionItemCount(section) }} 项</span>
              </div>
              <div v-if="section.items.length" class="divide-y divide-slate-100">
                <div
                  v-for="entry in section.items"
                  :key="entry.key"
                >
                  <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">{{ formatValue(entry.value) }}</div>
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
                    <!-- 容器ID 独占一行 -->
                    <div
                      v-for="entry in bucket.items.filter(e => e.label === '容器ID')"
                      :key="entry.key"
                      class="px-3 py-2.5"
                    >
                      <div class="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                        <p class="text-xs font-semibold text-slate-700" :title="entry.key">{{ entry.label }}</p>
                        <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                          {{ formatValue(entry.value) }}
                        </div>
                      </div>
                    </div>
                    <!-- 其他字段两列排布 -->
                    <div class="px-3 py-2.5">
                      <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <div
                          v-for="entry in bucket.items.filter(e => e.label !== '容器ID')"
                          :key="entry.key"
                          class="rounded-xl border border-slate-200 bg-slate-50/60 p-3"
                        >
                          <p class="text-xs font-semibold text-slate-700" :title="entry.key">{{ entry.label }}</p>
                          <div class="mt-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] leading-5 text-slate-800 break-all whitespace-pre-wrap">
                            {{ formatValue(entry.value) }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="py-12 text-center text-sm text-slate-400">暂无数据</div>
      </div>
    </BaseModal>

    <ConfirmModal
      :visible="confirmModal.open"
      :title="confirmModal.title"
      :message="confirmModal.message"
      :danger="confirmModal.danger"
      :loading="confirmModal.loading"
      @confirm="onConfirm"
      @cancel="onCancelConfirm"
    />
  </section>
</template>
