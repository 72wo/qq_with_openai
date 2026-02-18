/**
 * ProactiveSettings.js — 主动消息控制面板
 * 16 种策略开关 + 频率 / 范围 / 时段管理 + 策略编辑弹窗 + 好友/群号自动补全
 */
import api from '/static/js/api.js';

const { ref, reactive, computed, onMounted, onUnmounted, watch } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export default {
  name: 'ProactiveSettings',
  props: ['config', 'status', 'icons', 'savedAt'],
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
                  <span style="margin-left:8px;opacity:.7;">
                    {{ getStrategyTimeRange(s.id, s.time_range)[0] }} - {{ getStrategyTimeRange(s.id, s.time_range)[1] }}
                  </span>
                  <el-tag v-for="tt in getStrategyTargetTypes(s.id, s.target_types)" :key="tt" size="small" style="margin-left:4px;" :type="tt==='group' ? 'warning' : 'info'">{{ tt === 'friend' ? '好友' : '群聊' }}</el-tag>
                </div>
              </div>
            </div>
            <div style="flex-shrink:0;">
              <el-button
                :icon="EditIcon"
                circle
                style="width:28px;height:28px;padding:0;"
                title="自定义权重、时间与目标"
                @click="openStrategyEdit(s)"
              />
            </div>
          </div>
        </div>

        <div style="margin-top:16px;display:flex;gap:8px;">
          <el-button size="small" @click="enableAll">全部启用</el-button>
          <el-button size="small" @click="disableAll">全部禁用</el-button>
        </div>
      </div>

      <!-- ═══ 策略编辑弹窗 ═══ -->
      <el-dialog
        v-model="editDialog.visible"
        :title="editDialog.label ? '编辑策略: ' + editDialog.label : '编辑策略'"
        width="360px"
        destroy-on-close
      >
        <div style="display:flex;flex-direction:column;gap:20px;padding:8px 0;">

          <!-- 权重 -->
          <div style="display:flex;flex-direction:column;align-items:center;gap:6px;">
            <span style="font-size:13px;color:var(--color-text-secondary);">权重</span>
            <el-input-number
              v-model="editDialog.weight"
              :min="0.1" :max="5.0" :step="0.1" :precision="1"
              controls-position="right"
              style="width:120px;"
            />
            <span style="font-size:11px;color:var(--color-text-tertiary);">数值越大，被抽中概率越高</span>
          </div>

          <!-- 时间段 -->
          <div style="display:flex;flex-direction:column;align-items:center;gap:6px;">
            <span style="font-size:13px;color:var(--color-text-secondary);">自定义时间段</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <el-time-picker
                v-model="editDialog.timeStartStr"
                placeholder="开始"
                format="HH:mm"
                value-format="HH:mm"
                style="width:105px;"
              />
              <span style="color:var(--color-text-tertiary);">—</span>
              <el-time-picker
                v-model="editDialog.timeEndStr"
                placeholder="结束"
                format="HH:mm"
                value-format="HH:mm"
                style="width:105px;"
              />
            </div>
            <span style="font-size:11px;color:var(--color-text-tertiary);">覆盖全局活跃时段</span>
          </div>

          <!-- 目标类型 -->
          <div style="display:flex;flex-direction:column;align-items:center;gap:6px;">
            <span style="font-size:13px;color:var(--color-text-secondary);">目标类型</span>
            <el-checkbox-group v-model="editDialog.targetTypes">
              <el-checkbox value="friend">好友</el-checkbox>
              <el-checkbox value="group">群聊</el-checkbox>
            </el-checkbox-group>
            <span style="font-size:11px;color:var(--color-text-tertiary);">覆盖策略默认的目标类型</span>
          </div>

        </div>

        <template #footer>
          <el-button @click="editDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="saveStrategyEdit">保存</el-button>
        </template>
      </el-dialog>

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
                    <el-autocomplete
                      v-model="friendInput"
                      :fetch-suggestions="queryFriendSuggestions"
                      placeholder="输入 QQ 号或昵称后回车添加"
                      size="small"
                      style="width:220px;"
                      value-key="value"
                      @keyup.enter="addFriendWl"
                      @select="onFriendSelect($event, addFriendWl)"
                      clearable
                    />
                    <el-button size="small" type="primary" @click="addFriendWl" style="height:26px;padding:0 12px;">添加</el-button>
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
                    <el-autocomplete
                      v-model="groupInput"
                      :fetch-suggestions="queryGroupSuggestions"
                      placeholder="输入群号或群名后回车添加"
                      size="small"
                      style="width:220px;"
                      value-key="value"
                      @keyup.enter="addGroupWl"
                      @select="onGroupSelect($event, addGroupWl)"
                      clearable
                    />
                    <el-button size="small" type="primary" @click="addGroupWl" style="height:26px;padding:0 12px;">添加</el-button>
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
                    <el-autocomplete
                      v-model="friendInput"
                      :fetch-suggestions="queryFriendSuggestions"
                      placeholder="输入 QQ 号或昵称后回车添加"
                      size="small"
                      style="width:220px;"
                      value-key="value"
                      @keyup.enter="addFriendBl"
                      @select="onFriendSelect($event, addFriendBl)"
                      clearable
                    />
                    <el-button size="small" type="primary" @click="addFriendBl" style="height:26px;padding:0 12px;">添加</el-button>
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
                    <el-autocomplete
                      v-model="groupInput"
                      :fetch-suggestions="queryGroupSuggestions"
                      placeholder="输入群号或群名后回车添加"
                      size="small"
                      style="width:220px;"
                      value-key="value"
                      @keyup.enter="addGroupBl"
                      @select="onGroupSelect($event, addGroupBl)"
                      clearable
                    />
                    <el-button size="small" type="primary" @click="addGroupBl" style="height:26px;padding:0 12px;">添加</el-button>
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

    // 好友/群聊缓存（用于自动补全）
    const friendsCache = ref([]);
    const groupsCache = ref([]);

    const msgIcon = `<svg viewBox="0 0 16 16"><path d="M2 3h12a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 3V4a1 1 0 011-1z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M5 7h6M5 9.5h4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>`;

    // ── 策略编辑弹窗状态 ────────────────────────────────
    const editDialog = reactive({
      visible: false,
      strategyId: null,
      label: '',
      weight: 0.5,
      timeStartStr: '08:00',
      timeEndStr: '23:00',
      targetTypes: ['friend', 'group'],
    });

    // 时间工具：分钟 <-> 字符串('HH:MM')，并支持输入为小时/分钟/字符串
    const minutesToStr = (m) => {
      const hh = Math.floor(m / 60);
      const mm = m % 60;
      return String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0');
    };
    const strToMinutes = (s) => {
      if (!s || typeof s !== 'string') return 0;
      const m = s.trim().match(/^(\d{1,2}):(\d{2})$/);
      if (!m) return 0;
      const hh = parseInt(m[1], 10);
      const mm = parseInt(m[2], 10);
      return hh * 60 + mm;
    };
    const normalizeToTimeStr = (v) => {
      if (typeof v === 'number') {
        // 小于等于 24 的视为小时
        if (v <= 24) return minutesToStr(v * 60);
        return minutesToStr(v);
      }
      if (typeof v === 'string') {
        const m = v.trim().match(/^(\d{1,2}):(\d{2})$/);
        if (m) return String(m[1]).padStart(2, '0') + ':' + String(m[2]).padStart(2, '0');
      }
      return '00:00';
    };

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

    // ── 加载 ────────────────────────────────────────────

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

    const loadStrategies = async () => {
      try {
        const res = await api.getProactiveStrategies();
        strategyDefs.value = res.strategies || [];
      } catch {}
    };

    const loadStatus = async () => {
      try {
        const res = await api.getProactiveStatus();
        if (res.data) schedulerStatus.value = res.data;
      } catch {}
    };

    // 懒加载好友/群聊缓存（仅在 NapCat 在线时加载一次）
    const ensureFriendsCache = async () => {
      if (friendsCache.value.length > 0 || !props.status?.napcat_connected) return;
      try {
        const res = await api.getFriendList();
        friendsCache.value = (res.friends || []).map(f => ({
          value: f.user_id,
          label: `${f.user_id}${f.nickname ? ' ' + f.nickname : ''}${f.remark ? ' (' + f.remark + ')' : ''}`,
        }));
      } catch {}
    };

    const ensureGroupsCache = async () => {
      if (groupsCache.value.length > 0 || !props.status?.napcat_connected) return;
      try {
        const res = await api.getGroupList();
        groupsCache.value = (res.groups || []).map(g => ({
          value: g.group_id,
          label: `${g.group_id}${g.group_name ? ' ' + g.group_name : ''}`,
        }));
      } catch {}
    };

    // ── 自动补全 fetch-suggestions ─────────────────────

    const queryFriendSuggestions = async (q, cb) => {
      await ensureFriendsCache();
      const lower = q.toLowerCase();
      const results = friendsCache.value.filter(f =>
        f.value.includes(q) || f.label.toLowerCase().includes(lower)
      ).slice(0, 20);
      cb(results);
    };

    const queryGroupSuggestions = async (q, cb) => {
      await ensureGroupsCache();
      const lower = q.toLowerCase();
      const results = groupsCache.value.filter(g =>
        g.value.includes(q) || g.label.toLowerCase().includes(lower)
      ).slice(0, 20);
      cb(results);
    };

    // 选中建议时，把 value 填入输入框并立即 add
    const onFriendSelect = (item, addFn) => {
      friendInput.value = item.value;
      addFn();
    };
    const onGroupSelect = (item, addFn) => {
      groupInput.value = item.value;
      addFn();
    };

    // ── 策略字段读写 helper ──────────────────────────────

    const getStrategyEnabled = (id) => pc.strategies?.[id]?.enabled ?? false;
    const getStrategyWeight = (id) => pc.strategies?.[id]?.weight ?? 0.5;
    // 返回字符串形式的时间范围 ['HH:MM','HH:MM']（处理默认值/小时/分钟兼容）
    const getStrategyTimeRange = (id, defRange) => {
      const tr = pc.strategies?.[id]?.time_range ?? defRange ?? [0, 24];
      // 三种可能的存储格式：
      // - [hour, hour] (例如 [6,10])
      // - [minutes, minutes] (例如 [360, 600])
      // - ["HH:MM","HH:MM"]
      const a = tr[0]; const b = tr[1];
      return [normalizeToTimeStr(a), normalizeToTimeStr(b)];
    };
    const getStrategyTargetTypes = (id, defTypes) => pc.strategies?.[id]?.target_types ?? defTypes ?? ['friend', 'group'];

    const setStrategyField = (id, field, val) => {
      if (!pc.strategies) pc.strategies = {};
      if (!pc.strategies[id]) pc.strategies[id] = { enabled: false, weight: 0.5 };
      pc.strategies[id][field] = val;
    };

    const enableAll = () => strategyDefs.value.forEach(s => setStrategyField(s.id, 'enabled', true));
    const disableAll = () => strategyDefs.value.forEach(s => setStrategyField(s.id, 'enabled', false));

    // ── 策略编辑弹窗 ────────────────────────────────────

    const EditIcon = ElementPlusIconsVue.Edit;

    const openStrategyEdit = (s) => {
      const overrides = pc.strategies?.[s.id] || {};
      editDialog.strategyId = s.id;
      editDialog.label = s.label;
      editDialog.weight = overrides.weight ?? 0.5;
      const tr = overrides.time_range ?? s.time_range ?? [8, 23];
      editDialog.timeStartStr = normalizeToTimeStr(tr[0]);
      editDialog.timeEndStr = normalizeToTimeStr(tr[1]);
      editDialog.targetTypes = [...(overrides.target_types ?? s.target_types ?? ['friend', 'group'])];
      editDialog.visible = true;
    };

    const saveStrategyEdit = () => {
      const id = editDialog.strategyId;
      if (!id) return;
      const tStartMin = strToMinutes(editDialog.timeStartStr);
      const tEndMin = strToMinutes(editDialog.timeEndStr);
      if (tStartMin >= tEndMin) {
        ElMessage.warning('时间范围起始必须小于结束');
        return;
      }
      if (editDialog.targetTypes.length === 0) {
        ElMessage.warning('至少选择一种目标类型');
        return;
      }
      if (!pc.strategies) pc.strategies = {};
      if (!pc.strategies[id]) pc.strategies[id] = { enabled: false };
      pc.strategies[id].weight = editDialog.weight;
      pc.strategies[id].time_range = [tStartMin, tEndMin];
      pc.strategies[id].target_types = [...editDialog.targetTypes];
      editDialog.visible = false;
    };

    // ── ID 列表操作 ──────────────────────────────────────

    const _addId = (list, inputRef) => {
      const val = inputRef.value.trim();
      if (!val) return;
      if (!/^\d{5,15}$/.test(val)) {
        ElMessage.warning('请输入有效的 QQ/群号 (5-15 位数字)');
        return;
      }
      if (!list.includes(val)) list.push(val);
      inputRef.value = '';
    };
    const addFriendWl = () => _addId(pc.friend_whitelist, friendInput);
    const addGroupWl = () => _addId(pc.group_whitelist, groupInput);
    const addFriendBl = () => _addId(pc.friend_blacklist, friendInput);
    const addGroupBl = () => _addId(pc.group_blacklist, groupInput);
    const removeFriendWl = id => { pc.friend_whitelist = pc.friend_whitelist.filter(v => v !== id); };
    const removeGroupWl = id => { pc.group_whitelist = pc.group_whitelist.filter(v => v !== id); };
    const removeFriendBl = id => { pc.friend_blacklist = pc.friend_blacklist.filter(v => v !== id); };
    const removeGroupBl = id => { pc.group_blacklist = pc.group_blacklist.filter(v => v !== id); };

    // ── 手动触发 ─────────────────────────────────────────

    const manualTrigger = async () => {
      triggering.value = true;
      try {
        const res = await api.triggerProactive();
        if (res && res.success) {
          ElMessage.success(res.message || '已触发一次主动消息');
        } else {
          ElMessage.warning(res?.message || '触发未成功，请检查目标和策略配置');
        }
        await loadStatus();
      } catch {}
      finally { triggering.value = false; }
    };

    // ── 同步到全局 config（供全局保存使用）─────────────

    watch(pc, () => {
      if (!props.config.proactive) props.config.proactive = {};
      Object.assign(props.config.proactive, JSON.parse(JSON.stringify(pc)));
    }, { deep: true });

    // ── 保存完成后刷新调度器状态 ─────────────────────────

    watch(() => props.savedAt, (n) => {
      if (n > 0) loadStatus();
    });

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
      editDialog, EditIcon,
      getStrategyEnabled, getStrategyWeight, getStrategyTimeRange, getStrategyTargetTypes,
      setStrategyField, enableAll, disableAll,
      openStrategyEdit, saveStrategyEdit,
      addFriendWl, addGroupWl, addFriendBl, addGroupBl,
      removeFriendWl, removeGroupWl, removeFriendBl, removeGroupBl,
      queryFriendSuggestions, queryGroupSuggestions,
      onFriendSelect, onGroupSelect,
      manualTrigger,
    };
  }
};
