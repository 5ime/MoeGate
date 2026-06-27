<script setup>
const props = defineProps({
  form: { type: Object, required: true },
  limitsLoading: { type: Boolean, default: false },
  limitsSaving: { type: Boolean, default: false },
});

const emit = defineEmits(['open-preferences', 'reset']);
</script>

<template>
  <div class="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3.5 max-md:flex-col max-md:items-stretch max-md:text-center">
    <div class="flex items-center gap-2 max-md:justify-center">
      <span v-if="props.form.port_mode === 'fixed' && props.form.port_mappings_text" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">端口映射: {{ props.form.port_mappings_text }}</span>
      <span v-else-if="props.form.port_mode === 'random' && (props.form.min_port || props.form.max_port)" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">端口范围: {{ props.form.min_port || '默认最小值' }} - {{ props.form.max_port || '默认最大值' }}</span>
      <span v-if="props.form.source === 'path' && props.form.path" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">路径: {{ props.form.path }}</span>
      <span v-else-if="props.form.source === 'image' && props.form.image" class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">镜像: {{ props.form.image }}</span>
      <span v-else class="text-xs text-slate-400">请先选择部署来源</span>
    </div>
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="props.limitsLoading || props.limitsSaving"
        @click="emit('open-preferences')"
      >
        偏好设置
      </button>
      <button type="button" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="emit('reset')">重置</button>
      <button type="submit" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55">
        创建容器
      </button>
    </div>
  </div>
</template>
