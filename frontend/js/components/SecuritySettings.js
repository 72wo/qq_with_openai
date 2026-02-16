/**
 * SecuritySettings.js — 密码管理 & 好友验证 Token 生成组件
 */
import api from '/static/js/api.js';
const { ref } = Vue;
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
          <p style="font-size:13px;color:var(--color-text-secondary);margin-bottom:12px;">
            登录会话有效期为 24 小时。修改密码后需要重新登录。
          </p>
          <el-button type="danger" plain @click="logout">退出登录</el-button>
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
  setup() {
    const form = ref({ oldPassword: '', newPassword: '', confirmPassword: '' });
    const loading = ref(false);

    // 好友验证 Token
    const tokenForm = ref({ qq: '' });
    const tokenLoading = ref(false);
    const tokenResult = ref('');

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

    const logout = async () => {
      try {
        await api.logout();
        ElMessage.success('已退出');
        setTimeout(() => { window.location.reload(); }, 500);
      } catch {}
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

    return { form, loading, changePassword, logout, tokenForm, tokenLoading, tokenResult, generateToken, copyToken };
  }
};
