/**
 * StatusPanel.js — Dashboard overview (Azure style)
 */
import api from '/static/js/api.js';

const { ref, computed, onMounted, onUnmounted } = Vue;

export default {
  name: 'StatusPanel',
  props: ['status', 'config', 'icons'],
  emits: ['refresh'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.dashboard"></span>
        概览
      </div>

      <!-- Connection banner -->
      <div v-if="status.napcat_connected" class="az-status-banner az-status-banner--ok">
        <span class="az-status-banner__icon" v-html="icons.checkCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">NapCat 服务在线</div>
          <div class="az-status-banner__desc">
            {{ botInfoText }}
          </div>
        </div>
      </div>
      <div v-else class="az-status-banner az-status-banner--err">
        <span class="az-status-banner__icon" v-html="icons.errorCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">NapCat 服务离线</div>
          <div class="az-status-banner__desc">WebSocket 连接断开，请检查 NapCat 是否启动</div>
        </div>
      </div>

      <!-- Metric tiles -->
      <div class="az-metrics">
        <div class="az-metric">
          <div class="az-metric__label">连接状态</div>
          <div class="az-metric__value" :class="status.napcat_connected ? 'az-metric__value--success' : 'az-metric__value--danger'">
            {{ status.napcat_connected ? 'Online' : 'Offline' }}
          </div>
          <div class="az-metric__sub">NapCat WebSocket</div>
        </div>
        <div class="az-metric">
          <div class="az-metric__label">服务端口</div>
          <div class="az-metric__value">{{ config.advanced.service_port || '-' }}</div>
          <div class="az-metric__sub">HTTP Server</div>
        </div>
        <div class="az-metric">
          <div class="az-metric__label">消息总量</div>
          <div class="az-metric__value">{{ messages.length }}</div>
          <div class="az-metric__sub">已记录消息条数</div>
        </div>
      </div>

      <!-- Activity log -->
      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">活动日志</span>
          <div style="display:flex;gap:8px;">
            <el-button size="small" @click="$emit('refresh')">
              <el-icon><Refresh /></el-icon>
              <span style="margin-left:4px;">刷新</span>
            </el-button>
            <el-button size="small" type="danger" plain @click="handleClearLogs">清屏</el-button>
          </div>
        </div>
        <div class="az-card__body--flush">
          <div class="az-terminal" ref="termRef">
            <div v-if="messages.length === 0" class="az-terminal__empty">暂无消息记录</div>
            <div
              v-for="(msg, i) in messages" :key="i"
              class="az-terminal__row"
              :class="{ 'az-terminal__row--friend-ok': msg.event_type === 'friend_request' && msg.approved, 'az-terminal__row--friend-fail': msg.event_type === 'friend_request' && !msg.approved }"
            >
              <span class="az-terminal__time">{{ fmtTime(msg.timestamp) }}</span>
              <span v-if="msg.event_type === 'friend_request'" class="az-terminal__role" :style="{ color: msg.approved ? 'var(--color-success)' : 'var(--color-danger)' }">[好友请求]</span>
              <span v-else class="az-terminal__role">[{{ msg.role === 'assistant' ? 'AI' : 'User' }}]</span>
              <span class="az-terminal__msg">{{ stripEmoji(msg.content) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,

  setup(props, { emit }) {
    const { ElMessage } = ElementPlus;
    const messages = ref([]);
    const termRef = ref(null);
    const botQQ = ref('');
    const botNickname = ref('');
    let timer = null;

    const botInfoText = computed(() => {
      if (botQQ.value && botNickname.value) {
        return `当前账号: ${botNickname.value} (${botQQ.value})`;
      } else if (botQQ.value) {
        return `当前账号: ${botQQ.value}`;
      }
      return '通信链路已建立，正在监听消息事件';
    });

    const fetch = async () => {
      try {
        const d = await api.getStatus();
        Object.assign(props.status, { napcat_connected: d.napcat_connected, napcat_url: d.napcat_url, napcat_error: d.napcat_error });
        messages.value = d.recent_messages || [];
        botQQ.value = d.bot_qq || '';
        botNickname.value = d.bot_nickname || '';
        if (d.log_max_length && props.config.advanced) props.config.advanced.log_max_length = Number(d.log_max_length);
      } catch {}
    };

    const handleClearLogs = async () => {
      try { await api.clearLogs(); messages.value = []; ElMessage.success('日志已清理'); } catch {}
    };

    const pad = n => String(n).padStart(2, '0');
    const fmtTime = ts => {
      if (!ts) return '';
      const d = new Date(ts);
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };

    const stripEmoji = t => t ? t.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '') : '';

    onMounted(() => { fetch(); timer = setInterval(fetch, 5000); });
    onUnmounted(() => { if (timer) clearInterval(timer); });

    return { messages, termRef, botInfoText, handleClearLogs, fmtTime, stripEmoji };
  }
};
