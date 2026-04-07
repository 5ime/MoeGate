<script setup>
const props = defineProps({
  search: { type: String, default: '' },
  select: { type: String, default: '' },
  searchId: { type: String, default: '' },
  selectId: { type: String, default: '' },
  searchPlaceholder: { type: String, default: '搜索...' },
  selectMinWidthClass: { type: String, default: 'min-w-[120px]' },
  showSelect: { type: Boolean, default: true },
  options: { type: Array, default: () => [] }, // [{ value, label }]
});

const emit = defineEmits(['update:search', 'update:select']);

function onSearchInput(event) {
  emit('update:search', event.target.value);
}

function onSelectChange(event) {
  emit('update:select', event.target.value);
}
</script>

<template>
  <div class="rounded-xl border border-slate-200 p-4 md:p-5">
    <div class="flex items-center gap-3 max-md:flex-col max-md:items-stretch">
      <input
        :id="searchId || undefined"
        :value="search"
        type="text"
        :placeholder="searchPlaceholder"
        class="min-w-[240px] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-4 focus:ring-slate-100 max-md:min-w-0 max-md:w-full"
        @input="onSearchInput"
      />

      <div v-if="showSelect" class="relative" :class="[selectMinWidthClass, 'max-md:min-w-0 max-md:w-full']">
        <select
          :id="selectId || undefined"
          :value="select"
          class="h-[38px] w-full appearance-none rounded-lg border border-slate-200 bg-white pl-3 pr-9 text-sm font-medium text-slate-800 transition hover:border-slate-300 focus:border-slate-500 focus:outline-none focus:ring-4 focus:ring-slate-100"
          @change="onSelectChange"
        >
          <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <svg class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      <slot name="tail" />
    </div>
  </div>
</template>

