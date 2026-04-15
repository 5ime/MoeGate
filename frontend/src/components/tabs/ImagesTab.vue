<script setup>
import { computed, inject, ref } from 'vue';
import BaseModal from '../BaseModal.vue';
import ConfirmModal from '../ConfirmModal.vue';
import ManagedImageDetailModal from '../images/ManagedImageDetailModal.vue';
import ImagePullProgressModal from '../images/ImagePullProgressModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import StatCard from '../ui/StatCard.vue';
import { useConfirmAction, useFlashEffect, useInlineError } from '../../composables';
import {
  deleteManagedImage,
  loadImageDetail,
  loadImages,
  pruneManagedImages,
  showMessage,
  store,
} from '../../stores/appStore';

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
  return [...(store.images.items || [])]
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

function imageSubtitle(item) {
  const tags = item?.tags || [];
  if (tags.length <= 1) return tags[0] || '无标签';
  return `${tags[0]} 等 ${tags.length} 个标签`;
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
    showMessage('镜像源设置入口不可用', 'error');
    return;
  }

  imageSourceSettingsOpening.value = true;
  try {
    await openImageSourcePreferences();
  } catch (error) {
    showMessage(error.message || '打开镜像源设置失败', 'error');
  } finally {
    imageSourceSettingsOpening.value = false;
  }
}

async function refresh() {
  try {
    refreshing.value = true;
    await loadImages();
  } catch (error) {
    showMessage(error.message || '受管镜像列表加载失败', 'error');
  } finally {
    refreshing.value = false;
  }
}

async function submitPull() {
  const image = String(pullModal.value.image || '').trim();
  if (!image) {
    setError('pull', '请填写镜像名称');
    showMessage('请填写镜像名称', 'error');
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
  showMessage('受管镜像拉取成功', 'success');
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
    showMessage(error.message || '加载受管镜像详情失败', 'error');
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
        showMessage(result?.msg || (forceDelete ? '受管镜像强制删除成功' : '受管镜像删除成功'), 'success');
      } catch (error) {
        setError(`image:${ref}`, error.message || '受管镜像删除失败');
        showMessage(error.message || '受管镜像删除失败', 'error');
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
        showMessage(result?.msg || '受管悬空镜像清理成功', 'success');
      } catch (error) {
        setError('prune', error.message || '清理受管悬空镜像失败');
        showMessage(error.message || '清理受管悬空镜像失败', 'error');
      } finally {
        actionPending.value = false;
      }
    },
    true,
  );
}

