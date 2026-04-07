<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import BaseModal from '../BaseModal.vue';
import ConfirmModal from '../ConfirmModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import FrpProxyCard from '../frp/FrpProxyCard.vue';
import FrpCreateProxyModal from '../frp/FrpCreateProxyModal.vue';
import FrpEditProxyModal from '../frp/FrpEditProxyModal.vue';
import FrpPreferencesModal from '../frp/FrpPreferencesModal.vue';
import StatCard from '../ui/StatCard.vue';
import { useConfirmAction, useFlashEffect, useInlineError } from '../../composables';
import {
  createFrpProxy,
  deleteFrpProxy,
  loadFrpConfig,
  loadFrpPanel,
  loadFrpProxy,
  loadFrpSettings,
  reloadFrpConfig,
  saveFrpPreferences,
  saveFrpSettings,
  showMessage,
  store,
  updateFrpProxy,
} from '../../stores/appStore';

const form = reactive({
  name: '',
  localPort: '',
  remotePort: '',
  type: 'tcp',
  domain: '',
});

const editingName = ref('');
const editForm = reactive({
  type: 'tcp',
  localPort: '',
  remotePort: '',
  domain: '',
});
const switchSaving = ref(false);
const refreshing = ref(false);
const proxyKeyword = ref('');
const createPending = ref(false);
const reloadPending = ref(false);
const configPending = ref(false);
const editPending = ref(false);
const deletingName = ref('');
const preferencesModal = ref(false);
const createModal = ref(false);
const preferencesLoading = ref(false);
const preferencesSaving = ref(false);
const createInlineError = ref('');
const editInlineError = ref('');
const preferencesForm = reactive({
  serverAddr: '',
  serverPort: '7000',
  vhostHttpPort: '',
  adminIp: '127.0.0.1',
  adminPort: '7400',
  adminUser: '',
  adminPassword: '',
  useDomain: false,
  domainSuffix: '',
});

const { confirmModal, requestConfirm, onConfirm, onCancelConfirm } = useConfirmAction();
const { flash, isFlashing } = useFlashEffect();
const { errorText: proxyErrorText, setError: setProxyError, matchesKey: matchesProxyKey } = useInlineError();

function resetCreateForm() {
  form.name = '';
  form.localPort = '';
  form.remotePort = '';
  form.type = 'tcp';
  form.domain = '';
  createInlineError.value = '';
}

// Config preview modal
const configModal = ref(false);

const healthState = computed(() => {
  const health = store.frp.health || {};
  if (health.overallOk) {
    return {
      label: '状态良好',
    };
  }
  if (health.serverReachable === false || health.adminReachable === false) {
    return {
      label: '异常',
    };
  }
  return {
    label: '待检查',
  };
});

const filteredProxies = computed(() => {
  const list = store.frp.proxies || [];
  const kw = proxyKeyword.value.trim().toLowerCase();
  if (!kw) return list;
  return list.filter((proxy) => {
    const name = String(proxy.name || '').toLowerCase();
    const type = String(proxy.type || proxy.proxy_type || '').toLowerCase();
    const domain = String(proxy.domain || '').toLowerCase();
    const localPort = String(proxy.localPort ?? proxy.local_port ?? '');
    const remotePort = String(proxy.remotePort ?? proxy.remote_port ?? '');
    return name.includes(kw) || type.includes(kw) || domain.includes(kw) || localPort.includes(kw) || remotePort.includes(kw);
  });
});

async function refresh() {
  try {
    refreshing.value = true;
    await loadFrpPanel();
  } catch (error) {
    showMessage(error.message || 'FRP 加载失败', 'error');
  } finally {
    refreshing.value = false;
  }
}

async function applySwitch(event) {
  switchSaving.value = true;
  try {
    await saveFrpSettings(!!event.target.checked);
    showMessage('FRP 开关已更新', 'success');
    await refresh();
  } catch (error) {
    showMessage(error.message || '开关更新失败', 'error');
  } finally {
    switchSaving.value = false;
  }
}

