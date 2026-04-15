<script setup>
import { computed, inject, ref } from 'vue';
import ConfirmModal from '../ConfirmModal.vue';
import KeyValueLinesEditor from '../KeyValueLinesEditor.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import ManagedNetworkFormModal from '../networks/ManagedNetworkFormModal.vue';
import ManagedNetworkDetailModal from '../networks/ManagedNetworkDetailModal.vue';
import StatCard from '../ui/StatCard.vue';
import { formatKeyValueLines, parseKeyValueLines, useConfirmAction, useFlashEffect, useInlineError } from '../../composables';
import {
  createManagedNetwork,
  deleteManagedNetwork,
  loadManagedNetworkDetail,
  loadManagedNetworks,
  showMessage,
  store,
  updateManagedNetwork,
} from '../../stores/appStore';

const refreshing = ref(false);
const saving = ref(false);
const actionPending = ref(false);
const detailLoading = ref(false);
const networkingSettingsOpening = ref(false);
const search = ref('');
const usageFilter = ref('all');
const formModal = ref({ open: false, mode: 'create', networkId: '', originalName: '' });
const detailModal = ref({ open: false, title: '', data: null });
const form = ref(createEmptyForm());
const openNetworkingPreferences = inject('openNetworkingPreferences', null);

const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
const { flash, isFlashing } = useFlashEffect();
const { errorText, setError, clearError, matchesKey } = useInlineError();

const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'in-use', label: '占用中' },
  { value: 'idle', label: '空闲' },
  { value: 'compose', label: '已绑归属' },
];

const networks = computed(() => {
  const keyword = String(search.value || '').trim().toLowerCase();
  return (store.networks.items || []).filter((item) => {
    if (usageFilter.value === 'in-use' && !item?.is_in_use) return false;
    if (usageFilter.value === 'idle' && item?.is_in_use) return false;
    if (usageFilter.value === 'compose' && !item?.compose_project_id) return false;

    if (!keyword) return true;

    const text = [
      item?.name,
      item?.id,
      item?.driver,
      item?.subnet,
      item?.gateway,
      item?.compose_project_id,
      Object.keys(item?.labels || {}).join(' '),
      Object.values(item?.labels || {}).join(' '),
    ].join(' ').toLowerCase();

    return text.includes(keyword);
  });
});

function createEmptyForm() {
  return {
    name: '',
    driver: 'bridge',
    subnet: '',
    gateway: '',
    composeProjectId: '',
    internal: false,
    attachable: false,
    enableIpv6: false,
    labelsText: '',
  };
}

function resetForm() {
  form.value = createEmptyForm();
}

function formatLabelLines(labels) {
  return formatKeyValueLines(labels);
}

function parseLabelLines(text) {
  return parseKeyValueLines(text, {
    allowColon: true,
    invalidLineMessage: (line) => `标签格式错误: ${line}`,
    emptyKeyMessage: (line) => `标签键不能为空: ${line}`,
  });
}

function validateLabelFormat() {
  const raw = String(form.value.labelsText || '').trim();
  if (!raw) {
    showMessage('标签为空，默认只保留系统标签', 'info');
    return;
  }

  try {
    const labels = parseLabelLines(raw);
    showMessage(`格式正确，共 ${Object.keys(labels).length} 项标签`, 'success');
  } catch (error) {
    showMessage(error.message || '标签格式错误，请检查填写内容', 'error');
  }
}

function buildPayload() {
  return {
    name: String(form.value.name || '').trim(),
    driver: String(form.value.driver || 'bridge').trim() || 'bridge',
    subnet: String(form.value.subnet || '').trim() || null,
    gateway: String(form.value.gateway || '').trim() || null,
    compose_project_id: String(form.value.composeProjectId || '').trim() || null,
    internal: !!form.value.internal,
    attachable: !!form.value.attachable,
    enable_ipv6: !!form.value.enableIpv6,
    labels: parseLabelLines(form.value.labelsText),
  };
}

function openCreateModal() {
  clearError();
  formModal.value = { open: true, mode: 'create', networkId: '', originalName: '' };
  resetForm();
}

