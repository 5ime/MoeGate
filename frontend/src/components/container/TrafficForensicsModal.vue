<script setup>
import { computed, watch } from 'vue';
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import { formatBytes, useTrafficForensics } from '../../composables/useTrafficForensics';

const props = defineProps({
  visible: { type: Boolean, default: false },
  container: { type: Object, default: null },
});

const emit = defineEmits(['close']);

const {
  status,
  parsed,
  files,
  hasFiles,
  message,
  loadingStatus,
  loadingSummary,
  pendingAction,
  reset,
  refreshStatus,
  loadSummary,
  toggleCapture,
  download,
} = useTrafficForensics();

const containerId = computed(() => props.container?.id || '');
const subtitle = computed(() => {
  const name = props.container?.name || containerId.value;
  return name ? `容器 ${name}` : '选择一个容器查看取证';
});

const captureEnabled = computed(() => status.value?.enabled !== false);
const isRunning = computed(() => !!status.value?.running);

watch(
  () => props.visible,
  (open) => {
    if (!open || !containerId.value) return;
    reset();
    void refreshStatus(containerId.value);
  },
);
</script>

<template>
  <BaseModal
    :visible="visible"
    title="流量取证"
    :subtitle="subtitle"
    width="max-w-[1080px]"
    icon="bolt"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div v-if="!containerId" class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">
        请从容器卡片点击「取证」进入
      </div>

      <template v-else>
        <div
          v-if="!captureEnabled"
          class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800"
        >
          服务端未开启流量取证能力（<span class="font-mono">ENABLE_TRAFFIC_CAPTURE=false</span>），当前容器不会抓包。
        </div>

        <SectionCard v-else title="取证状态">
          <template #header>
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="rounded-full border px-2.5 py-1 text-[11px] font-semibold"
                :class="isRunning
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 bg-slate-50 text-slate-600'"
              >{{ isRunning ? '录制中' : '未录制' }}</span>
              <span
                class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700"
                title="由创建参数 traffic_capture 决定的持久策略"
              >策略 {{ status?.policy === 'on' ? '抓包' : '不抓包' }}{{ status?.requested ? '（显式指定）' : '（默认）' }}</span>
              <span class="text-[11px] text-slate-500">{{ files.length }} 个文件 · {{ formatBytes(status?.total_bytes) }}</span>
              <span class="flex-1"></span>
              <button
                class="inline-flex h-8 items-center justify-center rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
                :disabled="loadingStatus"
                @click="refreshStatus(containerId)"
              >刷新</button>
            </div>
          </template>

          <div class="flex flex-wrap items-center gap-2">
            <button
              class="inline-flex h-8 items-center justify-center rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="pendingAction === 'stop' || !isRunning"
              @click="toggleCapture(containerId, 'stop')"
            >停止抓包</button>
            <button
              class="inline-flex h-8 items-center justify-center rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="pendingAction === 'start' || isRunning"
              title="容器标签不可变，强制开启只在本次运行有效"
              @click="toggleCapture(containerId, 'start')"
            >开始抓包</button>
            <span class="flex-1"></span>
            <button
              class="inline-flex h-8 items-center justify-center rounded-[10px] border border-slate-900 bg-slate-900 px-3 text-xs font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="loadingSummary || !hasFiles"
              @click="loadSummary(containerId)"
            >{{ loadingSummary ? '解析中...' : '生成摘要' }}</button>
          </div>
        </SectionCard>

        <div
          v-if="status?.hint && captureEnabled"
          class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800"
        >
          {{ status.hint }}
        </div>

        <SectionCard v-if="captureEnabled" title="pcap 文件" description="按会话轮转命名，容器重启会生成新文件，不覆盖旧证据。">
          <div v-if="loadingStatus" class="py-6 text-center text-xs text-slate-400">加载中...</div>
          <div v-else-if="!hasFiles" class="rounded-lg border border-dashed border-slate-200 bg-slate-50/70 px-3 py-6 text-center text-xs text-slate-500">
            还没有抓包文件（靶机可能没有流量，或取证未开启）
          </div>
          <div v-else class="overflow-hidden rounded-lg border border-slate-100">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th class="px-3 py-2 font-medium">文件</th>
                  <th class="px-3 py-2 font-medium">大小</th>
                  <th class="px-3 py-2 font-medium">修改时间</th>
                  <th class="px-3 py-2 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="file in files" :key="file.name" class="border-t border-slate-100">
                  <td class="px-3 py-2 font-mono text-[11px] text-slate-800">{{ file.name }}</td>
                  <td class="px-3 py-2 text-slate-600">{{ formatBytes(file.size) }}</td>
                  <td class="px-3 py-2 text-slate-500">{{ file.modified }}</td>
                  <td class="px-3 py-2 text-right">
                    <button
                      class="inline-flex h-7 items-center justify-center rounded-lg border border-slate-200 bg-white px-2.5 text-[11px] font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] disabled:cursor-not-allowed disabled:opacity-55"
                      :disabled="pendingAction === file.name"
                      @click="download(containerId, file.name)"
                    >{{ pendingAction === file.name ? '下载中' : '下载' }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </SectionCard>

        <p v-if="message" class="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2 text-xs text-slate-600">{{ message }}</p>

        <template v-if="parsed">
          <SectionCard title="流量概览" description="只呈现可复核的事实统计，不做任何判定。">
            <div class="grid grid-cols-2 gap-2 md:grid-cols-4">
              <div class="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2">
                <p class="text-[11px] text-slate-500">报文 / 字节</p>
                <p class="mt-0.5 font-mono text-xs text-slate-800">{{ parsed.packets }} / {{ formatBytes(parsed.bytes) }}</p>
              </div>
              <div class="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2">
                <p class="text-[11px] text-slate-500">时间范围</p>
                <p class="mt-0.5 font-mono text-[11px] text-slate-800">{{ parsed.first_seen || '-' }} → {{ parsed.last_seen || '-' }}</p>
              </div>
              <div class="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2">
                <p class="text-[11px] text-slate-500">HTTP 请求</p>
                <p class="mt-0.5 font-mono text-xs text-slate-800">{{ parsed.signals?.total_http_requests ?? 0 }}</p>
              </div>
              <div class="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2">
                <p class="text-[11px] text-slate-500">峰值 / 中位间隔</p>
                <p class="mt-0.5 font-mono text-xs text-slate-800">
                  {{ parsed.signals?.peak_requests_per_minute ?? 0 }} rpm /
                  {{ parsed.signals?.min_median_request_interval_ms ?? '-' }}ms
                </p>
              </div>
            </div>
            <p v-if="parsed.truncated" class="mt-2 text-[11px] text-amber-700">
              解析达到报文上限已被截断，仅代表前 {{ parsed.packets }} 个报文；完整证据请下载 pcap。
            </p>
            <p v-if="parsed.signals?.automation_user_agents?.length" class="mt-2 text-[11px] text-slate-600">
              命中的工具型 User-Agent：{{ parsed.signals.automation_user_agents.join(' | ') }}
            </p>
          </SectionCard>

          <SectionCard v-if="parsed.clients?.length" title="客户端画像">
            <div class="overflow-hidden rounded-lg border border-slate-100">
              <table class="w-full text-left text-xs">
                <thead class="bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th class="px-3 py-2 font-medium">客户端</th>
                    <th class="px-3 py-2 font-medium">请求</th>
                    <th class="px-3 py-2 font-medium">中位间隔</th>
                    <th class="px-3 py-2 font-medium">峰值</th>
                    <th class="px-3 py-2 font-medium">User-Agent</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="client in parsed.clients" :key="client.ip" class="border-t border-slate-100 align-top">
                    <td class="px-3 py-2 font-mono text-[11px] text-slate-800">{{ client.ip }}</td>
                    <td class="px-3 py-2 text-slate-600">{{ client.requests }}</td>
                    <td class="px-3 py-2 text-slate-600">{{ client.median_interval_ms ?? '-' }}ms</td>
                    <td class="px-3 py-2 text-slate-600">{{ client.peak_requests_per_minute ?? '-' }}/min</td>
                    <td class="px-3 py-2 text-[11px] text-slate-600">
                      <span v-if="client.user_agents?.length" class="break-all">{{ client.user_agents.join(' | ') }}</span>
                      <span v-else class="text-slate-400">无</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard v-if="parsed.http_requests?.length" title="请求时间线">
            <div class="max-h-[320px] overflow-y-auto rounded-lg border border-slate-100">
              <table class="w-full text-left text-xs">
                <thead class="sticky top-0 bg-slate-50/95 text-[11px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th class="px-3 py-2 font-medium">时间</th>
                    <th class="px-3 py-2 font-medium">方法</th>
                    <th class="px-3 py-2 font-medium">路径</th>
                    <th class="px-3 py-2 font-medium">User-Agent</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, index) in parsed.http_requests" :key="`${item.time}-${index}`" class="border-t border-slate-100">
                    <td class="whitespace-nowrap px-3 py-1.5 font-mono text-[11px] text-slate-500">{{ item.time }}</td>
                    <td class="px-3 py-1.5 font-mono text-[11px] text-slate-800">{{ item.method }}</td>
                    <td class="max-w-[360px] truncate px-3 py-1.5 font-mono text-[11px] text-slate-800" :title="item.path">{{ item.path }}</td>
                    <td class="max-w-[240px] truncate px-3 py-1.5 text-[11px] text-slate-500" :title="item.user_agent">
                      {{ item.user_agent || '-' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="mt-2 text-[11px] text-slate-500">
              仅展示明文 HTTP 的请求行；HTTPS 只能看到加密字节。
            </p>
          </SectionCard>
        </template>
      </template>
    </div>
  </BaseModal>
</template>
