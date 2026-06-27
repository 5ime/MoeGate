<script setup>
import { inject, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useSystemStore } from '../../stores/systemStore';
import { useUiStore } from '../../stores/uiStore';
import TrendChart from '../charts/TrendChart.vue';
import StatCard from '../ui/StatCard.vue';
import SectionCard from '../ui/SectionCard.vue';

const systemStore = useSystemStore();
const uiStore = useUiStore();
const { systemStatus, metricsText, trend } = storeToRefs(systemStore);

const refreshing = ref(false);
const preferencesLoading = ref(false);
const openSystemPreferences = inject('openSystemPreferences', null);

async function refresh() {
  try {
    refreshing.value = true;
    await systemStore.loadSystemPanel();
  } catch (error) {
    uiStore.showMessage(error.message || '系统面板加载失败', 'error');
  } finally {
    refreshing.value = false;
  }
}

async function openPreferences() {
  if (preferencesLoading.value) return;
  if (typeof openSystemPreferences !== 'function') {
    uiStore.showMessage('系统偏好入口不可用', 'error');
    return;
  }

  preferencesLoading.value = true;
  try {
    await openSystemPreferences();
  } catch (error) {
    uiStore.showMessage(error.message || '加载偏好设置失败', 'error');
  } finally {
    preferencesLoading.value = false;
  }
}
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
            :disabled="preferencesLoading || refreshing"
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
                <span id="sysCpuUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ systemStatus?.cpu_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">CPU</span>
                <span class="text-slate-300">/</span>
                <span id="sysMemoryUsageNow" class="mt-1 block text-[26px] font-semibold leading-none tracking-tight text-slate-900">{{ systemStatus?.memory_usage ?? '-' }}</span>
                <span class="text-xs font-medium text-slate-500">内存</span>
              </div>
            </SectionCard>
            <StatCard title="CPU 核心" :value="systemStatus?.cpu_cores ?? '-'" value-id="sysCpuCores" />
            <StatCard title="内存总量" :value="systemStatus?.memory_total || '-'" value-id="sysMemoryTotal" />

            <!-- 第 2 行 -->
            <SectionCard class="h-[90px] flex flex-col justify-between px-4 py-3">
              <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">磁盘容量</div>
              <div class="mt-1 flex items-baseline gap-2">
                <span id="sysDiskUsage" class="block text-[26px] font-semibold leading-none tracking-tight text-slate-900">
                  {{ systemStatus?.disk_usage || '-' }}
                </span>
                <span class="text-slate-300">/</span>
                <span id="sysDiskMeta" class="text-xs font-medium text-slate-500">
                  <span v-if="systemStatus?.disk_used && systemStatus?.disk_total">
                    {{ systemStatus?.disk_used }}/{{ systemStatus?.disk_total }}
                  </span>
                  <span v-else>-</span>
                </span>
              </div>
            </SectionCard>
            <StatCard title="系统类型" :value="systemStatus?.system || '-'" value-id="sysSystem" />
            <StatCard title="Docker 版本" :value="systemStatus?.docker_version || '-'" value-id="sysDockerVersion" />
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
            :threshold="80"
            :values="trend.cpu"
            :timestamps="trend.ts"
          />
          <TrendChart
            chart-id="memTrend"
            meta-id="memTrendMeta"
            title="内存趋势"
            color="#475569"
            card-class="rounded-xl border border-slate-200 bg-white p-4"
            :threshold="85"
            :values="trend.mem"
            :timestamps="trend.ts"
          />
        </div>
    </div>

    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-base font-semibold tracking-tight text-slate-900">Metrics</h3>
        <span class="text-[13px] text-slate-500">Prometheus 文本</span>
      </div>
      <pre class="mt-1.5 max-h-[430px] overflow-auto rounded-xl border border-slate-200 bg-[#fbfbfc] p-3 font-mono text-xs leading-relaxed text-slate-900">{{ metricsText || '# 暂无指标' }}</pre>
    </div>
  </section>
</template>
