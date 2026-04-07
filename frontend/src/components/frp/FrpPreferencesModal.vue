<script setup>
import BaseModal from '../BaseModal.vue';
import SectionCard from '../ui/SectionCard.vue';
import ModalFooterActions from '../ui/ModalFooterActions.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  serverAddr: { type: String, default: '' },
  serverPort: { type: String, default: '7000' },
  vhostHttpPort: { type: String, default: '' },
  adminIp: { type: String, default: '127.0.0.1' },
  adminPort: { type: String, default: '7400' },
  adminUser: { type: String, default: '' },
  adminPassword: { type: String, default: '' },
  useDomain: { type: Boolean, default: false },
  domainSuffix: { type: String, default: '' },
});

const emit = defineEmits([
  'close',
  'save',
  'update:serverAddr',
  'update:serverPort',
  'update:vhostHttpPort',
  'update:adminIp',
  'update:adminPort',
  'update:adminUser',
  'update:adminPassword',
  'update:useDomain',
  'update:domainSuffix',
]);

function updateField(field, event) {
  emit(`update:${field}`, event.target.value);
}

function updateBool(field, event) {
  emit(`update:${field}`, !!event.target.checked);
}
</script>

<template>
  <BaseModal
    :visible="visible"
    title="偏好设置"
    icon="bolt"
    width="max-w-[880px]"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <SectionCard title="FRPS 连接" description="用于 FRPC 连接服务端建立隧道。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="frpServerAddrInput" class="block text-xs font-medium text-slate-600">服务地址</label>
            <input
              id="frpServerAddrInput"
              :value="serverAddr"
              type="text"
              :disabled="saving"
              placeholder="如: 1.2.3.4 或 frps.example.com"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('serverAddr', $event)"
            />
          </div>
          <div>
            <label for="frpServerPortInput" class="block text-xs font-medium text-slate-600">服务端口</label>
            <input
              id="frpServerPortInput"
              :value="serverPort"
              type="number"
              min="1"
              :disabled="saving"
              placeholder="7000"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('serverPort', $event)"
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="管理面板" description="用于读取运行状态与健康检查（可选）。">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="frpAdminIpInput" class="block text-xs font-medium text-slate-600">管理地址</label>
            <input
              id="frpAdminIpInput"
              :value="adminIp"
              type="text"
              :disabled="saving"
              placeholder="127.0.0.1"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('adminIp', $event)"
            />
          </div>
          <div>
            <label for="frpAdminPortInput" class="block text-xs font-medium text-slate-600">管理端口</label>
            <input
              id="frpAdminPortInput"
              :value="adminPort"
              type="number"
              min="1"
              :disabled="saving"
              placeholder="7400"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('adminPort', $event)"
            />
          </div>
        </div>
        <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="frpAdminUserInput" class="block text-xs font-medium text-slate-600">用户名</label>
            <input
              id="frpAdminUserInput"
              :value="adminUser"
              type="text"
              :disabled="saving"
              placeholder="可选"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('adminUser', $event)"
            />
          </div>
          <div>
            <label for="frpAdminPasswordInput" class="block text-xs font-medium text-slate-600">密码</label>
            <input
              id="frpAdminPasswordInput"
              :value="adminPassword"
              type="password"
              :disabled="saving"
              placeholder="可选"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('adminPassword', $event)"
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="域名模式" description="开启后可为 HTTP/HTTPS 代理自动分配子域名。">
        <template #header>
          <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">即时生效</span>
        </template>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
            <label for="frpUseDomainSwitch" class="block text-xs font-medium text-slate-600">启用域名模式</label>
            <div class="mt-2 flex items-center gap-3">
              <label class="relative inline-block h-6 w-11">
                <input
                  id="frpUseDomainSwitch"
                  class="peer h-0 w-0 opacity-0"
                  type="checkbox"
                  :checked="useDomain"
                  :disabled="saving"
                  @change="updateBool('useDomain', $event)"
                />
                <span class="absolute inset-0 cursor-pointer rounded-full bg-slate-300 transition peer-checked:bg-slate-900"></span>
                <span class="absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.18)] transition peer-checked:translate-x-5"></span>
              </label>
              <span class="text-xs font-medium" :class="useDomain ? 'text-emerald-700' : 'text-slate-600'">{{ useDomain ? '已启用' : '已关闭' }}</span>
            </div>
            <p class="mt-2 text-[11px] leading-4 text-slate-500">切换后立即下发设置。</p>
          </div>

          <div class="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
            <label for="frpVhostHttpPortInput" class="block text-xs font-medium text-slate-600">HTTP 入口端口</label>
            <input
              id="frpVhostHttpPortInput"
              :value="vhostHttpPort"
              type="number"
              min="1"
              :disabled="saving"
              placeholder="80，可留空"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('vhostHttpPort', $event)"
            />
            <p class="mt-2 text-[11px] leading-4 text-slate-500">对应服务端 vhost_http_port。</p>
          </div>
        </div>

        <div class="mt-3">
          <label for="frpDomainSuffixInput" class="block text-xs font-medium text-slate-600">域名后缀</label>
          <div class="relative mt-2">
            <input
              id="frpDomainSuffixInput"
              :value="domainSuffix"
              type="text"
              :disabled="saving || !useDomain"
              placeholder="如: example.com"
              class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:cursor-not-allowed disabled:opacity-55"
              @input="updateField('domainSuffix', $event)"
            />
            <div
              v-if="!useDomain"
              class="absolute inset-0 flex items-center justify-center rounded-xl bg-slate-100/80 px-4 text-center text-xs font-medium leading-5 text-slate-600 backdrop-blur-sm"
            >
              请先开启域名模式
            </div>
          </div>
        </div>
      </SectionCard>
    </div>

    <template #footer>
      <ModalFooterActions
        cancel-text="取消"
        submit-text="保存设置"
        submitting-text="保存中..."
        :disabled="saving"
        :submitting="saving"
        @cancel="emit('close')"
        @submit="emit('save')"
      />
    </template>
  </BaseModal>
</template>

