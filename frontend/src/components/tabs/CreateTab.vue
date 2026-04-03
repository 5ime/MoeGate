<script setup>
import { onMounted, reactive, ref } from 'vue';
import {
  loadContainerDefaultsSetting,
  loadContainerLimitsSetting,
  loadContainers,
  loadImageSourceSetting,
  saveContainerLimitsSetting,
  saveImageSourceSetting,
  showMessage,
  store,
} from '../../stores/appStore';
import BaseModal from '../BaseModal.vue';
import BuildProgressModal from '../BuildProgressModal.vue';

const form = reactive({
  source: 'path',
  port_mode: 'random',
  path: '',
  image: '',
  uid: '',
  command: '',
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
const showAdvanced = ref(false);
const showPreferencesModal = ref(false);
const imageSourceInput = ref('');
const maxContainersInput = ref('');
const maxRenewTimesInput = ref('');
const imageSourceLoading = ref(false);
const imageSourceSaving = ref(false);
const limitsLoading = ref(false);
const limitsSaving = ref(false);

function applyContainerDefaults(defaults = store.settings.containerDefaults) {
  const source = defaults || {};
  form.max_time = String(source.maxTime ?? 3600);
  form.min_port = String(source.minPort ?? 20000);
  form.max_port = String(source.maxPort ?? 30000);
  form.memory_limit = String(source.memoryLimit ?? '512m');
  form.cpu_limit = String(source.cpuLimit ?? 1.0);
  form.cpu_shares = String(source.cpuShares ?? 1024);
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
      payload.env = JSON.parse(form.envText.trim());
    }
  } catch {
    showMessage('环境变量 JSON 格式错误', 'error');
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

async function loadImageSource() {
  imageSourceLoading.value = true;
  try {
    imageSourceInput.value = await loadImageSourceSetting();
  } catch (error) {
    showMessage(error.message || '加载镜像源设置失败', 'error');
  } finally {
    imageSourceLoading.value = false;
  }
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
  imageSourceSaving.value = true;
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

    await saveImageSourceSetting(imageSourceInput.value);
    await saveContainerLimitsSetting(maxContainers, maxRenewTimes);
    imageSourceInput.value = store.settings.imageSource;
    maxContainersInput.value = String(store.settings.containerLimits.maxContainers);
    maxRenewTimesInput.value = String(store.settings.containerLimits.maxRenewTimes);
    showMessage('创建偏好设置已更新', 'success');
    closePreferencesModal();
  } catch (error) {
    showMessage(error.message || '保存创建偏好设置失败', 'error');
  } finally {
    imageSourceSaving.value = false;
    limitsSaving.value = false;
  }
}

async function openPreferencesModal() {
  showPreferencesModal.value = true;
  await Promise.allSettled([loadImageSource(), loadContainerLimits()]);
}

function closePreferencesModal() {
  showPreferencesModal.value = false;
}

function validateEnvFormat() {
  const raw = String(form.envText || '').trim();
  if (!raw) {
    showMessage('环境变量为空，默认不传递额外变量', 'info');
    return;
  }

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      showMessage('环境变量必须是 JSON 对象格式，例如 {"KEY":"VALUE"}', 'error');
      return;
    }
    showMessage(`格式正确，共 ${Object.keys(parsed).length} 项环境变量`, 'success');
  } catch {
    showMessage('环境变量 JSON 格式错误，请检查逗号和引号', 'error');
  }
}

