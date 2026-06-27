<script setup>
import BaseModal from '../BaseModal.vue';
import ConfirmModal from '../ConfirmModal.vue';
import ManagedImageDetailModal from '../images/ManagedImageDetailModal.vue';
import ImagePullProgressModal from '../images/ImagePullProgressModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import StatCard from '../ui/StatCard.vue';
import { useImagesTab } from '../../composables/useImagesTab';

const {
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
} = useImagesTab();
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
        <StatCard title="受管镜像" :value="imagesState.stats.total" />
        <StatCard title="使用中" :value="imagesState.stats.inUse" />
        <StatCard title="未使用" :value="imagesState.stats.unused" />
        <StatCard title="悬空镜像" :value="imagesState.stats.dangling" />
        <StatCard title="总占用" :value="imagesState.stats.totalSizeText" />
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