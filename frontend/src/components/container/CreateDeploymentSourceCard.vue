<script setup>
const props = defineProps({
  form: { type: Object, required: true },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-5 md:p-6">
    <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
      <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.532a2.25 2.25 0 011.591.659l4.418 4.418A2.25 2.25 0 0117.25 8.59V17.75A2.25 2.25 0 0115 20H5.25A2.25 2.25 0 013 17.75V4.25z" clip-rule="evenodd"/></svg>
      <span>部署来源</span>
    </div>

    <div class="relative flex gap-0 rounded-xl border border-slate-200 bg-slate-50 p-1">
      <div
        class="pointer-events-none absolute bottom-1 left-1 top-1 w-[calc(50%-4px)] rounded-lg border border-slate-200 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-transform duration-200"
        :style="{ transform: props.form.source === 'image' ? 'translateX(100%)' : 'translateX(0%)' }"
        aria-hidden="true"
      ></div>
      <button
        type="button"
        class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
        :class="{ 'text-slate-900': props.form.source === 'path' }"
        @click="props.form.source = 'path'"
      >
        路径
      </button>
      <button
        type="button"
        class="relative z-10 flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-transparent py-2 text-sm font-medium text-slate-500 transition hover:text-slate-700"
        :class="{ 'text-slate-900': props.form.source === 'image' }"
        @click="props.form.source = 'image'"
      >
        镜像
      </button>
    </div>

    <div v-if="props.form.source === 'path'" class="mt-3">
      <label for="containerPath" class="mb-2 block text-sm font-medium text-slate-900">Dockerfile / Compose 路径</label>
      <input id="containerPath" v-model="props.form.path" type="text" required placeholder="/path/to/dockerfile_or_compose" class="w-full rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100" />
      <p class="mt-1.5 text-xs leading-relaxed text-slate-500">支持含 Dockerfile 或 docker-compose.yml 的目录路径</p>
    </div>

    <div v-else class="mt-3">
      <label for="containerImage" class="mb-2 block text-sm font-medium text-slate-900">镜像名称</label>
      <input id="containerImage" v-model="props.form.image" type="text" required placeholder="nginx:latest" class="w-full rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 transition focus:border-slate-400 focus:outline-none focus:ring-4 focus:ring-slate-100" />
      <p class="mt-1.5 text-xs leading-relaxed text-slate-500">镜像将直接拉取运行，跳过构建流程</p>
    </div>
  </div>
</template>
