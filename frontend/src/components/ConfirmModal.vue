<script setup>
import BaseModal from './BaseModal.vue';

const props = defineProps({
  visible: { type: Boolean, required: true },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(['confirm', 'cancel']);
</script>

<template>
  <BaseModal
    :visible="visible"
    :title="title"
    :icon="danger ? 'warning' : 'bolt'"
    width="max-w-[440px]"
    :show-close="false"
    z-index="z-[9300]"
    @close="emit('cancel')"
  >
    <p class="text-sm leading-relaxed text-slate-600">{{ message }}</p>

    <template #footer>
      <button
        class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="loading"
        @click="emit('cancel')"
      >{{ cancelText }}</button>
      <button
        class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border px-3 text-xs font-medium text-white transition active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
        :class="danger ? 'border-[#922f2f] bg-[#922f2f] hover:border-[#7b2929] hover:bg-[#7b2929]' : 'border-slate-900 bg-slate-900 hover:border-slate-700 hover:bg-slate-700'"
        :disabled="loading"
        @click="emit('confirm')"
      >
        {{ loading ? '处理中...' : confirmText }}
      </button>
    </template>
  </BaseModal>
</template>
