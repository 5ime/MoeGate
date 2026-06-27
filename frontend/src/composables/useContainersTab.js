import { computed, ref } from 'vue';
import {
  deleteComposeProject,
  deleteContainer,
  loadComposeProjectDetail,
  loadContainerDetail,
  renewComposeProject,
  renewContainer,
  restartComposeProject,
  restartContainer,
  useContainersStore,
  waitComposeProjectDestroyStatus,
  waitContainerDestroyStatus,
} from '../stores/containersStore';
import { useUiStore } from '../stores/uiStore';
import { useConfirmAction, useFlashEffect, useInlineError } from './index';

export function useContainersTab({ containers }) {
  const containersStore = useContainersStore();
  const uiStore = useUiStore();
  const actionPending = ref(false);
  const search = ref('');
  const sort = ref('default');
  const expandedProjects = ref({});

  const sortOptions = [
    { value: 'default', label: '默认排序' },
    { value: 'status', label: '状态优先' },
    { value: 'nameAsc', label: '名称（A 到 Z）' },
    { value: 'nameDesc', label: '名称（Z 到 A）' },
  ];

  const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
  const { flash, isFlashing } = useFlashEffect();
  const { errorText, setError, clearError, matchesKey } = useInlineError();

  const detailModal = ref({ open: false, title: '', data: null, loading: false, mode: '' });

  function getStatusClass(status) {
    const s = String(status || '').toLowerCase();
    if (s === 'running') return 'status-running';
    if (s === 'exited') return 'status-exited';
    return 'status-created';
  }

  const filteredContainers = computed(() => {
    let list = [...(containers.value || [])];
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
    return (containers.value || []).filter((item) => !!item.compose_project_id).length;
  });

  const composeProjectCount = computed(() => {
    const projectIds = new Set(
      (containers.value || [])
        .map((item) => item.compose_project_id)
        .filter((projectId) => !!projectId)
    );
    return projectIds.size;
  });

  const standaloneContainerCount = computed(() => {
    return (containers.value || []).filter((item) => !item.compose_project_id).length;
  });

  function formatContainerId(id) {
    const value = String(id || '').trim();
    if (!value) return '-';
    if (value.length <= 28) return value;
    return `${value.slice(0, 12)}...${value.slice(-12)}`;
  }

  async function refreshAll() {
    await containersStore.loadContainers();
  }

  async function viewContainer(containerId) {
    try {
      clearError();
      detailModal.value = { open: true, title: '容器详情', data: null, loading: true, mode: 'container' };
      const data = await loadContainerDetail(containerId);
      detailModal.value.data = data;
      detailModal.value.loading = false;
      flash('container', containerId);
    } catch (error) {
      detailModal.value.loading = false;
      detailModal.value.open = false;
      setError(`container:${containerId}`, error.message || '加载容器详情失败');
            uiStore.showMessage(error.message || '加载容器详情失败', 'error');
    }
  }

  async function viewProject(projectId) {
    try {
      clearError();
      detailModal.value = { open: true, title: 'Compose 项目详情', data: null, loading: true, mode: 'project' };
      const data = await loadComposeProjectDetail(projectId);
      detailModal.value.data = data;
      detailModal.value.loading = false;
      flash('project', projectId);
    } catch (error) {
      detailModal.value.loading = false;
      detailModal.value.open = false;
      setError(`project:${projectId}`, error.message || '加载 Compose 项目详情失败');
            uiStore.showMessage(error.message || '加载 Compose 项目详情失败', 'error');
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
              uiStore.showMessage(successMsg, 'success');
      } catch (error) {
        setError(`${type}:${id}`, error.message || failMsg);
              uiStore.showMessage(error.message || failMsg, 'error');
      } finally {
        actionPending.value = false;
      }
    }, danger);
  }

  function restartManagedContainer(id) {
    containerAction({
      title: '重启容器',
      message: '确定要重启这个容器吗？',
      id,
      type: 'container',
      apiFn: restartContainer,
      successMsg: '容器重启成功',
      failMsg: '容器重启失败',
    });
  }

  function renewManagedContainer(id) {
    containerAction({
      title: '续期容器',
      message: '确定要续期这个容器吗？',
      id,
      type: 'container',
      apiFn: renewContainer,
      successMsg: '容器续期成功',
      failMsg: '容器续期失败',
    });
  }

  async function monitorContainerDeletion(id) {
    try {
      await waitContainerDestroyStatus(id);
      await refreshAll();
            uiStore.showMessage('容器删除成功', 'success');
    } catch (error) {
      setError(`container:${id}`, error.message || '容器删除失败');
            uiStore.showMessage(error.message || '容器删除失败', 'error');
      await refreshAll();
    }
  }

  function removeManagedContainer(id) {
    requestConfirm('删除容器', '确定要删除这个容器吗？此操作不可恢复。', async () => {
      try {
        clearError();
        actionPending.value = true;
        await deleteContainer(id);
              uiStore.showMessage('删除任务已提交，正在后台执行...', 'info');
        void monitorContainerDeletion(id);
      } catch (error) {
        setError(`container:${id}`, error.message || '容器删除失败');
              uiStore.showMessage(error.message || '容器删除失败', 'error');
        await refreshAll();
      } finally {
        actionPending.value = false;
      }
    }, true);
  }

  function restartProject(id) {
    containerAction({
      title: '重启 Compose 项目',
      message: '确定要重启整个 Compose 项目吗？',
      id,
      type: 'project',
      apiFn: restartComposeProject,
      successMsg: 'Compose 项目重启成功',
      failMsg: 'Compose 项目重启失败',
    });
  }

  function renewProject(id) {
    containerAction({
      title: '续期 Compose 项目',
      message: '确定要续期整个 Compose 项目吗？',
      id,
      type: 'project',
      apiFn: renewComposeProject,
      successMsg: 'Compose 项目续期成功',
      failMsg: 'Compose 项目续期失败',
    });
  }

  async function monitorProjectDeletion(id, result) {
    try {
      await waitComposeProjectDestroyStatus(result);
      await refreshAll();
            uiStore.showMessage('Compose 项目删除成功', 'success');
    } catch (error) {
      setError(`project:${id}`, error.message || 'Compose 项目删除失败');
            uiStore.showMessage(error.message || 'Compose 项目删除失败', 'error');
      await refreshAll();
    }
  }

  function removeProject(id) {
    requestConfirm('删除 Compose 项目', '确定要删除整个 Compose 项目吗？此操作不可恢复。', async () => {
      try {
        clearError();
        actionPending.value = true;
        const result = await deleteComposeProject(id);
              uiStore.showMessage('Compose 删除任务已提交，正在后台执行...', 'info');
        void monitorProjectDeletion(id, result);
      } catch (error) {
        setError(`project:${id}`, error.message || 'Compose 项目删除失败');
              uiStore.showMessage(error.message || 'Compose 项目删除失败', 'error');
        await refreshAll();
      } finally {
        actionPending.value = false;
      }
    }, true);
  }

  return {
    actionPending,
    search,
    sort,
    sortOptions,
    confirmModal,
    onConfirm,
    onCancelConfirm,
    isFlashing,
    errorText,
    matchesKey,
    detailModal,
    getStatusClass,
    visibleContainers,
    hasSearchKeyword,
    composeContainerCount,
    composeProjectCount,
    standaloneContainerCount,
    formatContainerId,
    isProjectLeader,
    isProjectExpanded,
    toggleProject,
    hiddenProjectContainerCount,
    viewContainer,
    viewProject,
    closeDetail,
    restartManagedContainer,
    renewManagedContainer,
    removeManagedContainer,
    restartProject,
    renewProject,
    removeProject,
  };
}
