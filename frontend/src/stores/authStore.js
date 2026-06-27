import { ref } from 'vue';
import { defineStore } from 'pinia';
import {
  checkSession,
  loginWithCookie,
  logoutSession,
} from '../api/client';
import { useContainersStore } from './containersStore';
import { useFrpStore } from './frpStore';
import { useImagesStore } from './imagesStore';
import { useNetworksStore } from './networksStore';
import { useSystemStore } from './systemStore';
import { useUiStore } from './uiStore';

export const useAuthStore = defineStore('auth', () => {
  const sessionAuthenticated = ref(false);

  function reset() {
    sessionAuthenticated.value = false;
  }

  function isLoggedIn() {
    return sessionAuthenticated.value;
  }

  async function restoreSession() {
    try {
      const session = await checkSession();
      sessionAuthenticated.value = !!session?.data?.authenticated;
      return sessionAuthenticated.value;
    } catch {
      sessionAuthenticated.value = false;
      return false;
    }
  }

  async function login(apiKey) {
    const trimmed = String(apiKey || '').trim();
    if (!trimmed) {
      throw new Error('请输入 API Key');
    }

    await loginWithCookie(trimmed);
    sessionAuthenticated.value = true;
  }

  /** 登出时清空各域缓存数据（保留 settings 与 activeTab）。 */
  function resetSessionData() {
    reset();
    useContainersStore().reset();
    useImagesStore().reset();
    useNetworksStore().reset();
    useSystemStore().reset();
    useFrpStore().reset();
    useUiStore().reset();
  }

  async function logout() {
    try {
      await logoutSession();
    } catch {
      // ignore network errors during logout
    }
    resetSessionData();
    useUiStore().closeDetailPanel();
  }

  return {
    sessionAuthenticated,
    reset,
    isLoggedIn,
    restoreSession,
    login,
    logout,
  };
});
