<script setup>
import LoginOverlay from './components/auth/LoginOverlay.vue';
import ConfirmModal from './components/ConfirmModal.vue';
import WebUiSettingsModal from './components/layout/WebUiSettingsModal.vue';
import ImageSourcePreferencesModal from './components/system/ImageSourcePreferencesModal.vue';
import NetworkingPreferencesModal from './components/system/NetworkingPreferencesModal.vue';
import SystemPreferencesModal from './components/system/SystemPreferencesModal.vue';
import { useAppShell } from './composables/useAppShell';
import { storeToRefs } from 'pinia';
import { useSystemStore } from './stores/systemStore';

const systemStore = useSystemStore();
const { systemStatus } = storeToRefs(systemStore);

const {
  currentYear,
  tabs,
  activeTab,
  activeTabKey,
  message,
  messageType,
  loggedIn,
  tabNavEl,
  tabIndicatorStyle,
  setTabEl,
  switchTab,
  activeTabComponent,
  activeTabProps,
  initialLoading,
  loginOverlayRef,
  authApiKey,
  authApiBase,
  authApiKeyVisible,
  loginPending,
  loginError,
  authStorageHint,
  confirmModal,
  onLogin,
  onApiKeyInput,
  onCancelConfirm,
  onConfirm,
  apiBaseDisplay,
  pollDisplay,
  openSettings,
  onLogout,
  showSettings,
  settingsApiBase,
  settingsPollSec,
  closeSettings,
  saveSettings,
  showImageSourcePreferences,
  imageSourcePreferencesSaving,
  imageSourceInput,
  closeImageSourcePreferences,
  saveImageSourcePreferences,
  showNetworkingPreferences,
  networkingPreferencesSaving,
  composeManagedSubnetPool,
  composeManagedSubnetPrefix,
  closeNetworkingPreferences,
  saveNetworkingPreferences,
  showSystemPreferences,
  systemPreferencesSaving,
  systemTestSending,
  webhookUrl,
  webhookUrlSet,
  webhookUrlMasked,
  webhookTimeout,
  webhookUrlTouched,
  closeSystemPreferences,
  saveSystemPreferences,
  sendSystemWebhookTest,
} = useAppShell();
</script>

