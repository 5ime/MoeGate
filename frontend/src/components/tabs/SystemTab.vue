<script setup>
import { computed, onMounted, ref } from 'vue';
import { loadAlertWebhookSetting, loadAlertPerfSettings, loadSystemPanel, saveAlertPerfSettings, saveAlertWebhookSetting, sendAlertWebhookTest, showMessage, store } from '../../stores/appStore';
import TrendChart from '../charts/TrendChart.vue';
import SystemPreferencesModal from '../system/SystemPreferencesModal.vue';
import StatCard from '../ui/StatCard.vue';
import SectionCard from '../ui/SectionCard.vue';

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
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
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
            <SectionCard class="h-[90px] flex flex-col justify-between px-4 py-3">
              <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">当前负载</div>
              <div class="mt-1 flex items-baseline gap-2">
                <span id="sysCpuUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.cpu_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">CPU</span>
                <span class="text-slate-300">/</span>
                <span id="sysMemoryUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ store.systemStatus?.memory_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">内存</span>
              </div>
            </SectionCard>
            <StatCard title="CPU 核心" :value="store.systemStatus?.cpu_cores ?? '-'" value-id="sysCpuCores" />
            <StatCard title="内存总量" :value="store.systemStatus?.memory_total || '-'" value-id="sysMemoryTotal" />

            <!-- 第 2 行 -->
            <SectionCard class="h-[90px] flex flex-col justify-between px-4 py-3">
              <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">磁盘容量</div>
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
            </SectionCard>
            <StatCard title="系统类型" :value="store.systemStatus?.system || '-'" value-id="sysSystem" />
            <StatCard title="Docker 版本" :value="store.systemStatus?.docker_version || '-'" value-id="sysDockerVersion" />
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
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
            card-class="rounded-xl border border-slate-200 bg-white p-4"
            :threshold="Number(store.systemStatus?.alert_cpu_threshold ?? 80)"
            :values="store.trend.cpu"
            :timestamps="store.trend.ts"
          />
          <TrendChart
            chart-id="memTrend"
            meta-id="memTrendMeta"
            title="内存趋势"
            color="#475569"
            card-class="rounded-xl border border-slate-200 bg-white p-4"
            :threshold="Number(store.systemStatus?.alert_mem_threshold ?? 85)"
            :values="store.trend.mem"
            :timestamps="store.trend.ts"
          />
        </div>
    </div>

    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-base font-semibold tracking-tight text-slate-900">Metrics</h3>
        <span class="text-[13px] text-slate-500">Prometheus 文本</span>
      </div>
      <pre class="mt-1.5 max-h-[430px] overflow-auto rounded-xl border border-slate-200 bg-[#fbfbfc] p-3 font-mono text-xs leading-relaxed text-slate-900">{{ store.metricsText || '# 暂无指标' }}</pre>
    </div>

    <SystemPreferencesModal
      :visible="preferencesModal"
      :saving="preferencesSaving"
      :test-sending="testSending"
      v-model:webhook-url="webhookUrl"
      v-model:webhook-timeout="webhookTimeout"
      v-model:perf-interval="perfInterval"
      v-model:cpu-threshold="cpuThreshold"
      v-model:cpu-intervals="cpuIntervals"
      v-model:mem-threshold="memThreshold"
      v-model:mem-intervals="memIntervals"
      v-model:cooldown-sec="cooldownSec"
      @close="preferencesModal = false"
      @save="savePreferences"
      @send-test="sendTest"
    />
  </section>
</template>
