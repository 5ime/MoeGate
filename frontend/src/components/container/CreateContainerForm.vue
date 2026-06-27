<script setup>
import CreateBasicOptionsCard from './CreateBasicOptionsCard.vue';
import CreateDeploymentSourceCard from './CreateDeploymentSourceCard.vue';
import CreateEnvCard from './CreateEnvCard.vue';
import CreateFormActions from './CreateFormActions.vue';
import CreatePortResourceCard from './CreatePortResourceCard.vue';
import CreateResourceLimitCard from './CreateResourceLimitCard.vue';

const props = defineProps({
  form: { type: Object, required: true },
  limitsLoading: { type: Boolean, default: false },
  limitsSaving: { type: Boolean, default: false },
  validateEnvFormat: { type: Function, required: true },
});

const emit = defineEmits(['open-preferences', 'reset', 'submit']);
</script>

<template>
  <form id="createContainerForm" @submit.prevent="$emit('submit')">
    <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">

      <div class="space-y-5">

        <CreateDeploymentSourceCard :form="form" />

        <CreateBasicOptionsCard :form="form" />
      </div>

      <div class="space-y-5">

        <CreatePortResourceCard :form="form" />

        <CreateResourceLimitCard :form="form" />

        <CreateEnvCard :form="form" :validate-env-format="validateEnvFormat" />
      </div>
    </div>

    <CreateFormActions
      :form="form"
      :limits-loading="limitsLoading"
      :limits-saving="limitsSaving"
      @open-preferences="$emit('open-preferences')"
      @reset="$emit('reset')"
    />
  </form>
</template>