<template>
  <div class="relative min-h-screen px-4 py-6 md:px-6 md:py-8">
    <div class="pointer-events-none fixed inset-x-[-20%] top-[-30%] z-0 h-[380px] bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.75),rgba(255,255,255,0))]"></div>
    <div v-if="initialLoading" class="fixed inset-0 z-[9500] flex items-center justify-center bg-[radial-gradient(circle_at_50%_42%,rgba(255,255,255,0.18),rgba(255,255,255,0)_48%),linear-gradient(165deg,rgba(12,13,17,0.44),rgba(17,18,20,0.35))] backdrop-blur-[8px] saturate-[108%]" role="status" aria-live="polite" aria-label="正在加载">
      <div class="text-center">
        <div class="relative mx-auto h-[54px] w-[54px] max-md:h-[46px] max-md:w-[46px]" aria-hidden="true">
          <span class="absolute inset-0 rounded-full border-[1.5px] border-white/80 animate-[loadingRingSpin_1.45s_cubic-bezier(0.65,0,0.35,1)_infinite]"></span>
          <span class="absolute inset-[8px] rounded-full border-[1.2px] border-white/80 opacity-60 animate-[loadingRingSpin_1.85s_cubic-bezier(0.65,0,0.35,1)_infinite] [animation-direction:reverse]"></span>
          <span class="absolute left-1/2 top-1/2 h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/95 animate-[loadingCorePulse_1.05s_ease-in-out_infinite] max-md:h-[6px] max-md:w-[6px]"></span>
        </div>
        <p class="mt-[10px] whitespace-nowrap text-[12px] font-medium uppercase tracking-[0.16em] text-white/90 max-md:tracking-[0.12em]">正在准备控制台</p>
      </div>
    </div>

    <LoginOverlay
      ref="loginOverlayRef"
      :visible="!loggedIn"
      v-model:auth-api-key="authApiKey"
      v-model:auth-api-base="authApiBase"
      v-model:auth-api-key-visible="authApiKeyVisible"
      :login-pending="loginPending"
      :login-error="loginError"
      :auth-storage-hint="authStorageHint"
      @submit="onLogin"
      @input-api-key="onApiKeyInput"
    />

    <div class="relative z-[1] mx-auto max-w-[1260px] rounded-[24px] border border-slate-200 bg-white shadow-[0_8px_30px_-12px_rgba(10,12,18,0.15)]">
      <header class="border-b border-slate-100 px-6 py-6 md:px-8">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 class="text-[30px] font-semibold tracking-tight text-slate-900">MoeGate 控制台</h1>
            <p class="mt-1 text-sm text-slate-500">{{ activeTab.desc }}</p>
            <div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">API Base: {{ apiBaseDisplay }}</span>
              <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600">自动刷新: {{ pollDisplay }}</span>
            </div>
          </div>
          <div class="flex w-full flex-wrap items-center gap-3 lg:w-auto">
            <button id="openSettingsBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="openSettings">设置</button>
            <button id="logoutBtn" class="inline-flex h-9 items-center justify-center gap-1.5 rounded-[10px] border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-900 transition hover:border-[#d2d5dc] hover:bg-[#fbfbfc] active:translate-y-[0.5px] disabled:cursor-not-allowed disabled:opacity-55" @click="onLogout">退出登录</button>
          </div>
        </div>
      </header>

      <div class="tab-nav-wrap border-b border-slate-100 px-6 md:px-8">
        <div class="flex flex-wrap items-center justify-between gap-2 py-3">
          <div ref="tabNavEl" class="relative isolate flex gap-2 overflow-x-auto py-0">
          <div
            class="pointer-events-none absolute top-1/2 -z-10 rounded-[12px] border border-slate-300 bg-white shadow-[0_10px_24px_-18px_rgba(12,14,18,0.4)] transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :style="{ opacity: tabIndicatorStyle.opacity, left: tabIndicatorStyle.left, width: tabIndicatorStyle.width, height: tabIndicatorStyle.height, transform: 'translateY(-50%)' }"
            aria-hidden="true"
          ></div>
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :data-tab="tab.key"
            class="relative z-10 inline-flex h-[38px] items-center justify-center rounded-[12px] border border-transparent bg-transparent px-3.5 text-sm font-medium text-slate-500 transition hover:border-slate-200 hover:bg-slate-50 hover:text-slate-900"
            :class="activeTabKey === tab.key ? 'text-slate-900' : ''"
            :ref="(el) => setTabEl(tab.key, el)"
            @click="switchTab(tab.key)"
          >
            {{ tab.label }}
          </button>
          </div>
        </div>
      </div>

      <transition name="tab-page" mode="out-in">
        <div :key="activeTabKey" class="p-6 md:p-9">
          <component :is="activeTabComponent" v-bind="activeTabProps" />
        </div>
      </transition>
    </div>

    <footer class="mx-auto mt-6 max-w-[1260px] px-2 text-[11px] text-slate-500">
      <div class="flex flex-col gap-2 border-t border-slate-100 pt-3 md:flex-row md:items-center md:justify-between">
        <div class="text-center md:text-left">
          <div class="flex flex-wrap items-center justify-center gap-1.5 md:justify-start">
            <span class="font-medium">
              &copy; {{ currentYear }}
              <a
                href="https://github.com/5ime/moegate"
                target="_blank"
                rel="noreferrer"
                class="ml-1 underline-offset-2 hover:underline"
              >
                MoeGate
              </a>
            </span>
            <span>·</span>
            <span class="uppercase tracking-[0.12em] text-[10px]">Console</span>
            <span
              v-if="systemStatus?.app_version"
              class="ml-1 inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600"
            >v{{ systemStatus.app_version }}</span>
          </div>
          <p class="mt-1 text-[10px] text-slate-500/80">
            轻量级 Docker 容器控制台，专注简单、稳定、可视化。
          </p>
        </div>
        <div class="flex flex-col items-center gap-1 text-[10px] md:items-end md:text-right">
          <div class="flex flex-wrap items-center justify-center gap-1.5 md:justify-end">
            <span class="font-medium">开发者</span>
            <span>·</span>
            <a
              href="https://5ime.cn"
              target="_blank"
              rel="noreferrer"
              class="underline-offset-2 hover:underline"
            >
              <span class="font-medium">iami233</span>
            </a>
          </div>
          <p class="text-[10px] text-slate-500/80">
            永远相信美好的事情即将发生
          </p>
        </div>
      </div>
    </footer>

    <WebUiSettingsModal
      :visible="showSettings"
      v-model:api-base="settingsApiBase"
      v-model:poll-sec="settingsPollSec"
      @close="closeSettings"
      @save="saveSettings"
    />

    <ConfirmModal
      :visible="confirmModal.open"
      :title="confirmModal.title"
      :message="confirmModal.message"
      :danger="confirmModal.danger"
      :loading="confirmModal.loading"
      confirm-text="退出登录"
      @confirm="onConfirm"
      @cancel="onCancelConfirm"
    />

    <ImageSourcePreferencesModal
      :visible="showImageSourcePreferences"
      :saving="imageSourcePreferencesSaving"
      v-model:image-source="imageSourceInput"
      @close="closeImageSourcePreferences"
      @save="saveImageSourcePreferences"
    />

    <NetworkingPreferencesModal
      :visible="showNetworkingPreferences"
      :saving="networkingPreferencesSaving"
      v-model:compose-managed-subnet-pool="composeManagedSubnetPool"
      v-model:compose-managed-subnet-prefix="composeManagedSubnetPrefix"
      @close="closeNetworkingPreferences"
      @save="saveNetworkingPreferences"
    />

    <SystemPreferencesModal
      :visible="showSystemPreferences"
      :saving="systemPreferencesSaving"
      :test-sending="systemTestSending"
      v-model:webhook-url="webhookUrl"
      :webhook-url-set="webhookUrlSet"
      :webhook-url-masked="webhookUrlMasked"
      v-model:webhook-timeout="webhookTimeout"
      @webhook-url-touched="webhookUrlTouched = true"
      @close="closeSystemPreferences"
      @save="saveSystemPreferences"
      @send-test="sendSystemWebhookTest"
    />

    <Teleport to="body">
      <transition name="toast">
        <div
          v-if="message"
          class="toast-notification"
          :class="`toast-${messageType || 'info'}`"
        >
          <div class="toast-icon">
            <svg v-if="messageType === 'success'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <svg v-else-if="messageType === 'error'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            <svg v-else-if="messageType === 'warning'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <span class="toast-text">{{ message }}</span>
        </div>
      </transition>
    </Teleport>
  </div>
</template>
