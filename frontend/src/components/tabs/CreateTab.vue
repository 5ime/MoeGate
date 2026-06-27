<script setup>
import { inject } from 'vue';
import BuildProgressModal from '../BuildProgressModal.vue';
import CreateContainerForm from '../container/CreateContainerForm.vue';
import CreatePreferencesModal from '../container/CreatePreferencesModal.vue';
import { useCreateTab } from '../../composables/useCreateTab';

const switchTab = inject('switchTab', null);

const {
  buildPayload,
  closePreferencesModal,
  composeManagedSubnetPool,
  composeManagedSubnetPrefix,
  form,
  imageSourceInput,
  limitsLoading,
  limitsSaving,
  maxContainersInput,
  maxRenewTimesInput,
  onBuildClose,
  onBuildSuccess,
  openPreferencesModal,
  resetForm,
  savePreferences,
  showBuildModal,
  showPreferencesModal,
  submit,
  validateEnvFormat,
} = useCreateTab();
</script>

<template>
  <section class="space-y-5">
    <div class="rounded-xl border border-slate-200 p-5 md:p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[12px] font-medium uppercase tracking-wider text-slate-500">创建向导</p>
          <h2 class="mt-1 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">创建新容器</h2>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-8 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3 text-xs font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55"
            @click="switchTab?.('containers')"
          >
            查看容器
          </button>
        </div>
      </div>
    </div>

    <CreateContainerForm
      :form="form"
      :limits-loading="limitsLoading"
      :limits-saving="limitsSaving"
      :validate-env-format="validateEnvFormat"
      @open-preferences="openPreferencesModal"
      @reset="resetForm"
      @submit="submit"
    />

    <BuildProgressModal
      :visible="showBuildModal"
      :payload="buildPayload"
      @success="onBuildSuccess"
      @close="onBuildClose"
    />

    <CreatePreferencesModal
      :visible="showPreferencesModal"
      :limits-loading="limitsLoading"
      :limits-saving="limitsSaving"
      v-model:image-source="imageSourceInput"
      v-model:compose-managed-subnet-pool="composeManagedSubnetPool"
      v-model:compose-managed-subnet-prefix="composeManagedSubnetPrefix"
      v-model:max-containers-input="maxContainersInput"
      v-model:max-renew-times-input="maxRenewTimesInput"
      @close="closePreferencesModal"
      @save="savePreferences"
    />
  </section>
</template>
