<script setup>
const props = defineProps({
  form: { type: Object, required: true },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-5 md:p-6">
    <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
      <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path d="M13 7H7v6h6V7z"/><path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clip-rule="evenodd"/></svg>
      <span>资源限制</span>
      <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
    </div>
    <div class="grid grid-cols-3 gap-3 max-lg:grid-cols-1">
      <div>
        <label for="memoryLimit" class="mb-2 block text-xs font-medium text-slate-600">内存</label>
        <input id="memoryLimit" v-model="props.form.memory_limit" type="text" placeholder="512m" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>
      <div>
        <label for="cpuLimit" class="mb-2 block text-xs font-medium text-slate-600">CPU (核)</label>
        <input id="cpuLimit" v-model="props.form.cpu_limit" type="number" step="0.1" min="0" placeholder="1.0" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>
      <div>
        <label for="cpuShares" class="mb-2 block text-xs font-medium text-slate-600">Shares</label>
        <input id="cpuShares" v-model="props.form.cpu_shares" type="number" min="0" placeholder="1024" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>
    </div>
  </div>
</template>
