<script setup>
import { inject, onMounted, reactive, ref } from 'vue';
import {
  loadContainerDefaultsSetting,
  loadContainerLimitsSetting,
  loadContainers,
  loadManagedNetworks,
  saveContainerLimitsSetting,
  showMessage,
  store,
} from '../../stores/appStore';
import BaseModal from '../BaseModal.vue';
import BuildProgressModal from '../BuildProgressModal.vue';
import { parseKeyValueLines } from '../../composables';
import KeyValueLinesEditor from '../KeyValueLinesEditor.vue';
import CreatePreferencesModal from '../container/CreatePreferencesModal.vue';

const form = reactive({
  source: 'path',
  port_mode: 'random',
  path: '',
  image: '',
  uid: '',
  command: '',
  network: '',
  port_mappings_text: '',
  min_port: '',
  max_port: '',
  max_time: '',
  tag: '',
  memory_limit: '',
  cpu_limit: '',
  cpu_shares: '',
  envText: '',
});

const showBuildModal = ref(false);
const buildPayload = ref(null);
const showPreferencesModal = ref(false);
const maxContainersInput = ref('');
const maxRenewTimesInput = ref('');
const limitsLoading = ref(false);
const limitsSaving = ref(false);
const systemPreferencesOpening = ref(false);
const openSystemPreferences = inject('openSystemPreferences', null);

function applyContainerDefaults(defaults = store.settings.containerDefaults) {
  const source = defaults || {};
  form.max_time = String(source.maxTime ?? 3600);
  form.min_port = String(source.minPort ?? 20000);
  form.max_port = String(source.maxPort ?? 30000);
  form.memory_limit = String(source.memoryLimit ?? '512m');
  form.cpu_limit = String(source.cpuLimit ?? 1.0);
  form.cpu_shares = String(source.cpuShares ?? 1024);
}

function parseEnvText(text) {
  const raw = String(text || '').trim();
  if (!raw) return {};
  return parseKeyValueLines(raw, {
    allowColon: true,
    invalidLineMessage: (line) => `环境变量格式错误，请使用 key=value: ${line}`,
    emptyKeyMessage: (line) => `环境变量键不能为空: ${line}`,
  });
}

function submit() {
  const payload = { source: form.source };
  if (form.source === 'image') {
    payload.image = form.image.trim();
    if (!payload.image) {
      showMessage('请填写镜像名称', 'error');
      return;
    }
  } else {
    payload.path = form.path.trim();
    if (!payload.path) {
      showMessage('请填写容器路径', 'error');
      return;
    }
  }

  if (form.uid.trim()) payload.uid = form.uid.trim();
  if (form.command.trim()) payload.command = form.command.trim();
  if (form.network.trim()) payload.network = form.network.trim();
  if (form.port_mode === 'fixed') {
    if (!form.port_mappings_text.trim()) {
      showMessage('请填写固定端口映射', 'error');
      return;
    }
    payload.port_mappings = form.port_mappings_text.trim();
  } else {
    if (form.min_port) payload.min_port = Number(form.min_port);
    if (form.max_port) payload.max_port = Number(form.max_port);
  }
  if (form.max_time) payload.max_time = Number(form.max_time);
  if (form.tag.trim()) payload.tag = form.tag.trim();
  if (form.memory_limit.trim()) payload.memory_limit = form.memory_limit.trim();
  if (form.cpu_limit) payload.cpu_limit = Number(form.cpu_limit);
  if (form.cpu_shares) payload.cpu_shares = Number(form.cpu_shares);

  try {
    if (form.envText.trim()) {
      payload.env = parseEnvText(form.envText);
    }
  } catch (error) {
    showMessage(error.message || '环境变量格式错误', 'error');
    return;
  }

  buildPayload.value = payload;
  showBuildModal.value = true;
}

function resetForm() {
  form.source = 'path';
  form.port_mode = 'random';
  form.path = '';
  form.image = '';
  form.uid = '';
  form.command = '';
  form.network = '';
  form.port_mappings_text = '';
  form.min_port = String(store.settings.containerDefaults.minPort ?? 20000);
  form.max_port = String(store.settings.containerDefaults.maxPort ?? 30000);
  form.max_time = String(store.settings.containerDefaults.maxTime ?? 3600);
  form.tag = '';
  form.memory_limit = String(store.settings.containerDefaults.memoryLimit ?? '512m');
  form.cpu_limit = String(store.settings.containerDefaults.cpuLimit ?? 1.0);
  form.cpu_shares = String(store.settings.containerDefaults.cpuShares ?? 1024);
  form.envText = '';
}

