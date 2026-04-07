<script setup>
const props = defineProps({
  cancelText: { type: String, default: '取消' },
  submitText: { type: String, default: '保存' },
  submittingText: { type: String, default: '保存中...' },
  disabled: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
});

const emit = defineEmits(['cancel', 'submit']);
</script>

<template>
  <div class="flex items-center justify-end gap-2">
    <button
      type="button"
      class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
      :disabled="disabled || submitting"
      @click="emit('cancel')"
    >{{ cancelText }}</button>
    <button
      type="button"
      class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 text-sm font-medium text-white transition hover:border-slate-700 hover:bg-slate-700 active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
      :disabled="disabled || submitting"
      @click="emit('submit')"
    >{{ submitting ? submittingText : submitText }}</button>
  </div>
</template>

