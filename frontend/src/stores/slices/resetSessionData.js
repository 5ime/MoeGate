import { resetAuthSlice } from './authSlice';
import { resetContainersSlice } from './containersSlice';
import { resetFrpSlice } from './frpSlice';
import { resetImagesSlice } from './imagesSlice';
import { resetNetworksSlice } from './networksSlice';
import { resetSystemSlice } from './systemSlice';
import { resetUiSlice } from './uiSlice';

/** 登出时清空各域缓存数据（保留 settings 与 activeTab）。 */
export function resetSessionData(store) {
  resetAuthSlice(store);
  resetContainersSlice(store);
  resetImagesSlice(store);
  resetNetworksSlice(store);
  resetSystemSlice(store);
  resetFrpSlice(store);
  resetUiSlice(store);
}