function syncPreferencesFormFromStore() {
  preferencesForm.serverAddr = String(store.frp.settings.serverAddr || '');
  preferencesForm.serverPort = String(store.frp.settings.serverPort || 7000);
  preferencesForm.vhostHttpPort = store.frp.settings.vhostHttpPort == null ? '' : String(store.frp.settings.vhostHttpPort);
  preferencesForm.adminIp = String(store.frp.settings.adminIp || '127.0.0.1');
  preferencesForm.adminPort = String(store.frp.settings.adminPort || 7400);
  preferencesForm.adminUser = String(store.frp.settings.adminUser || '');
  preferencesForm.adminPassword = String(store.frp.settings.adminPassword || '');
  preferencesForm.useDomain = !!store.frp.settings.useDomain;
  preferencesForm.domainSuffix = String(store.frp.settings.domainSuffix || '');
}

async function openPreferences() {
  preferencesLoading.value = true;
  try {
    await loadFrpSettings();
    syncPreferencesFormFromStore();
    preferencesModal.value = true;
  } catch (error) {
    showMessage(error.message || '加载 FRP 偏好设置失败', 'error');
  } finally {
    preferencesLoading.value = false;
  }
}

function closePreferences() {
  preferencesModal.value = false;
}

async function savePreferences() {
  preferencesSaving.value = true;
  try {
    await saveFrpPreferences(preferencesForm);
    showMessage('FRP 偏好设置已保存', 'success');
    preferencesModal.value = false;
    await refresh();
  } catch (error) {
    showMessage(error.message || '保存 FRP 偏好设置失败', 'error');
  } finally {
    preferencesSaving.value = false;
  }
}

async function submitProxy() {
  createPending.value = true;
  createInlineError.value = '';
  try {
    if (!form.name.trim() || !form.localPort) {
      showMessage('请填写名称和本地端口', 'error');
      return;
    }
    const payload = {
      name: form.name.trim(),
      localPort: Number(form.localPort),
    };
    if (form.remotePort) payload.remotePort = Number(form.remotePort);
    if (form.type.trim()) payload.type = form.type.trim();
    if (form.domain.trim()) payload.domain = form.domain.trim();

    await createFrpProxy(payload);
    flash('proxy', payload.name);
    showMessage('FRP 代理创建成功', 'success');
    resetCreateForm();
    createModal.value = false;
    await refresh();
  } catch (error) {
    createInlineError.value = error.message || '创建代理失败';
    showMessage(error.message || '创建代理失败', 'error');
  } finally {
    createPending.value = false;
  }
}

async function reloadConfig() {
  reloadPending.value = true;
  try {
    await reloadFrpConfig();
    showMessage('FRP 配置已重载', 'success');
    await refresh();
  } catch (error) {
    showMessage(error.message || '重载失败', 'error');
  } finally {
    reloadPending.value = false;
  }
}

async function viewConfig() {
  configPending.value = true;
  try {
    await loadFrpConfig();
    configModal.value = true;
    showMessage('已获取 FRP 配置', 'success');
  } catch (error) {
    showMessage(error.message || '获取配置失败', 'error');
  } finally {
    configPending.value = false;
  }
}

async function openEdit(proxyName) {
  editInlineError.value = '';
  try {
    const proxy = await loadFrpProxy(proxyName);
    if (!proxy) {
      showMessage('未找到 FRP 代理详情', 'error');
      return;
    }
    editingName.value = proxy.name || proxyName;
    editForm.type = proxy.type || proxy.proxy_type || 'tcp';
    editForm.localPort = String(proxy.localPort ?? proxy.local_port ?? '');
    editForm.remotePort = String(proxy.remotePort ?? proxy.remote_port ?? '');
    const firstCustomDomain = Array.isArray(proxy.customDomains) ? proxy.customDomains[0] : '';
    editForm.domain = proxy.domain || firstCustomDomain || '';
  } catch (error) {
    showMessage(error.message || '加载代理详情失败', 'error');
  }
}

function cancelEdit() {
  editingName.value = '';
  editForm.type = 'tcp';
  editForm.localPort = '';
  editForm.remotePort = '';
  editForm.domain = '';
}

