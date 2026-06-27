import { computed, inject, ref } from 'vue';
import { storeToRefs } from 'pinia';
import {
  deleteManagedImage,
  loadImageDetail,
  pruneManagedImages,
  useImagesStore,
} from '../stores/imagesStore';
import { useUiStore } from '../stores/uiStore';
import { useConfirmAction, useFlashEffect, useInlineError } from './index';

export function useImagesTab() {
  const imagesStore = useImagesStore();
  const uiStore = useUiStore();
  const { images: imagesState } = storeToRefs(imagesStore);

  const refreshing = ref(false);
  const actionPending = ref(false);
  const pulling = ref(false);
  const imageSourceSettingsOpening = ref(false);
  const detailModal = ref({ open: false, title: '', data: null, loading: false });
  const pullModal = ref({ open: false, image: '' });
  const pullProgressModal = ref({ open: false, payload: null });
  const search = ref('');
  const filter = ref('all');

  const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
  const { flash, isFlashing } = useFlashEffect();
  const { errorText, setError, clearError, matchesKey } = useInlineError();
  const openImageSourcePreferences = inject('openImageSourcePreferences', null);

  const filterOptions = [
    { value: 'all', label: '全部受管镜像' },
    { value: 'in-use', label: '使用中' },
    { value: 'unused', label: '未使用' },
    { value: 'dangling', label: '悬空镜像' },
  ];

  const images = computed(() => {
    const keyword = String(search.value || '').trim().toLowerCase();
    return [...(imagesState.value.items || [])]
      .filter((item) => {
        const usingCount = Number(item?.containers_using || 0);
        if (filter.value === 'in-use' && usingCount <= 0) return false;
        if (filter.value === 'unused' && usingCount > 0) return false;
        if (filter.value === 'dangling' && !item?.is_dangling) return false;

        if (!keyword) return true;

        const text = [
          item?.primary_tag,
          item?.id,
          item?.short_id,
          ...(item?.tags || []),
          ...(item?.repo_digests || []),
          ...(item?.container_refs || []).map((ref) => `${ref.name} ${ref.id} ${ref.status}`),
        ].join(' ').toLowerCase();

        return text.includes(keyword);
      })
      .sort((left, right) => {
        const usageDiff = Number(right?.containers_using || 0) - Number(left?.containers_using || 0);
        if (usageDiff) return usageDiff;
        const sizeDiff = Number(right?.size_bytes || 0) - Number(left?.size_bytes || 0);
        if (sizeDiff) return sizeDiff;
        return String(right?.created_at || '').localeCompare(String(left?.created_at || ''));
      });
  });

  function formatImageId(imageId) {
    const text = String(imageId || '').trim();
    if (!text) return '-';
    if (text.length <= 26) return text;
    return `${text.slice(0, 18)}...${text.slice(-6)}`;
  }

  function formatCreatedAt(value) {
    const text = String(value || '').trim();
    if (!text) return '-';
    const normalized = text.replace('T', ' ').replace('Z', '');
    return normalized.split('.')[0] || '-';
  }

  function imageTitle(item) {
    return item?.primary_tag && item.primary_tag !== '<dangling>' ? item.primary_tag : item?.short_id || item?.id || '未命名镜像';
  }

  function shouldForceDelete(item) {
    return Number((item?.tags || []).length) > 1;
  }

  function openPullModal(defaultImage = '') {
    clearError();
    pullModal.value = { open: true, image: String(defaultImage || '').trim() };
  }

  function closePullModal() {
    pullModal.value = { open: false, image: '' };
  }

  function closeDetailModal() {
    detailModal.value = { open: false, title: '', data: null, loading: false };
  }

  async function openImageSourceSettings() {
    if (imageSourceSettingsOpening.value) return;
    if (typeof openImageSourcePreferences !== 'function') {
      uiStore.showMessage('镜像源设置入口不可用', 'error');
      return;
    }

    imageSourceSettingsOpening.value = true;
    try {
      await openImageSourcePreferences();
    } catch (error) {
      uiStore.showMessage(error.message || '打开镜像源设置失败', 'error');
    } finally {
      imageSourceSettingsOpening.value = false;
    }
  }

  async function refresh() {
    try {
      refreshing.value = true;
      await imagesStore.loadImages();
    } catch (error) {
      uiStore.showMessage(error.message || '受管镜像列表加载失败', 'error');
    } finally {
      refreshing.value = false;
    }
  }

  async function submitPull() {
    const image = String(pullModal.value.image || '').trim();
    if (!image) {
      setError('pull', '请填写镜像名称');
      uiStore.showMessage('请填写镜像名称', 'error');
      return;
    }

    clearError();
    pulling.value = true;
    pullProgressModal.value = { open: true, payload: { image } };
    closePullModal();
  }

  async function onPullSuccess(result) {
    await refresh();
    const imageId = result?.id || result?.resolved_image || pullProgressModal.value?.payload?.image;
    flash('image', imageId);
    uiStore.showMessage('受管镜像拉取成功', 'success');
  }

  function onPullProgressClose() {
    pullProgressModal.value = { open: false, payload: null };
    pulling.value = false;
  }

  async function openDetail(item) {
    const imageRef = item?.id;
    try {
      clearError();
      detailModal.value = { open: true, title: '受管镜像详情', data: null, loading: true };
      const data = await loadImageDetail(imageRef);
      detailModal.value.data = data;
      detailModal.value.loading = false;
      flash('image', imageRef);
    } catch (error) {
      closeDetailModal();
      setError(`image:${imageRef}`, error.message || '加载受管镜像详情失败');
      uiStore.showMessage(error.message || '加载受管镜像详情失败', 'error');
    }
  }

  function confirmDelete(item) {
    const ref = item?.id || item?.primary_tag;
    const forceDelete = shouldForceDelete(item);
    const tagCount = Number((item?.tags || []).length || 0);
    requestConfirm(
      forceDelete ? '强制删除受管镜像' : '删除受管镜像',
      forceDelete
        ? `镜像 ${imageTitle(item)} 当前关联 ${tagCount} 个标签，Docker 需要强制删除才能一次性移除全部仓库引用。确认继续后会强制删除该受管镜像及其全部标签。`
        : `确定要删除受管镜像 ${imageTitle(item)} 吗？该操作不可撤销。`,
      async () => {
        try {
          clearError();
          actionPending.value = true;
          const result = await deleteManagedImage(ref, forceDelete);
          await refresh();
          uiStore.showMessage(result?.msg || (forceDelete ? '受管镜像强制删除成功' : '受管镜像删除成功'), 'success');
        } catch (error) {
          setError(`image:${ref}`, error.message || '受管镜像删除失败');
          uiStore.showMessage(error.message || '受管镜像删除失败', 'error');
        } finally {
          actionPending.value = false;
        }
      },
      true,
    );
  }

  function confirmPrune() {
    requestConfirm(
      '清理受管悬空镜像',
      '确定要清理所有受管悬空镜像吗？这只会删除 MoeGate 管过且未被标签引用的镜像层。',
      async () => {
        try {
          clearError();
          actionPending.value = true;
          const result = await pruneManagedImages();
          await refresh();
          uiStore.showMessage(result?.msg || '受管悬空镜像清理成功', 'success');
        } catch (error) {
          setError('prune', error.message || '清理受管悬空镜像失败');
          uiStore.showMessage(error.message || '清理受管悬空镜像失败', 'error');
        } finally {
          actionPending.value = false;
        }
      },
      true,
    );
  }

  function emptyStateText() {
    if (!imagesState.value.stats.total) return '暂无受管镜像，可通过右上角手动拉取。';
    return '当前筛选条件下没有匹配的受管镜像。';
  }

  return {
    refreshing,
    actionPending,
    pulling,
    imageSourceSettingsOpening,
    detailModal,
    pullModal,
    pullProgressModal,
    search,
    filter,
    filterOptions,
    confirmModal,
    onConfirm,
    onCancelConfirm,
    isFlashing,
    errorText,
    matchesKey,
    images,
    imagesState,
    formatImageId,
    formatCreatedAt,
    imageTitle,
    openPullModal,
    closePullModal,
    closeDetailModal,
    openImageSourceSettings,
    refresh,
    submitPull,
    onPullSuccess,
    onPullProgressClose,
    openDetail,
    confirmDelete,
    confirmPrune,
    emptyStateText,
  };
}
