<script setup>
const props = defineProps({
  visible: { type: Boolean, required: true },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  width: { type: String, default: 'max-w-[640px]' },
  closeText: { type: String, default: '关闭' },
  showClose: { type: Boolean, default: true },
  icon: { type: String, default: '' },  // info | success | error | loading | bolt
  zIndex: { type: String, default: 'z-[9200]' },
  closeOnBackdrop: { type: Boolean, default: false },
});

const emit = defineEmits(['close']);

function onBackdrop() {
  if (!props.closeOnBackdrop) return;
  emit('close');
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 flex items-start justify-center overflow-y-auto bg-black/30 px-3 py-4 backdrop-blur-md sm:items-center sm:p-5"
      :class="zIndex"
      @click.self="onBackdrop"
    >
      <div
        class="flex max-h-[calc(100vh-2rem)] w-full flex-col overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-[0_10px_40px_-16px_rgba(10,12,18,0.2)] sm:max-h-[calc(100vh-2.5rem)]"
        :class="width"
      >
        <div class="flex shrink-0 items-start justify-between gap-3 border-b border-slate-100 px-4 py-4 sm:px-6">
          <div class="flex min-w-0 flex-1 items-center gap-3">
            <div
              v-if="icon"
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              :class="{
                'bg-emerald-50 text-emerald-600': icon === 'success',
                'bg-red-50 text-red-600': icon === 'error',
                'bg-amber-50 text-amber-600': icon === 'warning',
                'bg-slate-100 text-slate-600': icon === 'info' || icon === 'loading' || icon === 'bolt',
              }"
            >
              <svg v-if="icon === 'loading'" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <svg v-else-if="icon === 'success'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              <svg v-else-if="icon === 'error'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <svg v-else-if="icon === 'warning'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <svg v-else-if="icon === 'bolt'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>

            <div class="min-w-0">
              <h3 class="break-words text-base font-semibold text-slate-900">{{ title }}</h3>
              <p v-if="subtitle" class="mt-0.5 break-words text-xs text-slate-500">{{ subtitle }}</p>
            </div>
          </div>

          <button
            v-if="showClose"
            class="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            @click="emit('close')"
          >{{ closeText }}</button>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-6">
          <slot />
        </div>

        <div v-if="$slots.footer" class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-slate-100 bg-white px-4 py-3 sm:px-6">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