function openEditModal(network) {
  clearError();
  formModal.value = {
    open: true,
    mode: 'edit',
    networkId: network.id || network.name,
    originalName: network.name || '',
  };
  form.value = {
    name: String(network.name || ''),
    driver: String(network.driver || 'bridge'),
    subnet: String(network.subnet || ''),
    gateway: String(network.gateway || ''),
    composeProjectId: String(network.compose_project_id || ''),
    internal: !!network.internal,
    attachable: !!network.attachable,
    enableIpv6: !!network.enable_ipv6,
    labelsText: formatLabelLines(network.labels),
  };
}

function closeFormModal() {
  formModal.value = { open: false, mode: 'create', networkId: '', originalName: '' };
  resetForm();
}

function closeDetailModal() {
  detailModal.value = { open: false, title: '', data: null };
}

async function refresh() {
  try {
    refreshing.value = true;
    await loadManagedNetworks();
  } catch (error) {
    showMessage(error.message || '受管网络列表加载失败', 'error');
  } finally {
    refreshing.value = false;
  }
}

async function openNetworkingSettings() {
  if (networkingSettingsOpening.value) return;
  if (typeof openNetworkingPreferences !== 'function') {
    showMessage('Compose 网络池入口不可用', 'error');
    return;
  }

  networkingSettingsOpening.value = true;
  try {
    await openNetworkingPreferences();
  } catch (error) {
    showMessage(error.message || '打开 Compose 网络池失败', 'error');
  } finally {
    networkingSettingsOpening.value = false;
  }
}

async function submitForm() {
  try {
    clearError();
    saving.value = true;
    const payload = buildPayload();
    let result;
    if (formModal.value.mode === 'edit') {
      result = await updateManagedNetwork(formModal.value.networkId, payload);
    } else {
      result = await createManagedNetwork(payload);
    }
    await refresh();
    flash('network', result?.data?.id || result?.data?.name || payload.name);
    showMessage(result?.msg || (formModal.value.mode === 'edit' ? '网络更新成功' : '网络创建成功'), 'success');
    closeFormModal();
  } catch (error) {
    setError('form', error.message || '网络保存失败');
    showMessage(error.message || '网络保存失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function openDetail(network) {
  try {
    clearError();
    detailLoading.value = true;
    detailModal.value = { open: true, title: `网络详情`, data: null };
    const data = await loadManagedNetworkDetail(network.id || network.name);
    detailModal.value.data = data;
    flash('network', network.id || network.name);
  } catch (error) {
    closeDetailModal();
    setError(`network:${network.id || network.name}`, error.message || '加载网络详情失败');
    showMessage(error.message || '加载网络详情失败', 'error');
  } finally {
    detailLoading.value = false;
  }
}

function confirmDelete(network) {
  requestConfirm(
    '删除受管网络',
    `确定要删除网络 ${network.name} 吗？该操作不可撤销。`,
    async () => {
      try {
        clearError();
        actionPending.value = true;
        const result = await deleteManagedNetwork(network.id || network.name);
        await refresh();
        showMessage(result?.msg || '网络删除成功', 'success');
      } catch (error) {
        setError(`network:${network.id || network.name}`, error.message || '网络删除失败');
        showMessage(error.message || '网络删除失败', 'error');
      } finally {
        actionPending.value = false;
      }
    },
    true,
  );
}

function shortId(value) {
  const text = String(value || '').trim();
  if (!text) return '-';
  if (text.length <= 24) return text;
  return `${text.slice(0, 12)}...${text.slice(-10)}`;
}

function formatLabelCount(labels) {
  return Object.keys(labels || {}).length;
}

function boolLabel(value) {
  return value ? '是' : '否';
}

function emptyStateText() {
  if (!store.networks.stats.total) return '暂无受管网络';
  return '当前筛选条件下没有匹配的受管网络。';
}
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
        <StatCard title="总网络数" :value="store.networks.stats.total" />
        <StatCard title="占用中" :value="store.networks.stats.inUse" />
        <StatCard title="空闲网络" :value="store.networks.stats.idle" />
        <StatCard title="已绑归属" :value="store.networks.stats.composeBound" />
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