async function loadContainerDefaults() {
  try {
    await loadContainerDefaultsSetting();
    applyContainerDefaults();
  } catch (error) {
    showMessage(error.message || '加载容器默认配置失败，已使用内置默认值', 'warning');
    applyContainerDefaults();
  }
}

async function onBuildSuccess() {
  showMessage('容器创建成功', 'success');
  await loadContainers();
  resetForm();
}

function onBuildClose() {
  showBuildModal.value = false;
  buildPayload.value = null;
}

async function loadContainerLimits() {
  limitsLoading.value = true;
  try {
    const limits = await loadContainerLimitsSetting();
    maxContainersInput.value = String(limits.maxContainers ?? 30);
    maxRenewTimesInput.value = String(limits.maxRenewTimes ?? 3);
  } catch (error) {
    showMessage(error.message || '加载容器限制设置失败', 'error');
  } finally {
    limitsLoading.value = false;
  }
}

async function savePreferences() {
  limitsSaving.value = true;
  try {
    const maxContainers = Number.parseInt(String(maxContainersInput.value || '').trim(), 10);
    const maxRenewTimes = Number.parseInt(String(maxRenewTimesInput.value || '').trim(), 10);
    if (!Number.isFinite(maxContainers) || maxContainers <= 0) {
      throw new Error('最大容器数需为正整数');
    }
    if (!Number.isFinite(maxRenewTimes) || maxRenewTimes < 0) {
      throw new Error('最大续期次数需为非负整数');
    }

    await saveContainerLimitsSetting(maxContainers, maxRenewTimes);
    maxContainersInput.value = String(store.settings.containerLimits.maxContainers);
    maxRenewTimesInput.value = String(store.settings.containerLimits.maxRenewTimes);
    showMessage('创建偏好设置已更新', 'success');
    closePreferencesModal();
  } catch (error) {
    showMessage(error.message || '保存创建偏好设置失败', 'error');
  } finally {
    limitsSaving.value = false;
  }
}

async function openPreferencesModal() {
  showPreferencesModal.value = true;
  await loadContainerLimits();
}

function closePreferencesModal() {
  showPreferencesModal.value = false;
}

async function openImageSourceSettings() {
  if (systemPreferencesOpening.value) return;
  if (typeof openSystemPreferences !== 'function') {
    showMessage('系统偏好入口不可用', 'error');
    return;
  }

  systemPreferencesOpening.value = true;
  try {
    await openSystemPreferences();
  } catch (error) {
    showMessage(error.message || '打开系统偏好失败', 'error');
  } finally {
    systemPreferencesOpening.value = false;
  }
}

function validateEnvFormat() {
  const raw = String(form.envText || '').trim();
  if (!raw) {
    showMessage('环境变量为空，默认不传递额外变量', 'info');
    return;
  }

  try {
    const parsed = parseEnvText(raw);
    showMessage(`格式正确，共 ${Object.keys(parsed).length} 项环境变量`, 'success');
  } catch (error) {
    showMessage(error.message || '环境变量格式错误，请检查填写内容', 'error');
  }
}

