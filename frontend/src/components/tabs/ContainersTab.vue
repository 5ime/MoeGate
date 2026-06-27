<script setup>
import { inject, toRef } from 'vue';
import ConfirmModal from '../ConfirmModal.vue';
import ObjectDetailModal from '../ObjectDetailModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import StatCard from '../ui/StatCard.vue';
import { useContainersTab } from '../../composables/useContainersTab';

const switchTab = inject('switchTab', null);

const props = defineProps({
  containers: { type: Array, required: true },
  total: { type: Number, required: true },
  running: { type: Number, required: true },
});

const {
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
} = useContainersTab({ containers: toRef(props, 'containers') });
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">容器总览</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">运行概况</h2>
        </div>
        <button
          id="gotoSystemBtn"
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
          @click="switchTab?.('system')"
        >
          查看系统监控
        </button>
      </div>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard title="总容器数" :value="total" value-id="totalContainers" />
        <StatCard title="运行中" :value="running" value-id="runningContainers" />
        <StatCard title="独立容器数" :value="standaloneContainerCount" />
        <StatCard
          title="Docker Compose"
          :value="composeContainerCount"
          suffix="容器"
          :secondary-value="composeProjectCount"
          secondary-suffix="项目"
        />
      </div>
    </div>

    <SearchSelectBar
      v-model:search="search"
      v-model:select="sort"
      search-id="containerSearch"
      select-id="containerSort"
      search-placeholder="搜索名称/ID/项目..."
      :options="sortOptions"
    />

    <div
      id="containersList"
      class="columns-1 md:columns-2 xl:columns-2 gap-5 [column-gap:1.25rem]"
      v-if="visibleContainers.length"
    >
      <div
        class="mb-5 break-inside-avoid rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition "
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
              详情
            </button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="restartManagedContainer(item.id)" title="重启容器">
              重启
            </button>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="renewManagedContainer(item.id)" title="续期容器">
              续期
            </button>
            <span class="flex-1"></span>
            <button class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-[#922f2f] bg-[#922f2f] px-3 text-xs font-medium text-white transition hover:border-[#7b2929] hover:bg-[#7b2929] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="actionPending" @click="removeManagedContainer(item.id)" title="删除容器">
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

    <div v-else class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-700">暂无容器</div>

    <ObjectDetailModal
      :visible="detailModal.open"
      :title="detailModal.title"
      :loading="detailModal.loading"
      :data="detailModal.data"
      :mode="detailModal.mode"
      @close="closeDetail"
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
