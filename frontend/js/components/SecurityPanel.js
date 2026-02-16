/**
 * SecurityPanel.js — IP 封禁管理面板
 */
import api from '/static/js/api.js';
const { ref, onMounted, computed } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export default {
  name: 'SecurityPanel',
  props: ['config', 'status', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.shield || icons.list"></span>
        IP 安全
      </div>

      <!-- 子选项卡 -->
      <div class="az-subtabs">
        <div class="az-subtab" :class="{'az-subtab--active': subtab==='rules'}" @click="subtab='rules'">安全规则</div>
        <div class="az-subtab" :class="{'az-subtab--active': subtab==='bans'}" @click="subtab='bans'">封禁列表</div>
      </div>

      <!-- 安全规则 -->
      <div v-if="subtab==='rules'">
        <div class="az-card" v-for="rule in rules" :key="rule.rule_id" style="margin-bottom:12px;">
          <div class="az-card__header" style="padding:12px 20px;">
            <div style="display:flex;align-items:center;gap:12px;flex:1;">
              <el-switch v-model="rule.enabled" @change="updateRule(rule)" />
              <span class="az-card__title" style="font-size:14px;">{{ rule.description }}</span>
              <el-tag size="small" type="info">{{ rule.rule_id }}</el-tag>
            </div>
          </div>
          <div class="az-card__body" v-if="rule.enabled" style="padding:12px 20px;">
            <div style="display:flex;flex-wrap:wrap;gap:16px 32px;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:13px;color:var(--color-text-secondary);min-width:40px;">阈值</span>
                <el-input-number v-model="rule.threshold" :min="1" :max="100000" size="small" @change="updateRule(rule)" />
              </div>
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:13px;color:var(--color-text-secondary);min-width:56px;">窗口(s)</span>
                <el-input-number v-model="rule.window_sec" :min="1" :max="86400" size="small" @change="updateRule(rule)" />
              </div>
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:13px;color:var(--color-text-secondary);min-width:72px;">封禁时长(s)</span>
                <el-input-number v-model="rule.ban_duration_sec" :min="10" :max="2592000" size="small" @change="updateRule(rule)" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 封禁列表 -->
      <div v-if="subtab==='bans'">
        <div class="az-card">
          <div class="az-card__header">
            <span class="az-card__title">当前封禁 IP</span>
            <el-button type="primary" size="small" @click="showBanDialog=true">手动封禁</el-button>
          </div>
          <div class="az-card__body az-card__body--flush">
            <el-table :data="bans" stripe style="width:100%;" empty-text="暂无封禁 IP">
              <el-table-column prop="ip" label="IP 地址" width="160" />
              <el-table-column prop="reason" label="原因" />
              <el-table-column prop="rule_id" label="规则" width="160">
                <template #default="{row}">
                  <el-tag size="small" :type="row.manual ? 'warning' : 'info'">{{ row.rule_id }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="剩余时间" width="130">
                <template #default="{row}">
                  {{ row.remaining_sec < 0 ? '永久' : formatDuration(row.remaining_sec) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{row}">
                  <el-button type="danger" size="small" text @click="unbanIp(row.ip)">解封</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>

      <!-- 手动封禁对话框 -->
      <el-dialog v-model="showBanDialog" title="手动封禁 IP" width="420px">
        <el-form label-width="80px">
          <el-form-item label="IP 地址">
            <el-input v-model="banForm.ip" placeholder="如: 192.168.1.100" />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="banForm.reason" placeholder="封禁原因" />
          </el-form-item>
          <el-form-item label="时长(秒)">
            <el-input-number v-model="banForm.duration_sec" :min="60" :max="2592000" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showBanDialog=false">取消</el-button>
          <el-button type="primary" @click="banIp">确认封禁</el-button>
        </template>
      </el-dialog>
    </div>
  `,
  setup() {
    const subtab = ref('rules');
    const rules = ref([]);
    const bans = ref([]);
    const showBanDialog = ref(false);
    const banForm = ref({ ip: '', reason: '手动封禁', duration_sec: 3600 });

    const loadRules = async () => {
      try {
        const resp = await api.getSecurityRules();
        rules.value = resp.rules || [];
      } catch {}
    };

    const loadBans = async () => {
      try {
        const resp = await api.getSecurityBans();
        bans.value = resp.bans || [];
      } catch {}
    };

    const updateRule = async (rule) => {
      try {
        await api.updateSecurityRule(rule.rule_id, {
          enabled: rule.enabled,
          threshold: rule.threshold,
          window_sec: rule.window_sec,
          ban_duration_sec: rule.ban_duration_sec,
        });
        ElMessage.success('规则已更新');
      } catch {}
    };

    const banIp = async () => {
      if (!banForm.value.ip) { ElMessage.warning('请输入 IP'); return; }
      try {
        await api.banIp(banForm.value);
        ElMessage.success('已封禁');
        showBanDialog.value = false;
        banForm.value = { ip: '', reason: '手动封禁', duration_sec: 3600 };
        await loadBans();
      } catch {}
    };

    const unbanIp = async (ip) => {
      try {
        await ElMessageBox.confirm(`确认解封 ${ip}?`, '确认');
        await api.unbanIp(ip);
        ElMessage.success('已解封');
        await loadBans();
      } catch {}
    };

    const formatDuration = (sec) => {
      if (sec <= 0) return '已过期';
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      if (h > 0) return `${h}h ${m}m`;
      if (m > 0) return `${m}m ${s}s`;
      return `${s}s`;
    };

    onMounted(async () => {
      await Promise.all([loadRules(), loadBans()]);
    });

    return { subtab, rules, bans, showBanDialog, banForm, updateRule, banIp, unbanIp, formatDuration, loadRules, loadBans };
  }
};
