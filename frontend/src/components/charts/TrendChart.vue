<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import uPlot from 'uplot';

const props = defineProps({
  chartId: { type: String, required: true },
  metaId: { type: String, required: true },
  cardClass: { type: String, default: 'rounded-[16px] border border-slate-200 bg-white p-4' },
  title: { type: String, required: true },
  color: { type: String, default: '#2563eb' },
  values: { type: Array, required: true },
  timestamps: { type: Array, required: true },
  threshold: { type: Number, default: 80 },
});

const rootEl = ref(null);
const tooltip = ref({ show: false, text: '', x: 0, y: 0 });
let chart = null;
let resizeObserver = null;
let initRaf = null;

function parsePx(value) {
  const n = Number.parseFloat(value || '0');
  return Number.isFinite(n) ? n : 0;
}

function getPlotSize() {
  if (!rootEl.value) return { width: 0, height: 0 };
  const styles = window.getComputedStyle(rootEl.value);

  const horizontalPadding = parsePx(styles.paddingLeft) + parsePx(styles.paddingRight);
  const horizontalBorder = parsePx(styles.borderLeftWidth) + parsePx(styles.borderRightWidth);
  const verticalPadding = parsePx(styles.paddingTop) + parsePx(styles.paddingBottom);
  const verticalBorder = parsePx(styles.borderTopWidth) + parsePx(styles.borderBottomWidth);

  const width = Math.max(0, Math.floor(rootEl.value.clientWidth - horizontalPadding - horizontalBorder));
  const height = Math.max(0, Math.floor(rootEl.value.clientHeight - verticalPadding - verticalBorder));
  return { width, height };
}

const normalized = computed(() => {
  const vals = (props.values || []).map((v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  });
  const x = vals.map((_v, idx) => idx + 1);
  const line = vals.map(() => props.threshold);
  return { x, vals, line };
});

const baseMeta = computed(() => (props.values.length ? `样本 ${props.values.length} 条` : '暂无采样数据'));

function formatTimestamp(raw) {
  if (raw === null || raw === undefined || raw === '') return '';

  if (typeof raw === 'number' && Number.isFinite(raw)) {
    const ms = raw > 1e12 ? raw : raw * 1000;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? String(raw) : d.toLocaleTimeString('zh-CN', { hour12: false });
  }

  if (typeof raw === 'string') {
    const asNumber = Number(raw);
    if (Number.isFinite(asNumber) && raw.trim() !== '') {
      const ms = asNumber > 1e12 ? asNumber : asNumber * 1000;
      const d = new Date(ms);
      if (!Number.isNaN(d.getTime())) return d.toLocaleTimeString('zh-CN', { hour12: false });
    }
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? raw : d.toLocaleTimeString('zh-CN', { hour12: false });
  }

  return String(raw);
}

function hideTooltip() {
  tooltip.value = { show: false, text: '', x: 0, y: 0 };
}

function updateTooltip(u, idx) {
  if (!Number.isInteger(idx) || idx < 0 || idx >= normalized.value.vals.length) {
    hideTooltip();
    return;
  }

  const rawX = Number(u?.cursor?.left);
  const rawY = Number(u?.cursor?.top);
  if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) {
    hideTooltip();
    return;
  }

  const value = normalized.value.vals[idx];
  const rawTs = props.timestamps?.[idx];
  const tsText = formatTimestamp(rawTs);
  const text = tsText ? `${tsText} | ${value.toFixed(1)}%` : `第 ${idx + 1} 点 | ${value.toFixed(1)}%`;

  const width = rootEl.value?.clientWidth || 0;
  const height = rootEl.value?.clientHeight || 0;
  const x = Math.max(16, Math.min(rawX, Math.max(16, width - 16)));
  const y = Math.max(16, Math.min(rawY, Math.max(16, height - 16)));

  tooltip.value = { show: true, text, x, y };
}

function buildChart() {
  if (!rootEl.value) return;

  const { width, height } = getPlotSize();
  // If the tab is currently hidden (v-show), delay init until width becomes available.
  if (width <= 0 || height <= 0) {
    if (initRaf) window.cancelAnimationFrame(initRaf);
    initRaf = window.requestAnimationFrame(() => {
      initRaf = null;
      buildChart();
    });
    return;
  }

  if (chart) {
    chart.destroy();
    chart = null;
  }

  chart = new uPlot(
    {
      width,
      height,
      padding: [10, 8, 8, 8],
      legend: { show: false },
      scales: {
        x: { time: false },
        y: { range: [0, 100] },
      },
      hooks: {
        setCursor: [
          (u) => {
            updateTooltip(u, u.cursor?.idx);
          },
        ],
      },
      axes: [
        { show: false },
        {
          stroke: '#94a3b8',
          grid: { stroke: '#e2e8f0', width: 1 },
          values: (_u, vals) => vals.map((v) => `${v}%`),
          size: 44,
        },
      ],
      series: [
        {},
        {
          stroke: props.color,
          width: 2,
          fill: `${props.color}22`,
        },
        {
          stroke: '#ef4444',
          width: 1.2,
          dash: [6, 4],
          points: { show: false },
        },
      ],
    },
    [normalized.value.x, normalized.value.vals, normalized.value.line],
    rootEl.value
  );
}

function refreshData() {
  if (!chart) {
    buildChart();
    return;
  }
  chart.setData([normalized.value.x, normalized.value.vals, normalized.value.line]);
  updateTooltip(chart, chart.cursor?.idx);
}

function handleResize() {
  if (!rootEl.value) return;
  const { width, height } = getPlotSize();
  if (width <= 0 || height <= 0) return;

  if (!chart) {
    buildChart();
    return;
  }

  chart.setSize({ width, height });
}

onMounted(() => {
  buildChart();
  resizeObserver = new ResizeObserver(() => {
    handleResize();
  });
  if (rootEl.value) resizeObserver.observe(rootEl.value);
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (initRaf) {
    window.cancelAnimationFrame(initRaf);
    initRaf = null;
  }
  if (chart) chart.destroy();
  hideTooltip();
});

watch(() => [props.values, props.timestamps, props.threshold], refreshData, { deep: true });
</script>

<template>
  <div :class="cardClass">
    <div class="mb-2.5 flex items-center justify-between">
      <div class="text-sm font-semibold text-slate-600">{{ title }}</div>
      <span class="rounded-full border border-slate-200 bg-[#fafbfd] px-2 py-0.5 text-[11px] text-slate-500">阈值 {{ threshold }}%</span>
    </div>
    <div class="relative">
      <div
        :id="chartId"
        ref="rootEl"
        class="relative h-[200px] min-h-[200px] overflow-hidden rounded-[12px] border border-slate-200 bg-[#fcfcfd] p-2.5"
      ></div>
      <div
        v-if="tooltip.show"
        class="pointer-events-none absolute z-10 whitespace-nowrap rounded-[9px] border border-[#d8dbe1] bg-white/95 px-2.5 py-1 text-[11px] font-medium text-slate-900 shadow-sm"
        :style="{
          left: `${tooltip.x}px`,
          top: `${tooltip.y}px`,
          transform: 'translate(-50%, calc(-100% - 10px))',
        }"
      >
        {{ tooltip.text }}
      </div>
    </div>
    <div :id="metaId" class="mt-2.5 min-h-5 text-xs text-slate-500">{{ baseMeta }}</div>
  </div>
</template>
