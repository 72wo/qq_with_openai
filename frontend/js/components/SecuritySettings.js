/**
 * SecuritySettings.js — 密码管理 & 好友验证 Token 生成组件
 */
import api from '/static/js/api.js';
const { ref, computed } = Vue;
const { ElMessage } = ElementPlus;

export default {
  name: 'SecuritySettings',
  props: ['config', 'status', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.lock || icons.settings"></span>
        密码管理
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">修改管理员密码</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="100px" class="az-form" style="max-width:440px;">
            <el-form-item label="当前密码">
              <el-input v-model="form.oldPassword" type="password" show-password placeholder="输入当前密码" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="form.newPassword" type="password" show-password placeholder="至少 8 位" />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input v-model="form.confirmPassword" type="password" show-password placeholder="再次输入新密码" @keyup.enter="changePassword" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading" @click="changePassword">修改密码</el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card" style="margin-top:16px;">
        <div class="az-card__header">
          <span class="az-card__title">会话信息</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="120px" class="az-form" style="max-width:480px;">
            <el-form-item label="会话有效时长">
              <el-select v-model="sessionExpiryHours" placeholder="选择有效时长" style="width:220px;">
                <el-option :value="1"    label="1 小时" />
                <el-option :value="6"    label="6 小时" />
                <el-option :value="12"   label="12 小时" />
                <el-option :value="24"   label="24 小时（默认）" />
                <el-option :value="48"   label="48 小时" />
                <el-option :value="168"  label="7 天" />
                <el-option :value="720"  label="30 天" />
                <el-option :value="0"    label="永不过期" />
              </el-select>
            </el-form-item>
            <div v-if="sessionExpiryHours === 0" style="display:flex;align-items:center;gap:6px;padding:8px 12px;background:var(--color-warning-bg);border:1px solid #e8d44d;border-radius:var(--radius-sm);margin-bottom:16px;">
              <el-icon style="color:#b7950b;flex-shrink:0;" :size="16"><WarningFilled /></el-icon>
              <span style="font-size:12px;color:#8a6d00;line-height:1.3;position:relative;top:1px;">
                永不过期的会话存在安全风险，建议仅在可信环境中使用此选项。
              </span>
            </div>
          </el-form>
        </div>
      </div>

      <div class="az-card" style="margin-top:16px;">
        <div class="az-card__header">
          <span class="az-card__title">好友验证 Token</span>
        </div>
        <div class="az-card__body">
          <p style="font-size:13px;color:var(--color-text-secondary);margin-bottom:16px;">
            输入 QQ 号生成好友验证 Token，用户将此 Token 作为验证消息发送好友请求即可自动通过。
            也可将公开页面 <a href="/token" target="_blank" style="color:var(--color-link);">/token</a> 分享给用户自助获取。
          </p>
          <el-form label-width="120px" class="az-form" style="max-width:480px;">
            <el-form-item label="Token 有效时长">
              <el-select v-model="friendTokenExpiryMinutes" placeholder="选择有效时长" style="width:220px;">
                <el-option :value="5"    label="5 分钟" />
                <el-option :value="10"   label="10 分钟（默认）" />
                <el-option :value="15"   label="15 分钟" />
                <el-option :value="30"   label="30 分钟" />
                <el-option :value="60"   label="1 小时" />
                <el-option :value="120"  label="2 小时" />
                <el-option :value="360"  label="6 小时" />
                <el-option :value="720"  label="12 小时" />
                <el-option :value="1440" label="24 小时" />
              </el-select>
            </el-form-item>
          </el-form>
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <el-form-item label="QQ 号" style="flex: 0; margin-bottom: 0;">
              <el-input v-model="tokenForm.qq" placeholder="输入 QQ 号..." @keyup.enter="generateToken" style="width: 160px;" />
            </el-form-item>
            <el-button type="primary" :loading="tokenLoading" @click="generateToken">生成 Token</el-button>
          </div>
          <el-form-item label="Token" v-if="tokenResult" style="margin-bottom: 0;">
            <div style="display:flex;align-items:center;gap:8px;">
              <el-input :model-value="tokenResult" readonly style="min-width: 350px;" />
              <el-button @click="copyToken" size="small">复制</el-button>
            </div>
          </el-form-item>
        </div>
      </div>
    </div>
  `,
setup(props) {
    const form = ref({ oldPassword: '', newPassword: '', confirmPassword: '' });
    const loading = ref(false);

    // 会话有效时长 — 直接映射到全局 config.advanced.session_expiry_hours，由右上角“保存配置”持久化
    const sessionExpiryHours = computed({
      get() {
        try { return (props.config && props.config.advanced && typeof props.config.advanced.session_expiry_hours !== 'undefined') ? props.config.advanced.session_expiry_hours : 24; }
        catch { return 24; }
      },
      set(v) {
        if (!props.config) props.config = {};
        if (!props.config.advanced) props.config.advanced = {};
        props.config.advanced.session_expiry_hours = v;
      }
    });

    // 好友验证 Token
    const tokenForm = ref({ qq: '' });
    const tokenLoading = ref(false);
    const tokenResult = ref('');

    // 好友验证 Token 有效时长 — 映射到 config.advanced.friend_token_expiry_minutes
    const friendTokenExpiryMinutes = computed({
      get() {
        try { return (props.config && props.config.advanced && typeof props.config.advanced.friend_token_expiry_minutes !== 'undefined') ? props.config.advanced.friend_token_expiry_minutes : 10; }
        catch { return 10; }
      },
      set(v) {
        if (!props.config) props.config = {};
        if (!props.config.advanced) props.config.advanced = {};
        props.config.advanced.friend_token_expiry_minutes = v;
      }
    });

    const changePassword = async () => {
      if (!form.value.oldPassword) { ElMessage.warning('请输入当前密码'); return; }
      if (form.value.newPassword.length < 8) { ElMessage.warning('新密码至少 8 位'); return; }
      if (form.value.newPassword !== form.value.confirmPassword) { ElMessage.warning('两次输入不一致'); return; }

      loading.value = true;
      try {
        await api.changePassword(form.value.oldPassword, form.value.newPassword);
        ElMessage.success('密码修改成功，请重新登录');
        form.value = { oldPassword: '', newPassword: '', confirmPassword: '' };
        // 延迟跳转以显示消息
        setTimeout(() => { window.location.reload(); }, 1500);
      } catch {}
      finally { loading.value = false; }
    };


    const generateToken = async () => {
      const qq = tokenForm.value.qq.trim();
      if (!qq) { ElMessage.warning('请输入 QQ 号'); return; }
      if (!/^[1-9]\d{4,11}$/.test(qq)) { ElMessage.warning('QQ 号格式不正确'); return; }

      tokenLoading.value = true;
      tokenResult.value = '';
      try {
        const resp = await api.generateFriendToken(qq);
        tokenResult.value = resp.token;
        ElMessage.success('Token 已生成');
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || '生成失败');
      } finally {
        tokenLoading.value = false;
      }
    };

    const copyToken = async () => {
      try {
        await navigator.clipboard.writeText(tokenResult.value);
        ElMessage.success('已复制到剪贴板');
      } catch {
        ElMessage.info('请手动复制');
      }
    };

    return { form, loading, changePassword, sessionExpiryHours, friendTokenExpiryMinutes, tokenForm, tokenLoading, tokenResult, generateToken, copyToken };
  }
};
