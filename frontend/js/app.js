/**
 * app.js — Vue Root Instance
 * Azure Portal layout: Header + Sidebar + Content
 * 含登录门控 + 新导航结构
 */
import api, { onUnauthorized } from '/static/js/api.js';
import LoginPage        from '/static/js/components/LoginPage.js';
import StatusPanel      from '/static/js/components/StatusPanel.js';
import OpenAIConfig     from '/static/js/components/OpenAIConfig.js';
import VisionConfig     from '/static/js/components/VisionConfig.js';
import BotSettings      from '/static/js/components/BotSettings.js';
import ListManager      from '/static/js/components/ListManager.js';
import AdvancedSettings from '/static/js/components/AdvancedSettings.js';
import SecurityPanel    from '/static/js/components/SecurityPanel.js';
import SecuritySettings from '/static/js/components/SecuritySettings.js';
import FriendManager    from '/static/js/components/FriendManager.js';

const { createApp, ref, computed, onMounted, reactive } = Vue;
const { ElMessage } = ElementPlus;

/* ---- Inline SVG Icons (no emoji / no external icon fonts) ---- */
const ICONS = {
  hamburger: `<svg viewBox="0 0 16 16"><rect x="1" y="3" width="14" height="1.5" rx=".5"/><rect x="1" y="7.25" width="14" height="1.5" rx=".5"/><rect x="1" y="11.5" width="14" height="1.5" rx=".5"/></svg>`,
  dashboard: `<svg viewBox="0 0 16 16"><rect x="1" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="1" width="6" height="3" rx="1" fill="currentColor"/><rect x="9" y="6" width="6" height="2" rx="1" fill="currentColor" opacity=".5"/><rect x="1" y="9" width="6" height="2" rx="1" fill="currentColor" opacity=".5"/><rect x="1" y="13" width="6" height="2" rx="1" fill="currentColor" opacity=".3"/><rect x="9" y="10" width="6" height="5" rx="1" fill="currentColor" opacity=".7"/></svg>`,
  openai:    `<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>`,
  eye:       `<svg viewBox="0 0 16 16"><path d="M8 4C4.5 4 1.7 6.5 1 8c.7 1.5 3.5 4 7 4s6.3-2.5 7-4c-.7-1.5-3.5-4-7-4z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>`,
  settings:  `<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="2" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>`,
  list:      `<svg viewBox="0 0 16 16"><rect x="1" y="2" width="3" height="3" rx=".5" fill="currentColor"/><rect x="6" y="2.5" width="9" height="2" rx=".5" fill="currentColor"/><rect x="1" y="6.5" width="3" height="3" rx=".5" fill="currentColor"/><rect x="6" y="7" width="9" height="2" rx=".5" fill="currentColor"/><rect x="1" y="11" width="3" height="3" rx=".5" fill="currentColor"/><rect x="6" y="11.5" width="9" height="2" rx=".5" fill="currentColor"/></svg>`,
  advanced:  `<svg viewBox="0 0 16 16"><rect x="2" y="3" width="12" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5 7h6M5 9.5h4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>`,
  shield:    `<svg viewBox="0 0 16 16"><path d="M8 1L2 4v4c0 3.5 2.6 6.3 6 7 3.4-.7 6-3.5 6-7V4L8 1z" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M6 8l1.5 1.5L10 6.5" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  lock:      `<svg viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>`,
  people:    `<svg viewBox="0 0 16 16"><circle cx="6" cy="4.5" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M1 13c0-2.8 2.2-5 5-5s5 2.2 5 5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M11 6.5a2 2 0 110-4" fill="none" stroke="currentColor" stroke-width="1.1"/><path d="M12 8c1.7 0 3 1.3 3.5 3" fill="none" stroke="currentColor" stroke-width="1.1"/></svg>`,
  logout:    `<svg viewBox="0 0 16 16"><path d="M6 2h7v12H6" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><path d="M10 8H1M3 5.5L.5 8 3 10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  checkCircle: `<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#107c10"/><path d="M6 10l2.5 3L14 7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  errorCircle: `<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#d13438"/><path d="M7 7l6 6M13 7l-6 6" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>`,
};

