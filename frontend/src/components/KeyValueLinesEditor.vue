<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, default: '' },
  rows: { type: [Number, String], default: 6 },
  placeholder: { type: String, default: '' },
  helperText: { type: String, default: '' },
  validateText: { type: String, default: '检测格式' },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'validate']);

const resolvedRows = computed(() => {
  const value = Number(props.rows);
  return Number.isFinite(value) && value > 0 ? value : 6;
});

function onInput(event) {
  emit('update:modelValue', event.target.value);
}

function onValidate() {
  emit('validate', String(props.modelValue || ''));
}
</script>

<template>
  <div>
    <div class="mb-2 flex flex-wrap items-center justify-between gap-3" v-if="$slots.header || validateText">
      <div v-if="$slots.header">
        <slot name="header" />
      </div>
      <button
        v-if="validateText"
        type="button"
        class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="disabled"
        @click="onValidate"
      >
        {{ validateText }}
      </button>
    </div>

    <textarea
      :id="id || undefined"
      :rows="resolvedRows"
      :value="modelValue"
      :disabled="disabled"
      class="w-full resize-y rounded-[14px] border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
      :placeholder="placeholder"
      @input="onInput"
    ></textarea>

    <p v-if="helperText" class="mt-2 text-xs leading-relaxed text-slate-500">{{ helperText }}</p>
  </div>
</template>

