<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import { LOG_TAIL_OPTIONS, useContainerLogs } from '../../composables/useContainerLogs';

const props = defineProps({
  visible: { type: Boolean, default: false },
  container: { type: Object, default: null },
});

const emit = defineEmits(['close']);

const {
  lines,
  lineCount,
  truncated,
  loading,
  error,
  tail,
  withTimestamps,
  isEmpty,
  following,
  followError,
  followNotice,
  setScrollHandler,
  reset,
  refresh,
  startFollow,
  stopFollow,
} = useContainerLogs();

const logContainer = ref(null);

function scrollToBottom() {
  nextTick(() => {
    const el = logContainer.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

setScrollHandler(scrollToBottom);

const containerId = computed(() => props.container?.id || '');
const subtitle = computed(() => {
  const name = props.container?.name || containerId.value;
  return name ? `容器 ${name}` : '选择一个容器查看日志';
});

watch(
  () => props.visible,
  (open) => {
    if (!open) {
      stopFollow();
      return;
    }
    if (!containerId.value) return;
    reset();
    void refresh(containerId.value).then(scrollToBottom);
  },
);

function onToggleFollow() {
  if (following.value) {
    stopFollow();
    return;
  }
  void startFollow(containerId.value);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="容器日志"
    :subtitle="subtitle"
    width="max-w-[1080px]"
    icon="info"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div v-if="!containerId" class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">
        请从容器卡片点击「日志」进入
      </div>

      <template v-else>
        <SectionCard
          title="stdout + stderr"
          :description="`最近 ${tail} 行${following ? '，正在跟随新输出' : ''}；服务端已解 docker 多路复用帧头`"
        >
          <template #header>
            <div class="flex flex-wrap items-center gap-2">
              <label class="text-xs text-slate-500" for="logTailSelect">行数</label>
              <select
                id="logTailSelect"
                v-model.number="tail"
                :disabled="following"
                class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              >
                <option v-for="option in LOG_TAIL_OPTIONS" :key="option" :value="option">{{ option }}</option>
              </select>

              <label class="inline-flex items-center gap-1.5 text-xs text-slate-500">
                <input v-model="withTimestamps" type="checkbox" class="h-3.5 w-3.5 rounded border-slate-300" />
                时间戳
              </label>

              <span class="flex-1"></span>

              <button
                class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
                :disabled="loading"
                @click="refresh(containerId)"
              >
                {{ loading ? '读取中...' : '刷新' }}
              </button>
              <button
                class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] px-3 text-xs font-medium transition active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
                :class="following
                  ? 'border border-slate-200 bg-white text-slate-900 hover:border-[#d2d5dc] hover:bg-[#fbfbfc]'
                  : 'border border-slate-900 bg-slate-900 text-white hover:border-slate-700 hover:bg-slate-700'"
                @click="onToggleFollow"
              >
                {{ following ? '停止跟随' : '跟随' }}
              </button>
            </div>
          </template>

          <div v-if="following" class="mb-2 flex flex-wrap items-center gap-2">
            <span
              class="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700"
            >跟随中</span>
          </div>

          <p v-if="truncated" class="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            输出超过单次上限，已截断为尾部内容；调小行数或到宿主机查看完整日志。
          </p>

          <p v-if="error" class="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {{ error }}
          </p>

          <p v-else-if="followError" class="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            跟随中断：{{ followError }}
          </p>

          <p v-else-if="followNotice" class="mb-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            {{ followNotice }}
          </p>

          <div
            ref="logContainer"
            class="build-log-container max-h-[56vh] min-h-[220px] overflow-y-auto rounded-[14px] border border-slate-200 bg-slate-950 p-4 font-mono text-[13px] leading-relaxed text-slate-300"
          >
            <div v-if="loading && lines.length === 0" class="text-slate-500">正在读取日志...</div>
            <div v-else-if="lines.length === 0" class="text-slate-500">暂无日志输出</div>
            <template v-else>
              <div
                v-for="(line, idx) in lines"
                :key="idx"
                class="build-log-line whitespace-pre-wrap break-all"
              >{{ line }}</div>
            </template>
          </div>

          <p v-if="!loading && lineCount" class="mt-2 text-xs text-slate-500">
            共 {{ lineCount }} 行<span v-if="following">（跟随上限 5 分钟 / 5000 行）</span>
          </p>
        </SectionCard>
      </template>
    </div>
  </BaseModal>
</template>