function emptyStateText() {
  if (!store.images.stats.total) return '暂无受管镜像，可通过右上角手动拉取。';
  return '当前筛选条件下没有匹配的受管镜像。';
}
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">镜像空间</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">受管镜像</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="imageSourceSettingsOpening || actionPending || pulling"
            @click="openImageSourceSettings"
          >偏好设置</button>
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="refreshing || actionPending || pulling"
            @click="refresh"
          >{{ refreshing ? '刷新中...' : '刷新列表' }}</button>
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="actionPending || pulling"
            @click="confirmPrune"
          >清理悬空</button>
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="actionPending || pulling"
            @click="openPullModal()"
          >拉取镜像</button>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatCard title="受管镜像" :value="store.images.stats.total" />
        <StatCard title="使用中" :value="store.images.stats.inUse" />
        <StatCard title="未使用" :value="store.images.stats.unused" />
        <StatCard title="悬空镜像" :value="store.images.stats.dangling" />
        <StatCard title="总占用" :value="store.images.stats.totalSizeText" />
      </div>
    </div>

    <SearchSelectBar
      v-model:search="search"
      v-model:select="filter"
      search-id="imageSearch"
      select-id="imageFilter"
      search-placeholder="搜索受管标签、ID、Digest、容器引用..."
      select-min-width-class="min-w-[140px]"
      :options="filterOptions"
    />

    <div
      id="imagesList"
      v-if="images.length"
      class="columns-1 md:columns-2 xl:columns-2 gap-5 [column-gap:1.25rem]"
    >
      <article
        v-for="item in images"
        :key="item.id || item.primary_tag"
        class="mb-5 break-inside-avoid rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition"
        :class="isFlashing('image', item.id || item.primary_tag) ? 'border-slate-400 bg-slate-50/80 shadow-[0_12px_24px_-18px_rgba(15,23,42,0.45)]' : ''"
      >
        <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
          <div class="min-w-0 flex-1">
            <h3 class="break-words text-lg font-semibold tracking-tight text-slate-900">{{ imageTitle(item) }}</h3>
            <p class="mt-1 font-mono text-xs tracking-wide text-slate-400" :title="item.id || '-'">ID: {{ formatImageId(item.id) }}</p>
          </div>
          <span
            class="inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider"
            :class="item.is_dangling ? 'border-rose-200 bg-rose-50 text-rose-700' : Number(item.containers_using || 0) > 0 ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-700'"
          >{{ item.is_dangling ? '悬空' : Number(item.containers_using || 0) > 0 ? '使用中' : '未使用' }}</span>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">体积</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.size_text || '-' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">创建时间</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ formatCreatedAt(item.created_at) }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">引用容器</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.containers_using ?? 0 }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">Digest</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.repo_digests?.length ? item.repo_digests[0] : '-' }}</span>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-2" v-if="item.tags?.length">
          <span
            v-for="tag in item.tags.slice(0, 4)"
            :key="tag"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600"
          >{{ tag }}</span>
          <span v-if="item.tags.length > 4" class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-500">+{{ item.tags.length - 4 }}</span>
        </div>

        <div class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <div class="text-xs text-rose-600" v-if="matchesKey(`image:${item.id || item.primary_tag}`)">{{ errorText }}</div>
          <div class="text-xs text-rose-600" v-else-if="matchesKey('prune')">{{ errorText }}</div>
          <div class="ml-auto flex flex-wrap items-center gap-2">
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="actionPending || pulling"
              @click="openDetail(item)"
            >详情</button>
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="actionPending || pulling"
              @click="openPullModal(item.tags?.[0] || '')"
            >重新拉取</button>
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="actionPending || Number(item.containers_using || 0) > 0"
              :title="Number(item.containers_using || 0) > 0 ? '镜像仍被容器引用，无法直接删除' : ''"
              @click="confirmDelete(item)"
            >删除</button>
          </div>
        </div>
        <p v-if="matchesKey(`image:${item.id || item.primary_tag}`) || matchesKey('prune')" class="mt-3 text-xs leading-5 text-rose-600">{{ errorText }}</p>
      </article>
    </div>

    <div v-else class="rounded-xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500">
      {{ emptyStateText() }}
    </div>

    <BaseModal
      :visible="pullModal.open"
      title="拉取受管镜像"
      subtitle="手动拉取后会登记为受管镜像；若已配置全局镜像源，会自动拼接镜像前缀。"
      icon="bolt"
      width="max-w-[640px]"
      close-text="取消"
      @close="closePullModal"
    >
      <div class="space-y-4">
        <label class="block text-sm font-medium text-slate-900" for="pullImageInput">镜像名称</label>
        <input
          id="pullImageInput"
          v-model="pullModal.image"
          type="text"
          placeholder="例如 nginx:latest"
          class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-4 focus:ring-slate-100"
          :disabled="pulling"
          @keydown.enter.prevent="submitPull"
        >
        <p class="text-xs leading-5 text-slate-500">手动拉取会登记为受管镜像；容器创建时的自动拉取和构建镜像也会自动纳入受管范围。</p>
        <p v-if="matchesKey('pull')" class="text-xs text-rose-600">{{ errorText }}</p>
      </div>
      <template #footer>
        <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] disabled:cursor-not-allowed disabled:opacity-55" :disabled="pulling" @click="closePullModal">取消</button>
        <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-55" :disabled="pulling" @click="submitPull">{{ pulling ? '拉取中...' : '开始拉取' }}</button>
      </template>
    </BaseModal>

    <ManagedImageDetailModal
      :visible="detailModal.open"
      :title="detailModal.title"
      :loading="detailModal.loading"
      :data="detailModal.data"
      @close="closeDetailModal"
    />

    <ImagePullProgressModal
      :visible="pullProgressModal.open"
      :payload="pullProgressModal.payload"
      @close="onPullProgressClose"
      @success="onPullSuccess"
    />

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