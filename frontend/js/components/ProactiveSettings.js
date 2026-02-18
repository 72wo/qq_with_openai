/**
 * ProactiveSettings.js — 主动消息控制面板
 * 16 种策略开关 + 频率 / 范围 / 时段管理
 */
import api from '/static/js/api.js';

const { ref, reactive, computed, onMounted, onUnmounted, watch } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export default {
  name: 'ProactiveSettings',
  props: ['config', 'status', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.message || msgIcon"></span>
        主动消息
      </div>

      <!-- Status banner -->
      <div v-if="schedulerStatus.running" class="az-status-banner az-status-banner--ok">
        <span class="az-status-banner__icon" v-html="icons.checkCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">调度器运行中</div>
          <div class="az-status-banner__desc">
            今日已发 {{ schedulerStatus.total_sent_today }} / {{ schedulerStatus.daily_limit }} 条
            <template v-if="schedulerStatus.last_strategy"> · 最近: {{ schedulerStatus.last_strategy }} → {{ schedulerStatus.last_target }}</template>
            <template v-if="schedulerStatus.next_action_in > 0"> · 下次约 {{ Math.ceil(schedulerStatus.next_action_in / 60) }} 分钟后</template>
          </div>
        </div>
        <el-button size="small" style="margin-left:auto;" @click="manualTrigger" :loading="triggering">手动触发</el-button>
      </div>
      <div v-else class="az-status-banner az-status-banner--err">
        <span class="az-status-banner__icon" v-html="icons.errorCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">调度器未运行</div>
          <div class="az-status-banner__desc">启用主动消息并保存配置后，调度器将自动启动</div>
        </div>
      </div>

      <!-- Sub tabs -->
      <div class="az-subtabs">
        <div class="az-subtab" :class="{'az-subtab--active': subtab==='general'}" @click="subtab='general'">基本设置</div>
        <div class="az-subtab" :class="{'az-subtab--active': subtab==='strategies'}" @click="subtab='strategies'">策略管理</div>
        <div class="az-subtab" :class="{'az-subtab--active': subtab==='scope'}" @click="subtab='scope'">作用范围</div>
      </div>

      <!-- ═══ Tab 1: General ═══ -->
      <div v-if="subtab==='general'" class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">基本设置</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="160px" class="az-form">
            <el-form-item label="启用主动消息">
              <el-switch v-model="pc.enabled" />
              <span class="az-helper">开启后，AI 将在合适的时间主动给好友/群聊发送消息</span>
            </el-form-item>

            <div class="az-section-title">频率控制</div>

            <el-form-item label="全局每日上限">
              <el-input-number v-model="pc.global_daily_max" :min="1" :max="200" :step="5" controls-position="right" />
              <span class="az-helper">每天最多发送的主动消息总数</span>
            </el-form-item>
            <el-form-item label="最小间隔 (分钟)">
              <el-input-number v-model="pc.min_interval_minutes" :min="5" :max="1440" :step="5" controls-position="right" />
              <span class="az-helper">实际会有 ±30% 的随机抖动</span>
            </el-form-item>
            <el-form-item label="单好友每日上限">
              <el-input-number v-model="pc.per_friend_daily_max" :min="1" :max="50" controls-position="right" />
              <span class="az-helper">同一好友每天最多收到几条</span>
            </el-form-item>
            <el-form-item label="单群每日上限">
              <el-input-number v-model="pc.per_group_daily_max" :min="1" :max="30" controls-position="right" />
              <span class="az-helper">同一群聊每天最多几条</span>
            </el-form-item>

            <div class="az-section-title">活跃时段</div>

            <el-form-item label="活跃时间">
              <div style="display:flex;align-items:center;gap:8px;">
                <el-input-number v-model="pc.active_hours_start" :min="0" :max="23" controls-position="right" />
                <span style="color:var(--color-text-secondary);">时 —</span>
                <el-input-number v-model="pc.active_hours_end" :min="1" :max="24" controls-position="right" />
                <span style="color:var(--color-text-secondary);">时</span>
              </div>
              <span class="az-helper">仅在此时间段内发送，避免深夜打扰</span>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- ═══ Tab 2: Strategies ═══ -->
      <div v-if="subtab==='strategies'">
        <div v-for="s in strategyDefs" :key="s.id" class="az-card" style="margin-bottom:12px;">
          <div class="az-card__header" style="padding:12px 20px;">
            <div style="display:flex;align-items:center;gap:12px;flex:1;min-width:0;">
              <el-switch
                :model-value="getStrategyEnabled(s.id)"
                @change="v => setStrategyField(s.id, 'enabled', v)"
                size="small"
              />
              <div style="flex:1;min-width:0;">
                <div style="font-weight:600;font-size:14px;color:var(--color-text-primary);">{{ s.label }}</div>
                <div style="font-size:12px;color:var(--color-text-tertiary);margin-top:4px;line-height:1.5;">
                  {{ s.description }}
                  <span style="margin-left:8px;opacity:.7;">{{ s.time_range[0] }}:00 - {{ s.time_range[1] }}:00</span>
                  <el-tag v-for="tt in s.target_types" :key="tt" size="small" style="margin-left:4px;" :type="tt==='group' ? 'warning' : 'info'">{{ tt === 'friend' ? '好友' : '群聊' }}</el-tag>
                </div>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
              <span style="font-size:12px;color:var(--color-text-tertiary);">权重</span>
              <el-input-number
                :model-value="getStrategyWeight(s.id)"
                @change="v => setStrategyField(s.id, 'weight', v)"
                :min="0.1" :max="5.0" :step="0.1" :precision="1"
                size="small" style="width:120px;"
                controls-position="right"
                :disabled="!getStrategyEnabled(s.id)"
              />
            </div>
          </div>
        </div>

        <div style="margin-top:16px;display:flex;gap:8px;">
          <el-button size="small" @click="enableAll">全部启用</el-button>
          <el-button size="small" @click="disableAll">全部禁用</el-button>
        </div>
      </div>

      <!-- ═══ Tab 3: Scope ═══ -->
      <div v-if="subtab==='scope'" class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">作用范围</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="160px" class="az-form">
            <el-form-item label="范围模式">
              <el-radio-group v-model="pc.scope_mode">
                <el-radio value="disabled">禁用</el-radio>
                <el-radio value="whitelist">白名单</el-radio>
                <el-radio value="blacklist">黑名单</el-radio>
              </el-radio-group>
              <span class="az-helper">
                <template v-if="pc.scope_mode==='disabled'">不会发送给任何人</template>
                <template v-if="pc.scope_mode==='whitelist'">仅对列表中的好友/群发送</template>
                <template v-if="pc.scope_mode==='blacklist'">对所有好友发送，排除列表</template>
              </span>
            </el-form-item>
          </el-form>

          <template v-if="pc.scope_mode==='whitelist'">
            <div class="az-section-title">好友白名单</div>
            <el-form label-width="160px" class="az-form">
              <el-form-item label="允许的好友 QQ 号">
                <div class="az-id-list-editor">
                  <div class="az-id-list-editor__input">
                    <el-input v-model="friendInput" placeholder="输入 QQ 号后回车添加" size="small" @keyup.enter="addFriendWl" style="width:200px;" />
                    <el-button size="small" type="primary" @click="addFriendWl">添加</el-button>
                  </div>
                  <div class="az-id-list-editor__tags">
                    <el-tag v-for="id in pc.friend_whitelist" :key="id" closable @close="removeFriendWl(id)" size="small">{{ id }}</el-tag>
                    <span v-if="!pc.friend_whitelist.length" style="color:var(--color-text-tertiary);font-size:12px;">暂无</span>
                  </div>
                </div>
              </el-form-item>
            </el-form>

            <div class="az-section-title">群聊白名单</div>
            <el-form label-width="160px" class="az-form">
              <el-form-item label="允许的群号">
                <div class="az-id-list-editor">
                  <div class="az-id-list-editor__input">
                    <el-input v-model="groupInput" placeholder="输入群号后回车添加" size="small" @keyup.enter="addGroupWl" style="width:200px;" />
                    <el-button size="small" type="primary" @click="addGroupWl">添加</el-button>
                  </div>
                  <div class="az-id-list-editor__tags">
                    <el-tag v-for="id in pc.group_whitelist" :key="id" closable @close="removeGroupWl(id)" size="small">{{ id }}</el-tag>
                    <span v-if="!pc.group_whitelist.length" style="color:var(--color-text-tertiary);font-size:12px;">暂无</span>
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </template>

          <template v-if="pc.scope_mode==='blacklist'">
            <div class="az-section-title">好友黑名单</div>
            <el-form label-width="160px" class="az-form">
              <el-form-item label="排除的好友 QQ 号">
                <div class="az-id-list-editor">
                  <div class="az-id-list-editor__input">
                    <el-input v-model="friendInput" placeholder="输入 QQ 号后回车添加" size="small" @keyup.enter="addFriendBl" style="width:200px;" />
                    <el-button size="small" type="primary" @click="addFriendBl">添加</el-button>
                  </div>
                  <div class="az-id-list-editor__tags">
                    <el-tag v-for="id in pc.friend_blacklist" :key="id" closable @close="removeFriendBl(id)" size="small" type="danger">{{ id }}</el-tag>
                    <span v-if="!pc.friend_blacklist.length" style="color:var(--color-text-tertiary);font-size:12px;">暂无</span>
                  </div>
                </div>
              </el-form-item>
            </el-form>

            <div class="az-section-title">群聊黑名单</div>
            <el-form label-width="160px" class="az-form">
              <el-form-item label="排除的群号">
                <div class="az-id-list-editor">
                  <div class="az-id-list-editor__input">
                    <el-input v-model="groupInput" placeholder="输入群号后回车添加" size="small" @keyup.enter="addGroupBl" style="width:200px;" />
                    <el-button size="small" type="primary" @click="addGroupBl">添加</el-button>
                  </div>
                  <div class="az-id-list-editor__tags">
                    <el-tag v-for="id in pc.group_blacklist" :key="id" closable @close="removeGroupBl(id)" size="small" type="danger">{{ id }}</el-tag>
                    <span v-if="!pc.group_blacklist.length" style="color:var(--color-text-tertiary);font-size:12px;">暂无</span>
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </template>

        </div>
      </div>

    </div>
  `,

  setup(props) {
    const subtab = ref('general');
    const triggering = ref(false);
    const friendInput = ref('');
    const groupInput = ref('');

    const msgIcon = `<svg viewBox="0 0 16 16"><path d="M2 3h12a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 3V4a1 1 0 011-1z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M5 7h6M5 9.5h4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>`;

    // 本地配置副本（响应式）
    const pc = reactive({
      enabled: false,
      scope_mode: 'disabled',
      friend_whitelist: [],
      friend_blacklist: [],
      group_whitelist: [],
      group_blacklist: [],
      global_daily_max: 30,
      per_friend_daily_max: 3,
      per_group_daily_max: 2,
      min_interval_minutes: 30,
      active_hours_start: 8,
      active_hours_end: 23,
      strategies: {},
    });

    const strategyDefs = ref([]);
    const schedulerStatus = ref({
      running: false, enabled: false, total_sent_today: 0, daily_limit: 0,
      last_sent_time: null, last_strategy: null, last_target: null, next_action_in: 0,
    });

    let statusTimer = null;

    // 加载配置
    const loadConfig = async () => {
      try {
        const res = await api.getProactiveConfig();
        if (res.data) {
          Object.keys(pc).forEach(k => {
            if (res.data[k] !== undefined) {
              if (Array.isArray(res.data[k])) {
                pc[k] = [...res.data[k]];
              } else if (typeof res.data[k] === 'object' && res.data[k] !== null) {
                pc[k] = { ...res.data[k] };
              } else {
                pc[k] = res.data[k];
              }
            }
          });
        }
      } catch {}
    };

    // 加载策略定义
    const loadStrategies = async () => {
      try {
        const res = await api.getProactiveStrategies();
        strategyDefs.value = res.strategies || [];
      } catch {}
    };

    // 轮询调度器状态
    const loadStatus = async () => {
      try {
        const res = await api.getProactiveStatus();
        if (res.data) schedulerStatus.value = res.data;
      } catch {}
    };

    // 策略字段读写 helper
    const getStrategyEnabled = (id) => pc.strategies?.[id]?.enabled ?? false;
    const getStrategyWeight = (id) => pc.strategies?.[id]?.weight ?? 0.5;
    const setStrategyField = (id, field, val) => {
      if (!pc.strategies) pc.strategies = {};
      if (!pc.strategies[id]) pc.strategies[id] = { enabled: false, weight: 0.5 };
      pc.strategies[id][field] = val;
    };

    const enableAll = () => {
      strategyDefs.value.forEach(s => setStrategyField(s.id, 'enabled', true));
    };
    const disableAll = () => {
      strategyDefs.value.forEach(s => setStrategyField(s.id, 'enabled', false));
    };

    // ID 列表操作
    const _addId = (list, input, inputRef) => {
      const val = input.value.trim();
      if (!val) return;
      if (!/^\d{5,15}$/.test(val)) {
        ElMessage.warning('请输入有效的 QQ/群号 (5-15 位数字)');
        return;
      }
      if (!list.includes(val)) list.push(val);
      input.value = '';
    };
    const addFriendWl = () => _addId(pc.friend_whitelist, friendInput);
    const addGroupWl = () => _addId(pc.group_whitelist, groupInput);
    const addFriendBl = () => _addId(pc.friend_blacklist, friendInput);
    const addGroupBl = () => _addId(pc.group_blacklist, groupInput);
    const removeFriendWl = id => { pc.friend_whitelist = pc.friend_whitelist.filter(v => v !== id); };
    const removeGroupWl = id => { pc.group_whitelist = pc.group_whitelist.filter(v => v !== id); };
    const removeFriendBl = id => { pc.friend_blacklist = pc.friend_blacklist.filter(v => v !== id); };
    const removeGroupBl = id => { pc.group_blacklist = pc.group_blacklist.filter(v => v !== id); };

    // 手动触发
    const manualTrigger = async () => {
      triggering.value = true;
      try {
        await api.triggerProactive();
        ElMessage.success('已触发一次主动消息');
        await loadStatus();
      } catch {}
      finally { triggering.value = false; }
    };

    // 将本地配置同步到 config.proactive 以便全局保存
    watch(pc, () => {
      if (!props.config.proactive) props.config.proactive = {};
      Object.assign(props.config.proactive, JSON.parse(JSON.stringify(pc)));
    }, { deep: true });

    onMounted(async () => {
      await Promise.all([loadConfig(), loadStrategies(), loadStatus()]);
      statusTimer = setInterval(loadStatus, 8000);
    });

    onUnmounted(() => {
      if (statusTimer) clearInterval(statusTimer);
    });

    return {
      subtab, pc, strategyDefs, schedulerStatus, triggering,
      friendInput, groupInput, msgIcon,
      getStrategyEnabled, getStrategyWeight, setStrategyField,
      enableAll, disableAll,
      addFriendWl, addGroupWl, addFriendBl, addGroupBl,
      removeFriendWl, removeGroupWl, removeFriendBl, removeGroupBl,
      manualTrigger,
    };
  }
};
