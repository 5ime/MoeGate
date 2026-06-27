<script setup>
import { storeToRefs } from 'pinia';
import { useNetworksStore } from '../../stores/networksStore';

const { networks } = storeToRefs(useNetworksStore());

const props = defineProps({
  form: { type: Object, required: true },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-5 md:p-6">
    <div class="mb-4 flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
      <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/></svg>
      <span>基础参数</span>
      <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <label for="containerUid" class="mb-2 block text-xs font-medium text-slate-600">用户标识 (UID)</label>
        <input id="containerUid" v-model="props.form.uid" type="text" placeholder="可选" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:outline-none" />
        <p class="mt-2 text-xs leading-relaxed text-slate-500">留空则自动生成 UUID</p>
      </div>

      <div>
        <label for="maxTime" class="mb-2 block text-xs font-medium text-slate-600">存活时间 (秒)</label>
        <input id="maxTime" v-model="props.form.max_time" type="number" placeholder="3600" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>

      <div>
        <label for="containerCommand" class="mb-2 block text-xs font-medium text-slate-600">启动命令</label>
        <input id="containerCommand" v-model="props.form.command" type="text" placeholder="可选" class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400" />
      </div>

      <div>
        <label for="containerTag" class="mb-2 block text-xs font-medium text-slate-600">构建标签</label>
        <div class="relative">
          <input
            id="containerTag"
            v-model="props.form.tag"
            :disabled="props.form.source === 'image'"
            type="text"
            :placeholder="props.form.source === 'image' ? '镜像模式下不可用' : '可选'"
            class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
          />
          <div
            v-if="props.form.source === 'image'"
            class="absolute inset-0 flex items-center justify-center rounded-lg bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
          >
            镜像模式下不可用
          </div>
        </div>
      </div>

      <div class="md:col-span-2">
        <div class="mb-2 flex items-center justify-between gap-2">
          <label for="containerNetworkSelect" class="block text-xs font-medium text-slate-600">网络</label>
        </div>

        <div class="relative">
          <select
            id="containerNetworkSelect"
            v-model="props.form.network"
            class="w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 pr-10 text-sm text-slate-900 outline-none transition focus:border-slate-400"
          >
            <option value="">默认 (bridge)</option>
            <option v-for="item in (networks.items || [])" :key="item.id || item.name" :value="item.name">{{ item.name }}</option>
          </select>
          <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500">
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z" clip-rule="evenodd" /></svg>
          </div>
        </div>

        <p class="mt-2 text-xs leading-relaxed text-slate-500">{{ props.form.source === 'image' ? '填写后，容器会加入所选 Docker network；留空则使用默认 bridge。' : '识别为 Dockerfile 时加入所选网络；识别为 Compose 时忽略此项，由 Compose 网络自动管理。' }}</p>
      </div>
    </div>
  </div>
</template>
