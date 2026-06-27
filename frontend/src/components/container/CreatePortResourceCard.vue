<script setup>
const props = defineProps({
  form: { type: Object, required: true },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-5 md:p-6">
    <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
      <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clip-rule="evenodd"/></svg>
      <span>端口分配</span>
    </div>
    <div class="relative mb-3 flex gap-0 rounded-xl border border-slate-200 bg-slate-50 p-1">
      <div
        class="pointer-events-none absolute bottom-1 left-1 top-1 w-[calc(50%-4px)] rounded-lg border border-slate-200 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-transform duration-200"
        :style="{ transform: props.form.port_mode === 'fixed' ? 'translateX(100%)' : 'translateX(0%)' }"
        aria-hidden="true"
      ></div>
      <button
        type="button"
        class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
        :class="{ 'text-slate-900': props.form.port_mode === 'random' }"
        @click="props.form.port_mode = 'random'"
      >
        随机分配
      </button>
      <button
        type="button"
        class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
        :class="{ 'text-slate-900': props.form.port_mode === 'fixed' }"
        @click="props.form.port_mode = 'fixed'"
      >
        固定映射
      </button>
    </div>

    <div v-if="props.form.port_mode === 'fixed'">
      <label for="portMappings" class="mb-2 block text-xs font-medium text-slate-600">固定端口映射</label>
      <input id="portMappings" v-model="props.form.port_mappings_text" type="text" placeholder="8080:80,8443:443" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      <p class="mt-2 text-xs leading-relaxed text-slate-500">格式: host:container，多个用逗号分隔，例如 8080:80,8443:443</p>
    </div>

    <div v-else class="grid grid-cols-2 gap-4 max-md:grid-cols-1">
      <div>
        <label for="minPort" class="mb-2 block text-xs font-medium text-slate-600">最小端口</label>
        <input id="minPort" v-model="props.form.min_port" type="number" min="1024" max="65535" placeholder="20000" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>
      <div>
        <label for="maxPort" class="mb-2 block text-xs font-medium text-slate-600">最大端口</label>
        <input id="maxPort" v-model="props.form.max_port" type="number" min="1024" max="65535" placeholder="30000" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>
    </div>
    <p v-if="props.form.port_mode === 'random'" class="mt-2 text-xs leading-relaxed text-slate-500">系统会在给定范围内自动选择可用宿主机端口</p>
  </div>
</template>
