<script setup>
import { computed, onMounted, ref } from 'vue';
import BaseModal from '../BaseModal.vue';
import { loadAlertWebhookSetting, loadAlertPerfSettings, loadSystemPanel, saveAlertPerfSettings, saveAlertWebhookSetting, sendAlertWebhookTest, showMessage, store } from '../../stores/appStore';
import TrendChart from '../charts/TrendChart.vue';

const refreshing = ref(false);
const preferencesModal = ref(false);
const preferencesLoading = ref(false);
const preferencesSaving = ref(false);
const testSending = ref(false);
const webhookUrl = ref('');
const webhookTimeout = ref('5');
const perfInterval = ref('300');
const cpuThreshold = ref('95');
const cpuIntervals = ref('3');
const memThreshold = ref('90');
const memIntervals = ref('3');
const cooldownSec = ref('900');

const webhookEnabled = computed(() => Boolean(String(webhookUrl.value || '').trim()));

async function refresh() {
  try {
    refreshing.value = true;
    await loadSystemPanel();
  } catch (error) {
    showMessage(error.message || '系统面板加载失败', 'error');
  } finally {
    refreshing.value = false;
  }
}

async function openPreferences() {
  preferencesLoading.value = true;
  try {
    const data = await loadAlertWebhookSetting();
    webhookUrl.value = String(data?.webhookUrl || '');
    webhookTimeout.value = String(data?.webhookTimeout ?? 5);

    const perf = await loadAlertPerfSettings();
    perfInterval.value = String(perf?.performanceLogInterval ?? 300);
    cpuThreshold.value = String(perf?.alertCpuThreshold ?? 95);
    cpuIntervals.value = String(perf?.alertCpuSustainedIntervals ?? 3);
    memThreshold.value = String(perf?.alertMemThreshold ?? 90);
    memIntervals.value = String(perf?.alertMemSustainedIntervals ?? 3);
    cooldownSec.value = String(perf?.alertCooldownSec ?? 900);
    preferencesModal.value = true;
  } catch (error) {
    showMessage(error.message || '加载偏好设置失败', 'error');
  } finally {
    preferencesLoading.value = false;
  }
}

async function savePreferences() {
  preferencesSaving.value = true;
  try {
    const [r1, r2] = await Promise.all([
      saveAlertWebhookSetting(webhookUrl.value, webhookTimeout.value),
      saveAlertPerfSettings({
        performanceLogInterval: Number(perfInterval.value),
        alertCpuThreshold: Number(cpuThreshold.value),
        alertCpuSustainedIntervals: Number(cpuIntervals.value),
        alertMemThreshold: Number(memThreshold.value),
        alertMemSustainedIntervals: Number(memIntervals.value),
        alertCooldownSec: Number(cooldownSec.value),
      }),
    ]);
    const msg = String((r2?.msg || r1?.msg) || '偏好设置已保存');
    showMessage(msg, 'success');
    preferencesModal.value = false;
    await refresh();
  } catch (error) {
    showMessage(error.message || '保存偏好设置失败', 'error');
  } finally {
    preferencesSaving.value = false;
  }
}

async function sendTest() {
  testSending.value = true;
  try {
    const result = await sendAlertWebhookTest();
    showMessage(String(result?.msg || '测试消息已发送'), 'success');
  } catch (error) {
    showMessage(error.message || '发送测试消息失败', 'error');
  } finally {
    testSending.value = false;
  }
}