async function saveEdit() {
  if (!editingName.value) return;
  editPending.value = true;
  editInlineError.value = '';
  try {
    const payload = {};
    if (editForm.type.trim()) payload.type = editForm.type.trim();
    if (editForm.localPort) payload.localPort = Number(editForm.localPort);
    if (editForm.remotePort) payload.remotePort = Number(editForm.remotePort);
    const typeLower = String(editForm.type || '').trim().toLowerCase();
    if (typeLower === 'http' || typeLower === 'https') {
      if (editForm.domain.trim()) payload.customDomains = [editForm.domain.trim()];
    }

    await updateFrpProxy(editingName.value, payload);
    flash('proxy', editingName.value);
    showMessage('FRP 代理更新成功', 'success');
    cancelEdit();
    await refresh();
  } catch (error) {
    editInlineError.value = error.message || '更新代理失败';
    showMessage(error.message || '更新代理失败', 'error');
  } finally {
    editPending.value = false;
  }
}

async function removeProxy(proxyName) {
  requestConfirm('删除代理', `确定要删除代理 ${proxyName} 吗？`, async () => {
    deletingName.value = proxyName;
    try {
      await deleteFrpProxy(proxyName);
      if (editingName.value === proxyName) {
        cancelEdit();
      }
      showMessage('FRP 代理删除成功', 'success');
      await refresh();
    } catch (error) {
      setProxyError(`proxy:${proxyName}`, error.message || '删除代理失败');
      showMessage(error.message || '删除代理失败', 'error');
    } finally {
      deletingName.value = '';
    }
  }, true);
}