onMounted(async () => {
  await loadContainerDefaults();
});
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-md border border-slate-200 p-5 md:p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">创建向导</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">创建新容器</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            @click="openPreferencesModal"
          >
            偏好设置
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

          <div class="rounded-md border border-slate-200 p-5 md:p-6">
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
                <svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M1 3.5A1.5 1.5 0 012.5 2h3.879a1.5 1.5 0 011.06.44l1.122 1.12A1.5 1.5 0 009.62 4H13.5A1.5 1.5 0 0115 5.5v8a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 011 13.5v-10z"/></svg>
                路径
              </button>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.source === 'image' }"
                @click="form.source = 'image'"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M2 4a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V4zm2-.5a.5.5 0 00-.5.5v8a.5.5 0 00.5.5h8a.5.5 0 00.5-.5V4a.5.5 0 00-.5-.5H4z"/></svg>
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

          <div class="rounded-md border border-slate-200 p-5 md:p-6">
            <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/></svg>
              <span>基础参数</span>
            </div>

            <div class="grid grid-cols-2 gap-4 max-md:grid-cols-1">
              <div class="mb-4">
                <label for="containerUid" class="mb-2 block text-xs font-medium text-slate-600">用户标识 (UID)</label>
                <input id="containerUid" v-model="form.uid" type="text" placeholder="可选" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:outline-none" />
              </div>
              <div class="mb-4">
                <label for="maxTime" class="mb-2 block text-xs font-medium text-slate-600">存活时间 (秒)</label>
                <input id="maxTime" v-model="form.max_time" type="number" placeholder="3600" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 max-md:grid-cols-1">
              <div>
                <label for="containerCommand" class="mb-2 block text-xs font-medium text-slate-600">启动命令</label>
                <input id="containerCommand" v-model="form.command" type="text" placeholder="可选" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
              </div>
              <div>
                <label for="containerTag" class="mb-2 block text-xs font-medium text-slate-600">构建标签</label>
                <div class="relative">
                  <input id="containerTag" v-model="form.tag" :disabled="form.source === 'image'" type="text" :placeholder="form.source === 'image' ? '镜像模式下不可用' : '可选'" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55" />
                  <div
                    v-if="form.source === 'image'"
                    class="absolute inset-0 flex items-center justify-center rounded-lg bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
                  >
                    镜像模式下不可用
                  </div>
                </div>
              </div>
            </div>
            <p class="mt-2 text-xs leading-relaxed text-slate-500">用户标识 (UID) 留空则自动生成 UUID</p>
          </div>
        </div>

        <div class="space-y-5">

          <div class="rounded-md border border-slate-200 p-5 md:p-6">
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
                <svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a1 1 0 011 1v1.07a5.002 5.002 0 013.93 3.93H14a1 1 0 110 2h-1.07a5.002 5.002 0 01-3.93 3.93V14a1 1 0 11-2 0v-1.07a5.002 5.002 0 01-3.93-3.93H2a1 1 0 110-2h1.07a5.002 5.002 0 013.93-3.93V2a1 1 0 011-1zm0 4a3 3 0 100 6 3 3 0 000-6z"/></svg>
                随机分配
              </button>
              <button
                type="button"
                class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
                :class="{ 'text-slate-900': form.port_mode === 'fixed' }"
                @click="form.port_mode = 'fixed'"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M2 3.5A1.5 1.5 0 013.5 2h9A1.5 1.5 0 0114 3.5v9a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 12.5v-9zm2 1a.5.5 0 00-.5.5v6.293l2.146-2.147a.5.5 0 01.708 0L8 10.793l2.646-2.647a.5.5 0 01.708 0L12.5 9.293V4.5a.5.5 0 00-.5-.5H4z"/></svg>
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

          <div class="rounded-md border border-slate-200 p-5 md:p-6">
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

          <div class="rounded-2xl border border-slate-200 p-4">
            <div class="mb-2 flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm7 10.5a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10z" clip-rule="evenodd"/></svg>
                <span class="text-sm font-semibold tracking-tight text-slate-900">环境变量</span>
                <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
              </div>
              <div class="flex items-center gap-2">
                <button type="button" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="validateEnvFormat">检测格式</button>
                <button type="button" class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px]" @click="showAdvanced = !showAdvanced">
                  {{ showAdvanced ? '收起' : '展开' }}
                </button>
              </div>
            </div>
            <div v-show="showAdvanced" class="mt-2">
              <label for="containerEnv" class="mb-2 block text-xs font-medium text-slate-600">JSON 对象</label>
              <textarea id="containerEnv" v-model="form.envText" rows="4" placeholder='{"ENV_VAR1": "value1", "ENV_VAR2": "value2"}' class="w-full resize-y rounded-[14px] border border-slate-200 bg-white px-3 py-2 font-mono text-[13px] text-slate-900 outline-none transition focus:border-slate-400"></textarea>
              <p class="mt-2 text-xs leading-relaxed text-slate-500">必须是 JSON 对象格式；留空表示不传额外环境变量。</p>
            </div>
          </div>
        </div>

      </div>

      <div class="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-3.5 max-md:flex-col max-md:items-stretch max-md:text-center">
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
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
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

    <BaseModal
      :visible="showPreferencesModal"
      title="偏好设置"
      icon="bolt"
      width="max-w-[720px]"
      close-text="取消"
      @close="closePreferencesModal"
    >
      <div class="space-y-4">
        <!-- 镜像源 -->
        <div class="rounded-2xl border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-start justify-between gap-3">
            <div>
              <p class="text-xs font-semibold tracking-tight text-slate-900">镜像源</p>
              <p class="mt-1 text-xs text-slate-500">为公共镜像配置加速前缀，例如私有仓库或内部镜像站。</p>
            </div>
            <span
              class="rounded-full border px-2 py-0.5 text-[11px] font-medium"
              :class="String(imageSourceInput || '').trim() ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
            >
              {{ String(imageSourceInput || '').trim() ? '已设置' : '未设置' }}
            </span>
          </div>
          <label for="imageSourceInput" class="block text-xs font-medium text-slate-600">仓库前缀</label>
          <input
            id="imageSourceInput"
            v-model="imageSourceInput"
            type="text"
            :disabled="imageSourceLoading || imageSourceSaving || limitsSaving"
            placeholder="留空使用默认源，如 registry.example.com/mirror"
            class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
          />
        </div>

        <!-- 容器上限 -->
        <div class="rounded-2xl border border-slate-200 bg-white p-4">
          <div class="mb-3">
            <p class="text-xs font-semibold tracking-tight text-slate-900">容器上限</p>
            <p class="mt-1 text-xs text-slate-500">限制单实例可创建的最大容器数量与可续期次数。</p>
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label for="maxContainersInput" class="block text-xs font-medium text-slate-600">最大容器数</label>
              <input
                id="maxContainersInput"
                v-model="maxContainersInput"
                type="number"
                min="1"
                :disabled="limitsLoading || limitsSaving || imageSourceSaving"
                placeholder="默认 30"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              />
            </div>
            <div>
              <label for="maxRenewTimesInput" class="block text-xs font-medium text-slate-600">最大续期次数</label>
              <input
                id="maxRenewTimesInput"
                v-model="maxRenewTimesInput"
                type="number"
                min="0"
                :disabled="limitsLoading || limitsSaving || imageSourceSaving"
                placeholder="默认 3"
                class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              />
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button type="button" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="closePreferencesModal">取消</button>
        <button type="button" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="imageSourceLoading || imageSourceSaving || limitsLoading || limitsSaving" @click="savePreferences">
          {{ (imageSourceSaving || limitsSaving) ? '保存中...' : '保存' }}
        </button>
      </template>
    </BaseModal>
  </section>
</template>