onMounted(() => {
  refresh();
});
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-md border border-slate-200 p-5 md:p-6">
      <div class="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">系统运行</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">状态总览</h2>
        </div>
        <div class="flex items-center gap-2">
          <button
            id="openSystemPreferencesBtn"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="preferencesLoading || preferencesSaving || refreshing"
            @click="openPreferences"
          >偏好设置</button>
          <button
            id="refreshSystemBtn"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="refreshing"
            @click="refresh"
          >{{ refreshing ? '刷新中...' : '刷新系统状态' }}</button>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div class="xl:col-span-12">
          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <!-- 第 1 行 -->
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">当前负载</span>
              <div class="mt-1 flex items-baseline gap-2">
                <span id="sysCpuUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.cpu_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">CPU</span>
                <span class="text-slate-300">/</span>
                <span id="sysMemoryUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.memory_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">内存</span>
              </div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">CPU 核心</span>
              <p id="sysCpuCores" class="mb-2 mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.cpu_cores ?? '-' }}</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">内存总量</span>
              <p id="sysMemoryTotal" class="mb-2 mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.memory_total || '-' }}</p>
            </div>

            <!-- 第 2 行 -->
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">磁盘容量</span>
              <div class="mt-1 flex items-baseline gap-2">
                <span id="sysDiskUsage" class="block text-[26px] font-semibold leading-none tracking-tight text-slate-900">
                  {{ store.systemStatus?.disk_usage || '-' }}
                </span>
                <span class="text-slate-300">/</span>
                <span id="sysDiskMeta" class="text-xs font-medium text-slate-500">
                  <span v-if="store.systemStatus?.disk_used && store.systemStatus?.disk_total">
                    {{ store.systemStatus?.disk_used }}/{{ store.systemStatus?.disk_total }}
                  </span>
                  <span v-else>-</span>
                </span>
              </div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">系统类型</span>
              <p id="sysSystem" class="mb-2 mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.system || '-' }}</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Docker 版本</span>
              <p id="sysDockerVersion" class="mb-2 mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.docker_version || '-' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-md border border-slate-200 p-5 md:p-6">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 class="text-base font-semibold tracking-tight text-slate-900">资源趋势</h3>
          <span class="text-[13px] text-slate-500">最近 20 次采样</span>
        </div>
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <TrendChart
            chart-id="cpuTrend"
            meta-id="cpuTrendMeta"
            title="CPU 趋势"
            color="#334155"
            card-class="rounded-[16px] border border-slate-200 bg-white p-4"
            :threshold="Number(store.systemStatus?.alert_cpu_threshold ?? 80)"
            :values="store.trend.cpu"
            :timestamps="store.trend.ts"
          />
          <TrendChart
            chart-id="memTrend"
            meta-id="memTrendMeta"
            title="内存趋势"
            color="#475569"
            card-class="rounded-[16px] border border-slate-200 bg-white p-4"
            :threshold="Number(store.systemStatus?.alert_mem_threshold ?? 85)"
            :values="store.trend.mem"
            :timestamps="store.trend.ts"
          />
        </div>
    </div>

    <div class="rounded-md border border-slate-200 p-5 md:p-6">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-base font-semibold tracking-tight text-slate-900">Metrics</h3>
        <span class="text-[13px] text-slate-500">Prometheus 文本</span>
      </div>
      <pre class="mt-1.5 max-h-[430px] overflow-auto rounded-[12px] border border-slate-200 bg-[#fbfbfc] p-3 font-mono text-xs leading-relaxed text-slate-900">{{ store.metricsText || '# 暂无指标' }}</pre>
    </div>

    <BaseModal
      :visible="preferencesModal"
      title="偏好设置"
      subtitle="Webhook 填写后默认启用资源告警；阈值/采样间隔会实时生效"
      icon="bolt"
      width="max-w-[880px]"
      @close="preferencesModal = false"
    >
      <div class="space-y-4">
        <!-- 顶部：Webhook -->
        <div>
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <div class="mb-3 flex items-start justify-between gap-3">
              <div>
                <p class="text-xs font-semibold tracking-tight text-slate-900">Webhook</p>
                <p class="mt-1 text-xs text-slate-500">填写后默认启用资源告警，并可用于容器异常通知。</p>
              </div>
              <span
                class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
                :class="String(webhookUrl || '').trim() ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'"
              >{{ String(webhookUrl || '').trim() ? '已启用' : '未启用' }}</span>
            </div>

            <label class="block text-xs font-medium text-slate-600">Webhook URL</label>
            <input
              v-model="webhookUrl"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              placeholder="例如：https://example.com/webhook 或飞书机器人 webhook"
            />
            <p class="mt-2 text-xs leading-5 text-slate-500">留空则关闭推送。</p>

            <div class="relative mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label class="block text-xs font-medium text-slate-600">超时（秒）</label>
                <input
                  v-model="webhookTimeout"
                  type="number"
                  min="1"
                  step="1"
                  class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                />
              </div>
              <div class="flex items-end">
                <button
                  class="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-[12px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
                  :disabled="testSending || !String(webhookUrl || '').trim()"
                  @click="sendTest"
                >{{ testSending ? '发送中...' : '发送测试' }}</button>
              </div>

              <div
                v-if="!webhookEnabled"
                class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
              >请先填写 Webhook URL</div>
            </div>
          </div>
        </div>

        <!-- 底部：告警策略 + 阈值 -->
        <div>
          <div class="relative rounded-2xl border border-slate-200 bg-white p-4">
            <div class="mb-3">
              <p class="text-xs font-semibold tracking-tight text-slate-900">资源告警策略</p>
              <p class="mt-1 text-xs text-slate-500">CPU/内存任一达到“持续区间”条件即推送；冷却时间内只推送一次。</p>
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
                <label class="block text-xs font-medium text-slate-600">采样间隔（秒）</label>
                <input v-model="perfInterval" type="number" min="1" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                <p class="mt-2 text-[11px] leading-4 text-slate-500">越小越灵敏，也更频繁采样。</p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
                <label class="block text-xs font-medium text-slate-600">冷却时间（秒）</label>
                <input v-model="cooldownSec" type="number" min="0" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                <p class="mt-2 text-[11px] leading-4 text-slate-500">避免告警风暴；0 表示不冷却。</p>
              </div>
            </div>

            <div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div class="rounded-xl border border-slate-200 p-3">
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-semibold text-slate-900">CPU</span>
                  <span class="text-[11px] text-slate-500">阈值 + 持续区间</span>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs font-medium text-slate-600">阈值（%）</label>
                    <input v-model="cpuThreshold" type="number" min="1" max="100" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-slate-600">持续区间</label>
                    <input v-model="cpuIntervals" type="number" min="1" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-200 p-3">
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-semibold text-slate-900">内存</span>
                  <span class="text-[11px] text-slate-500">阈值 + 持续区间</span>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs font-medium text-slate-600">阈值（%）</label>
                    <input v-model="memThreshold" type="number" min="1" max="100" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-slate-600">持续区间</label>
                    <input v-model="memIntervals" type="number" min="1" step="1" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400" />
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
              <p class="text-xs text-slate-600">
                触发时间约为 <span class="font-semibold text-slate-900">采样间隔 × 持续区间</span>。
                若要快速验证推送，建议先把持续区间设为 <span class="font-semibold text-slate-900">1</span>。
              </p>
            </div>

            <div
              v-if="!webhookEnabled"
              class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
            >请先填写 Webhook URL</div>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="preferencesSaving" @click="preferencesModal = false">取消</button>
        <button class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" :disabled="preferencesSaving" @click="savePreferences">{{ preferencesSaving ? '保存中...' : '保存设置' }}</button>
      </template>
    </BaseModal>
  </section>
</template>
