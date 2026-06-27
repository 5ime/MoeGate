import { reactive } from 'vue';
import { createAuthSlice } from './slices/authSlice';
import { createContainersSlice } from './slices/containersSlice';
import { createFrpSlice } from './slices/frpSlice';
import { createImagesSlice } from './slices/imagesSlice';
import { createNetworksSlice } from './slices/networksSlice';
import { createSettingsSlice } from './slices/settingsSlice';
import { createSystemSlice } from './slices/systemSlice';
import { createUiSlice } from './slices/uiSlice';

export const store = reactive({
  ...createAuthSlice(),
  ...createUiSlice(),
  ...createContainersSlice(),
  ...createImagesSlice(),
  ...createNetworksSlice(),
  ...createSystemSlice(),
  ...createFrpSlice(),
  ...createSettingsSlice(),
});