onMounted(() => {
  refresh();
});
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">FRP 工作台</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">代理与隧道管理</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button id="reloadFrpBtn" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="reloadPending || refreshing || !store.frp.enabled" @click="reloadConfig">{{ reloadPending ? '重载中...' : '重载配置' }}</button>
          <button id="viewFrpConfigBtn" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="configPending || refreshing" @click="viewConfig">{{ configPending ? '读取中...' : '查看配置' }}</button>
          <button id="openFrpPreferencesBtn" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="preferencesLoading || preferencesSaving || refreshing" @click="openPreferences">偏好设置</button>
          <button id="refreshSystemBtn" type="button" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="refreshing || switchSaving || createPending || reloadPending || configPending || editPending || !!deletingName" @click="refresh">
            {{ refreshing ? '刷新中...' : '刷新系统状态' }}
          </button>
        </div>
      </div>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-12">
        <div class="flex h-full flex-col rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition md:col-span-1 xl:col-span-4">
          <div class="flex items-center justify-between gap-2">
            <div class="text-xs font-medium uppercase tracking-wider text-slate-500">FRP 开关</div>
            <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">{{ switchSaving ? '保存中...' : '即时生效' }}</span>
          </div>
          <div class="mt-2 flex items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <label class="relative inline-block h-6 w-11">
                <input id="frpEnabledSwitch" class="peer h-0 w-0 opacity-0" type="checkbox" :checked="store.frp.enabled" :disabled="switchSaving" @change="applySwitch" />
                <span class="absolute inset-0 cursor-pointer rounded-full bg-slate-300 transition peer-checked:bg-slate-900"></span>
                <span class="absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.18)] transition peer-checked:translate-x-5"></span>
              </label>
              <span id="frpEnabledText" class="text-sm font-semibold" :class="store.frp.enabled ? 'text-emerald-700' : 'text-slate-600'">{{ store.frp.enabled ? '已启用' : '已关闭' }}</span>
            </div>
          </div>
          <p class="mt-auto pt-2 text-xs leading-5 text-slate-500">开启后可使用域名方式代理访问服务</p>
        </div>

        <div class="flex h-full flex-col rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition md:col-span-1 xl:col-span-4">
          <div id="frpHealthText">
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs font-medium uppercase tracking-wider text-slate-500">健康状态</div>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">实时</span>
            </div>
            <div class="mt-2 flex flex-wrap items-center gap-2.5">
              <span class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50/70 px-2.5 py-1 text-[12px] text-slate-600">
                <i class="inline-block h-2 w-2 rounded-full animate-[healthPulse_1.6s_ease-in-out_infinite]" :class="store.frp.health.serverReachable ? 'bg-emerald-700' : 'bg-[#922f2f]'"></i>
                服务端 {{ store.frp.health.serverReachable ? '可达' : '不可达' }}
              </span>
              <span class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50/70 px-2.5 py-1 text-[12px] text-slate-600">
                <i class="inline-block h-2 w-2 rounded-full animate-[healthPulse_1.6s_ease-in-out_infinite]" :class="store.frp.health.adminReachable ? 'bg-emerald-700' : 'bg-[#922f2f]'"></i>
                管理端 {{ store.frp.health.adminReachable ? '可达' : '不可达' }}
              </span>
            </div>
          </div>
          <p class="mt-auto pt-2 text-xs leading-5 text-slate-500">目前 FRP 状态 · {{ healthState.label }}</p>
        </div>

        <StatCard
          class="md:col-span-2 xl:col-span-4"
          title="代理数量"
          badge="当前"
          :value="store.frp.proxies.length"
          description="当前已配置的 FRP 代理总数"
          height-class="h-full"
        />
      </div>
    </div>

    <SearchSelectBar
      v-model:search="proxyKeyword"
      :show-select="false"
      search-id="frpSearch"
      search-placeholder="搜索名称/类型/端口..."
    >
      <template #tail>
            <button
              id="openCreateProxyBtn"
              type="button"
              class="inline-flex h-[38px] items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="createPending || !store.frp.enabled"
              @click="createModal = true"
            >
              新增代理
            </button>
      </template>
    </SearchSelectBar>
        <div id="frpList" class="grid grid-cols-1 gap-5 xl:grid-cols-2 flex-1 min-h-[220px]" v-if="filteredProxies.length">
      <FrpProxyCard
            v-for="proxy in filteredProxies"
            :key="proxy.name || proxy.local_port"
        :proxy="proxy"
        :flashing="isFlashing('proxy', proxy.name)"
        :can-edit="store.frp.enabled && !editPending"
        :can-delete="store.frp.enabled"
        :deleting="deletingName === proxy.name"
        :inline-error="proxyErrorText && matchesProxyKey(`proxy:${proxy.name}`) ? proxyErrorText : ''"
        @edit="openEdit"
        @delete="removeProxy"
      />
            </div>

    <div v-else class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-700">
      {{ proxyKeyword ? '未匹配到代理' : '暂无 FRP 代理' }}
    </div>

    <FrpCreateProxyModal
      :visible="createModal"
      :pending="createPending"
      :enabled="store.frp.enabled"
      :inline-error="createInlineError"
      v-model:name="form.name"
      v-model:localPort="form.localPort"
      v-model:remotePort="form.remotePort"
      v-model:type="form.type"
      v-model:domain="form.domain"
      @close="createModal = false"
      @submit="submitProxy"
    />

    <FrpPreferencesModal
      :visible="preferencesModal"
      :loading="preferencesLoading"
      :saving="preferencesSaving"
      v-model:server-addr="preferencesForm.serverAddr"
      v-model:server-port="preferencesForm.serverPort"
      v-model:vhost-http-port="preferencesForm.vhostHttpPort"
      v-model:admin-ip="preferencesForm.adminIp"
      v-model:admin-port="preferencesForm.adminPort"
      v-model:admin-user="preferencesForm.adminUser"
      v-model:admin-password="preferencesForm.adminPassword"
      v-model:use-domain="preferencesForm.useDomain"
      v-model:domain-suffix="preferencesForm.domainSuffix"
      @close="closePreferences"
      @save="savePreferences"
    />

    <FrpEditProxyModal
      :visible="!!editingName"
      :pending="editPending"
      :inline-error="editInlineError"
      v-model:type="editForm.type"
      v-model:localPort="editForm.localPort"
      v-model:remotePort="editForm.remotePort"
      v-model:domain="editForm.domain"
      @close="cancelEdit"
      @save="saveEdit"
    />

    <BaseModal
      :visible="configModal"
      title="FRP 配置预览"
      icon="bolt"
      width="max-w-[880px]"
      @close="configModal = false"
    >
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div>
            <p class="text-xs font-semibold tracking-tight text-slate-900">配置内容</p>
            <p class="mt-1 text-xs text-slate-500">只读预览，便于排查域名/端口配置问题。</p>
          </div>
          <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">只读</span>
        </div>
        <pre class="max-h-[64vh] overflow-y-auto rounded-[14px] border border-slate-200 bg-slate-50/60 p-3 font-mono text-xs leading-relaxed text-slate-900">{{ store.frp.configText || '暂无配置' }}</pre>
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