const NAV_ITEMS = [
  { key: 'status',    label: '概览',       icon: 'dashboard', section: '监控' },
  { key: 'openai',    label: '聊天模型',   icon: 'openai',    section: '配置' },
  { key: 'vision',    label: '视觉模型',   icon: 'eye',       section: '配置' },
  { key: 'customize', label: '自定义设置', icon: 'settings',  section: '配置' },
  { key: 'friends',   label: '好友管理',   icon: 'people',    section: '管理' },
  { key: 'lists',     label: '黑白名单',   icon: 'list',      section: '安全' },
  { key: 'ipban',     label: 'IP 安全',    icon: 'shield',    section: '安全' },
  { key: 'security',  label: '密码管理',   icon: 'lock',      section: '安全' },
  { key: 'advanced',  label: '高级设置',   icon: 'advanced',  section: '系统' },
];

const App = {
  template: `
    <!-- ======== LOGIN PAGE ======== -->
    <login-page v-if="!authenticated" :on-login="onLoginSuccess" />

    <!-- ======== MAIN APP ======== -->
    <div v-else style="display:flex;flex-direction:column;height:100vh;">

      <!-- ======== HEADER ======== -->
      <div class="az-header">
        <div class="az-header__left">
          <div class="az-header__hamburger" @click="sidebarCollapsed = !sidebarCollapsed" v-html="icons.hamburger"></div>
          <div class="az-header__brand">QQ Bot</div>
        </div>
        <div class="az-header__right">
          <div class="az-header__status" :class="{
            'az-header__status--ok':      status.napcat_connected,
            'az-header__status--err':     !status.napcat_connected && !loading,
            'az-header__status--loading': loading
          }">
            <span class="az-header__dot" :class="{
              'az-header__dot--ok':      status.napcat_connected,
              'az-header__dot--err':     !status.napcat_connected && !loading,
              'az-header__dot--loading': loading
            }"></span>
            {{ loading ? '加载中...' : (status.napcat_connected ? 'NapCat 在线' : 'NapCat 离线') }}
          </div>
          <div class="az-header__logout" @click="logout" title="退出登录">
            <span v-html="icons.logout"></span>
          </div>
        </div>
      </div>

      <!-- ======== BODY ======== -->
      <div class="az-body">

        <!-- ---- Sidebar ---- -->
        <nav class="az-sidebar" :class="{ 'az-sidebar--collapsed': sidebarCollapsed }">
          <template v-for="(section, idx) in navSections" :key="section.name">
            <div class="az-sidebar__section">
              <div class="az-sidebar__section-title">{{ section.name }}</div>
              <div
                v-for="item in section.items"
                :key="item.key"
                class="az-nav-item"
                :class="{ 'az-nav-item--active': activeTab === item.key }"
                @click="activeTab = item.key"
              >
                <span class="az-nav-item__icon" v-html="icons[item.icon]"></span>
                <span class="az-nav-item__label">{{ item.label }}</span>
              </div>
            </div>
          </template>
        </nav>

        <!-- ---- Content ---- -->
        <div class="az-content">

          <!-- Toolbar -->
          <div class="az-toolbar">
            <div class="az-breadcrumb">
              <span class="az-breadcrumb__home" @click="activeTab='status'">主页</span>
              <span class="az-breadcrumb__sep">></span>
              <span class="az-breadcrumb__current">{{ currentNavItem.label }}</span>
            </div>
            <div class="az-toolbar__actions">
              <el-button size="small" @click="resetConfig">重置</el-button>
              <el-button type="primary" size="small" @click="saveConfig" :loading="saving">保存配置</el-button>
            </div>
          </div>

          <!-- Page -->
          <div class="az-page" v-if="loading">
            <div class="az-skeleton">
              <div class="az-skeleton__block" style="width:35%;height:20px;"></div>
              <div class="az-skeleton__block" style="width:100%;"></div>
              <div class="az-skeleton__block" style="width:100%;"></div>
              <div class="az-skeleton__block" style="width:70%;"></div>
              <div class="az-skeleton__block" style="width:50%;height:20px;margin-top:28px;"></div>
              <div class="az-skeleton__block" style="width:100%;"></div>
              <div class="az-skeleton__block" style="width:85%;"></div>
            </div>
          </div>

          <div class="az-page" v-else>
            <transition name="az-fade" mode="out-in">
              <component
                :is="currentComponent"
                :config="config"
                :status="status"
                :icons="icons"
                @refresh="refreshStatus"
                :key="activeTab"
              />
            </transition>
          </div>

        </div>
      </div>
    </div>
  `,

  setup() {
    const authenticated    = ref(false);
    const activeTab        = ref('status');
    const sidebarCollapsed = ref(false);
    const loading          = ref(true);
    const saving           = ref(false);
    const icons            = ICONS;

    const config = ref({
      openai:    { baseurl:'', apikey:'', model:'gpt-4', reply_avg_length:50, max_tokens:500, reply_timeout_sec:60 },
      vision:    { enabled:false, use_reply_config:true, baseurl:'', apikey:'', model:'gpt-4-vision-preview' },
      bot:       { prompt:'', auto_reply:true, group_only_at:true, group_reply_at_all:false },
      blacklist: { mode:'disabled', users:[], groups:[], exceptions:[] },
      whitelist: { mode:'disabled', users:[], groups:[], exceptions:[] },
      features:  { image_processing:true, emotion_conversion:true, simulate_typing_enabled:false, typing_multiplier:1.0, typing_base_ms_per_char:60, context_enabled:true, context_max_messages:40, context_compression_enabled:false, context_use_model_for_compression:false, image_context_cache_size:64, context_message_max_chars:200 },
      advanced:  { napcat_url:'ws://localhost:8080/ws/napcat', napcat_token:'', service_port:5000, log_level:'INFO', log_max_length:200, session_expiry_hours: 24, friend_token_expiry_minutes: 10 }
    });

    const status = ref({ napcat_connected:false, napcat_connecting:false, napcat_url:'', napcat_error:'' });

    // ---- Auth check ----
    const checkAuth = async () => {
      const res = await api.checkAuth();
      authenticated.value = !!res.authenticated;
      return authenticated.value;
    };

    const onLoginSuccess = async () => {
      authenticated.value = true;
      loading.value = true;
      await Promise.all([loadConfig(), refreshStatus()]);
      loading.value = false;
    };

    const logout = async () => {
      try {
        await api.logout();
        ElMessage.success('已退出');
        authenticated.value = false;
        setTimeout(() => { window.location.reload(); }, 500);
      } catch {}
    };

    // 401 全局拦截
    onUnauthorized(() => {
      authenticated.value = false;
    });

    // ---- Nav sections ----
    const navSections = computed(() => {
      const map = {};
      NAV_ITEMS.forEach(item => {
        if (!map[item.section]) map[item.section] = { name: item.section, items: [] };
        map[item.section].items.push(item);
      });
      return Object.values(map);
    });

    const currentNavItem = computed(() => NAV_ITEMS.find(n => n.key === activeTab.value) || NAV_ITEMS[0]);

    const tabMap = {
      status: StatusPanel, openai: OpenAIConfig, vision: VisionConfig,
      customize: BotSettings, lists: ListManager, advanced: AdvancedSettings,
      ipban: SecurityPanel, security: SecuritySettings, friends: FriendManager,
    };
    const currentComponent = computed(() => tabMap[activeTab.value] || StatusPanel);

    const loadConfig = async () => {
      try { const resp = await api.getConfig(); config.value = resp.data; } catch {}
    };

    const saveConfig = async () => {
      saving.value = true;
      try { await api.saveConfig(config.value); ElMessage.success('配置已保存'); } catch {}
      finally { saving.value = false; }
    };

    const resetConfig = () => loadConfig();

    const refreshStatus = async () => {
      try {
        const d = await api.getStatus();
        status.value.napcat_connected = d.napcat_connected;
        status.value.napcat_url = d.napcat_url;
        status.value.napcat_error = d.napcat_error;
      } catch {}
    };

    onMounted(async () => {
      const isAuth = await checkAuth();
      if (isAuth) {
        await Promise.all([loadConfig(), refreshStatus()]);
      }
      loading.value = false;
    });

    return { authenticated, activeTab, sidebarCollapsed, loading, saving, icons, config, status, navSections, currentNavItem, currentComponent, saveConfig, resetConfig, refreshStatus, onLoginSuccess, logout };
  }
};

// ---- Bootstrap ----
const app = createApp(App);
app.use(ElementPlus);
for (const [key, comp] of Object.entries(ElementPlusIconsVue)) app.component(key, comp);
app.component('LoginPage', LoginPage);
app.component('StatusPanel', StatusPanel);
app.component('OpenAIConfig', OpenAIConfig);
app.component('VisionConfig', VisionConfig);
app.component('BotSettings', BotSettings);
app.component('ListManager', ListManager);
app.component('AdvancedSettings', AdvancedSettings);
app.component('SecurityPanel', SecurityPanel);
app.component('SecuritySettings', SecuritySettings);
app.component('FriendManager', FriendManager);
app.mount('#app');
