<script setup>
import KeyValueLinesEditor from '../KeyValueLinesEditor.vue';

const props = defineProps({
  form: { type: Object, required: true },
  validateEnvFormat: { type: Function, required: true },
});
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-5 md:p-6">
    <div class="mb-2 flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <svg class="h-[18px] w-[18px] flex-shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm7 10.5a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10z" clip-rule="evenodd"/></svg>
        <span class="text-sm font-semibold tracking-tight text-slate-900">环境变量</span>
        <span class="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">可选</span>
      </div>
    </div>
    <div class="mt-2">
      <KeyValueLinesEditor
        v-model="props.form.envText"
        :rows="3"
        placeholder="例如&#10;DEBUG=true&#10;NODE_ENV=production"
        @validate="props.validateEnvFormat"
      >
        <template #header>
          <div>
            <p class="mt-1 text-xs text-slate-500">每行一个环境变量，格式 key=value（也支持 key: value）。</p>
          </div>
        </template>
      </KeyValueLinesEditor>
    </div>
  </div>
</template>
