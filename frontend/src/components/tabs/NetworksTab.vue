<script setup>
import ConfirmModal from '../ConfirmModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import ManagedNetworkFormModal from '../networks/ManagedNetworkFormModal.vue';
import ManagedNetworkDetailModal from '../networks/ManagedNetworkDetailModal.vue';
import StatCard from '../ui/StatCard.vue';
import { useNetworksTab } from '../../composables/useNetworksTab';

const {
  refreshing,
  saving,
  actionPending,
  detailLoading,
  networkingSettingsOpening,
  search,
  usageFilter,
  formModal,
  detailModal,
  form,
  filterOptions,
  confirmModal,
  onConfirm,
  onCancelConfirm,
  isFlashing,
  errorText,
  matchesKey,
  networks,
  networksState,
  validateLabelFormat,
  openCreateModal,
  openEditModal,
  closeFormModal,
  closeDetailModal,
  refresh,
  openNetworkingSettings,
  submitForm,
  openDetail,
  confirmDelete,
  shortId,
  formatLabelCount,
  boolLabel,
  emptyStateText,
} = useNetworksTab();
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">网络空间</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">受管网络</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="networkingSettingsOpening || refreshing || saving || actionPending"
            @click="openNetworkingSettings"
          >偏好设置</button>
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="refreshing || saving || actionPending"
            @click="refresh"
          >{{ refreshing ? '刷新中...' : '刷新列表' }}</button>
          <button
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="saving || actionPending"
            @click="openCreateModal"
          >创建网络</button>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard title="总网络数" :value="networksState.stats.total" />
        <StatCard title="占用中" :value="networksState.stats.inUse" />
        <StatCard title="空闲网络" :value="networksState.stats.idle" />
        <StatCard title="已绑归属" :value="networksState.stats.composeBound" />
      </div>
    </div>

    <SearchSelectBar
      v-model:search="search"
      v-model:select="usageFilter"
      search-id="networkSearch"
      select-id="networkFilter"
      search-placeholder="搜索名称/ID/子网/归属..."
      select-min-width-class="min-w-[140px]"
      :options="filterOptions"
    />

    <div v-if="networks.length" class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <article
        v-for="item in networks"
        :key="item.id || item.name"
        class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition"
        :class="isFlashing('network', item.id || item.name) ? 'border-slate-400 bg-slate-50/80 shadow-[0_12px_24px_-18px_rgba(15,23,42,0.45)]' : ''"
      >
        <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
          <div class="min-w-0 flex-1">
            <h3 class="break-words text-lg font-semibold tracking-tight text-slate-900">{{ item.name }}</h3>
            <p class="mt-1 font-mono text-xs tracking-wide text-slate-400" :title="item.id || '-'">ID: {{ shortId(item.id) }}</p>
          </div>
          <span
            class="inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider"
            :class="item.is_in_use ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'"
          >{{ item.is_in_use ? '占用中' : '空闲' }}</span>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">驱动</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.driver || '-' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">子网</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.subnet || '-' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">网关</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.gateway || '-' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">归属 ID</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.compose_project_id || '-' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span class="text-[12px] text-slate-500">挂载容器</span>
            <span class="max-w-[65%] break-words text-right text-[12px] font-semibold text-slate-800">{{ item.attached_container_count ?? 0 }}</span>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap gap-2">
            <span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">内部网络: {{ boolLabel(item.internal) }}</span>
            <span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">可附加: {{ boolLabel(item.attachable) }}</span>
            <span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">IPv6: {{ boolLabel(item.enable_ipv6) }}</span>
            <span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">标签: {{ formatLabelCount(item.labels) }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px]"
              @click="openDetail(item)"
            >详情</button>
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="item.is_in_use"
              @click="openEditModal(item)"
            >编辑</button>
            <button
              class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="item.is_in_use || actionPending"
              @click="confirmDelete(item)"
            >删除</button>
          </div>
        </div>
        <p v-if="matchesKey(`network:${item.id || item.name}`)" class="mt-3 text-xs leading-5 text-rose-600">{{ errorText }}</p>
      </article>
    </div>

    <div v-else class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-700">
      {{ emptyStateText() }}
    </div>

    <ManagedNetworkFormModal
      :visible="formModal.open"
      :title="formModal.mode === 'edit' ? '编辑受管网络' : '创建受管网络'"
      :subtitle="formModal.mode === 'edit' ? `更新目标: ${formModal.originalName}` : '创建后会自动附加 moegate.managed=true 标签'"
      :saving="saving"
      :error-text="matchesKey('form') ? errorText : ''"
      v-model:name="form.name"
      v-model:driver="form.driver"
      v-model:subnet="form.subnet"
      v-model:gateway="form.gateway"
      v-model:compose-project-id="form.composeProjectId"
      v-model:internal="form.internal"
      v-model:attachable="form.attachable"
      v-model:enable-ipv6="form.enableIpv6"
      v-model:labels-text="form.labelsText"
      @validate-labels="validateLabelFormat"
      @close="closeFormModal"
      @save="submitForm"
    />

    <ManagedNetworkDetailModal
      :visible="detailModal.open"
      :title="detailModal.title"
      :loading="detailLoading"
      :data="detailModal.data"
      @close="closeDetailModal"
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