onMounted(async () => {
  await loadContainerDefaults();
  // 可选：用于“网络”下拉建议（不影响创建行为，加载失败也可直接手填 network 名称）
  loadManagedNetworks().catch(() => {});
});
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">创建向导</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">创建新容器</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="systemPreferencesOpening"
            @click="openImageSourceSettings"
          >镜像源设置</button>
          <button
            type="button"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            @click="openPreferencesModal"
          >
            创建偏好
          </button>
          <button
            type="button"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            @click="store.activeTab = 'containers'"
          >
            查看容器
          </button>
        </div>
      </div>
    </div>

    <form id="createContainerForm" @submit.prevent="submit">
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">

        <div class="space-y-5">

          <div class="rounded-xl border border-slate-200 p-5 md:p-6">
            <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.532a2.25 2.25 0 011.591.659l4.418 4.418A2.25 2.25 0 0117.25 8.59V17.75A2.25 2.25 0 0115 20H5.25A2.25 2.25 0 013 17.75V4.25z" clip-rule="evenodd"/></svg>
              <span>部署来源</span>
            </div>

            <div class="relative flex gap-0 rounded-xl border border-slate-200 bg-slate-50 p-1">
              <div
                class="pointer-events-none absolute bottom-1 left-1 top-1 w-[calc(50%-4px)] rounded-lg border border-slate-200 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-transform duration-200"
                :style="{ transform: form.source === 'image' ? 'translateX(100%)' : 'translateX(0%)' }"
                aria-hidden="true"
              ></div>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.source === 'path' }"
                @click="form.source = 'path'"
              >
                路径
              </button>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.source === 'image' }"
                @click="form.source = 'image'"
              >
                镜像
              </button>
            </div>

            <div v-if="form.source === 'path'" class="mt-3">
              <label for="containerPath" class="mb-2 block text-sm font-medium text-slate-900">Dockerfile / Compose 路径</label>
              <input id="containerPath" v-model="form.path" type="text" required placeholder="/path/to/dockerfile_or_compose" class="w-full rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100" />
              <p class="mt-1.5 text-xs leading-relaxed text-slate-500">支持含 Dockerfile 或 docker-compose.yml 的目录路径</p>
            </div>

            <div v-else class="mt-3">
              <label for="containerImage" class="mb-2 block text-sm font-medium text-slate-900">镜像名称</label>
              <input id="containerImage" v-model="form.image" type="text" required placeholder="nginx:latest" class="w-full rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100" />
              <p class="mt-1.5 text-xs leading-relaxed text-slate-500">镜像将直接拉取运行，跳过构建流程</p>
            </div>
          </div>

          <div class="rounded-xl border border-slate-200 p-5 md:p-6">
            <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/></svg>
              <span>基础参数</span>
              <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
            </div>

            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label for="containerUid" class="mb-2 block text-xs font-medium text-slate-600">用户标识 (UID)</label>
                <input
                  id="containerUid"
                  v-model="form.uid"
                  type="text"
                  placeholder="可选"
                  class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:outline-none"
                />
                <p class="mt-2 text-xs leading-relaxed text-slate-500">留空则自动生成 UUID</p>
              </div>

              <div>
                <label for="maxTime" class="mb-2 block text-xs font-medium text-slate-600">存活时间 (秒)</label>
                <input
                  id="maxTime"
                  v-model="form.max_time"
                  type="number"
                  placeholder="3600"
                  class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </div>

              <div>
                <label for="containerCommand" class="mb-2 block text-xs font-medium text-slate-600">启动命令</label>
                <input
                  id="containerCommand"
                  v-model="form.command"
                  type="text"
                  placeholder="可选"
                  class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </div>

              <div>
                <label for="containerTag" class="mb-2 block text-xs font-medium text-slate-600">构建标签</label>
                <div class="relative">
                  <input
                    id="containerTag"
                    v-model="form.tag"
                    :disabled="form.source === 'image'"
                    type="text"
                    :placeholder="form.source === 'image' ? '镜像模式下不可用' : '可选'"
                    class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
                  />
                  <div
                    v-if="form.source === 'image'"
                    class="absolute inset-0 flex items-center justify-center rounded-lg bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
                  >
                    镜像模式下不可用
                  </div>
                </div>
              </div>

              <div class="md:col-span-2">
                <div class="mb-2 flex items-center justify-between gap-2">
                  <label for="containerNetworkSelect" class="block text-xs font-medium text-slate-600">网络</label>
                </div>

                <div class="relative">
                  <select
                    id="containerNetworkSelect"
                    v-model="form.network"
                    class="w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 pr-10 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                  >
                    <option value="">默认 (bridge)</option>
                    <option v-for="item in (store.networks.items || [])" :key="item.id || item.name" :value="item.name">
                      {{ item.name }}
                    </option>
                  </select>
                  <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500">
                    <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </div>

                <p class="mt-2 text-xs leading-relaxed text-slate-500">填写后，单容器将加入该 Docker network（用于容器间互通/隔离/DNS）。</p>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-5">

          <div class="rounded-xl border border-slate-200 p-5 md:p-6">
            <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clip-rule="evenodd"/></svg>
              <span>端口分配</span>
            </div>
            <div class="relative mb-3 flex gap-0 rounded-xl border border-slate-200 bg-slate-50 p-1">
              <div
                class="pointer-events-none absolute bottom-1 left-1 top-1 w-[calc(50%-4px)] rounded-lg border border-slate-200 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-transform duration-200"
                :style="{ transform: form.port_mode === 'fixed' ? 'translateX(100%)' : 'translateX(0%)' }"
                aria-hidden="true"
              ></div>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.port_mode === 'random' }"
                @click="form.port_mode = 'random'"
              >
                随机分配
              </button>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.port_mode === 'fixed' }"
                @click="form.port_mode = 'fixed'"
              >
                固定映射
              </button>
            </div>

            <div v-if="form.port_mode === 'fixed'">
              <label for="portMappings" class="mb-2 block text-xs font-medium text-slate-600">固定端口映射</label>
              <input id="portMappings" v-model="form.port_mappings_text" type="text" placeholder="8080:80,8443:443" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              <p class="mt-2 text-xs leading-relaxed text-slate-500">格式: host:container，多个用逗号分隔，例如 8080:80,8443:443</p>
            </div>

            <div v-else class="grid grid-cols-2 gap-4 max-md:grid-cols-1">
              <div>
                <label for="minPort" class="mb-2 block text-xs font-medium text-slate-600">最小端口</label>
                <input id="minPort" v-model="form.min_port" type="number" min="1024" max="65535" placeholder="20000" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
              <div>
                <label for="maxPort" class="mb-2 block text-xs font-medium text-slate-600">最大端口</label>
                <input id="maxPort" v-model="form.max_port" type="number" min="1024" max="65535" placeholder="30000" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
            </div>
            <p v-if="form.port_mode === 'random'" class="mt-2 text-xs leading-relaxed text-slate-500">系统会在给定范围内自动选择可用宿主机端口</p>
          </div>

          <div class="rounded-xl border border-slate-200 p-5 md:p-6">
            <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path d="M13 7H7v6h6V7z"/><path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clip-rule="evenodd"/></svg>
              <span>资源限制</span>
              <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
            </div>
            <div class="grid grid-cols-3 gap-3 max-lg:grid-cols-1">
              <div>
                <label for="memoryLimit" class="mb-2 block text-xs font-medium text-slate-600">内存</label>
                <input id="memoryLimit" v-model="form.memory_limit" type="text" placeholder="512m" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
              <div>
                <label for="cpuLimit" class="mb-2 block text-xs font-medium text-slate-600">CPU (核)</label>
                <input id="cpuLimit" v-model="form.cpu_limit" type="number" step="0.1" min="0" placeholder="1.0" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
              <div>
                <label for="cpuShares" class="mb-2 block text-xs font-medium text-slate-600">Shares</label>
                <input id="cpuShares" v-model="form.cpu_shares" type="number" min="0" placeholder="1024" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
            </div>
          </div>

          <div class="rounded-xl border border-slate-200 p-5 md:p-6">
            <div class="mb-2 flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm7 10.5a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10z" clip-rule="evenodd"/></svg>
                <span class="text-sm font-semibold tracking-tight text-slate-900">环境变量</span>
                <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
              </div>
            </div>
            <div class="mt-2">
              <KeyValueLinesEditor
                v-model="form.labelsText"
                :rows="3"
                placeholder="例如&#10;env=test&#10;owner=lab"
                @validate="validateLabelFormat"
              >
                <template #header>
                  <div>
                    <p class="mt-1 text-xs text-slate-500">每行一个标签，格式 key=value。系统标签会自动补齐，不需要手填。</p>
                  </div>
                </template>
              </KeyValueLinesEditor>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3.5 max-md:flex-col max-md:items-stretch max-md:text-center">
        <div class="flex items-center gap-2 max-md:justify-center">
          <span v-if="form.port_mode === 'fixed' && form.port_mappings_text" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">端口映射: {{ form.port_mappings_text }}</span>
          <span v-else-if="form.port_mode === 'random' && (form.min_port || form.max_port)" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">端口范围: {{ form.min_port || '默认最小值' }} - {{ form.max_port || '默认最大值' }}</span>
          <span v-if="form.source === 'path' && form.path" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">路径: {{ form.path }}</span>
          <span v-else-if="form.source === 'image' && form.image" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">镜像: {{ form.image }}</span>
          <span v-else class="text-xs text-slate-400">请先选择部署来源</span>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="resetForm">重置</button>
          <button type="submit" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55">
            创建容器
          </button>
        </div>
      </div>

    </form>

    <BuildProgressModal
      :visible="showBuildModal"
      :payload="buildPayload"
      @success="onBuildSuccess"
      @close="onBuildClose"
    />

    <CreatePreferencesModal
      :visible="showPreferencesModal"
      :limits-loading="limitsLoading"
      :limits-saving="limitsSaving"
      v-model:max-containers-input="maxContainersInput"
      v-model:max-renew-times-input="maxRenewTimesInput"
      @close="closePreferencesModal"
      @save="savePreferences"
    />
  </section>
</template>
