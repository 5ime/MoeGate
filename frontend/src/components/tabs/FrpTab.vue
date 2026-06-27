<script setup>
import BaseModal from '../BaseModal.vue';
import ConfirmModal from '../ConfirmModal.vue';
import SearchSelectBar from '../SearchSelectBar.vue';
import FrpProxyCard from '../frp/FrpProxyCard.vue';
import FrpCreateProxyModal from '../frp/FrpCreateProxyModal.vue';
import FrpEditProxyModal from '../frp/FrpEditProxyModal.vue';
import FrpPreferencesModal from '../frp/FrpPreferencesModal.vue';
import StatCard from '../ui/StatCard.vue';
import { useFrpTab } from '../../composables/useFrpTab';

const {
  adminPasswordSet,
  applySwitch,
  cancelEdit,
  closePreferences,
  configModal,
  configPending,
  confirmModal,
  createInlineError,
  createModal,
  createPending,
  deletingName,
  editForm,
  editInlineError,
  editPending,
  editingName,
  filteredProxies,
  form,
  frp,
  healthState,
  isFlashing,
  matchesProxyKey,
  onCancelConfirm,
  onConfirm,
  openEdit,
  openPreferences,
  preferencesForm,
  preferencesLoading,
  preferencesModal,
  preferencesSaving,
  proxyErrorText,
  proxyKeyword,
  refresh,
  refreshing,
  reloadConfig,
  reloadPending,
  removeProxy,
  saveEdit,
  savePreferences,
  submitProxy,
  switchSaving,
  viewConfig,
} = useFrpTab();
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
          <button id="reloadFrpBtn" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="reloadPending || refreshing || !frp.enabled" @click="reloadConfig">{{ reloadPending ? '重载中...' : '重载配置' }}</button>
          <button id="viewFrpConfigBtn" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="configPending || refreshing || !frp.enabled" @click="viewConfig">{{ configPending ? '读取中...' : '查看配置' }}</button>
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
                <input id="frpEnabledSwitch" class="peer h-0 w-0 opacity-0" type="checkbox" :checked="frp.enabled" :disabled="switchSaving" @change="applySwitch" />
                <span class="absolute inset-0 cursor-pointer rounded-full bg-slate-300 transition peer-checked:bg-slate-900"></span>
                <span class="absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.18)] transition peer-checked:translate-x-5"></span>
              </label>
              <span id="frpEnabledText" class="text-sm font-semibold" :class="frp.enabled ? 'text-emerald-700' : 'text-slate-600'">{{ frp.enabled ? '已启用' : '已关闭' }}</span>
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
                <i class="inline-block h-2 w-2 rounded-full animate-[healthPulse_1.6s_ease-in-out_infinite]" :class="frp.health.serverReachable ? 'bg-emerald-700' : 'bg-[#922f2f]'"></i>
                服务端 {{ frp.health.serverReachable ? '可达' : '不可达' }}
              </span>
              <span class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50/70 px-2.5 py-1 text-[12px] text-slate-600">
                <i class="inline-block h-2 w-2 rounded-full animate-[healthPulse_1.6s_ease-in-out_infinite]" :class="frp.health.adminReachable ? 'bg-emerald-700' : 'bg-[#922f2f]'"></i>
                管理端 {{ frp.health.adminReachable ? '可达' : '不可达' }}
              </span>
            </div>
          </div>
          <p class="mt-auto pt-2 text-xs leading-5 text-slate-500">目前 FRP 状态 · {{ healthState.label }}</p>
        </div>

        <StatCard
          class="md:col-span-2 xl:col-span-4"
          title="代理数量"
          badge="当前"
          :value="frp.proxies.length"
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
              :disabled="createPending || !frp.enabled"
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
        :can-edit="frp.enabled && !editPending"
        :can-delete="frp.enabled"
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
      :enabled="frp.enabled"
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
      :admin-password-set="adminPasswordSet"
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
        <pre class="max-h-[64vh] overflow-y-auto rounded-[14px] border border-slate-200 bg-slate-50/60 p-3 font-mono text-xs leading-relaxed text-slate-900">{{ frp.configText || '暂无配置' }}</pre>
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
