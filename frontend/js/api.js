/**
 * api.js — Axios 封装
 */
const { ElMessage } = ElementPlus;

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

// 401 拦截器：未登录/过期时触发全局事件
let _on401 = null;
export function onUnauthorized(cb) { _on401 = cb; }

http.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status;
    // 401 且非登录/check 端点 → 触发回调
    const url = error.config?.url || '';
    // 对于登录/检查端点：让调用者自行处理所有错误（比如 401/422），不显示全局提示
    if (url.includes('/auth/login') || url.includes('/auth/check')) {
      return Promise.reject(error);
    }

    // 对于所有 401 响应：非登录/检查端点时触发全局未授权回调处理（不在这里显示消息）
    if (status === 401) {
      if (_on401) _on401();
      return Promise.reject(error);
    }

    const msg = error.response?.data?.detail
      || error.response?.data?.message
      || error.message
      || '网络异常';
    ElMessage.error(msg);
    return Promise.reject(error);
  }
);

const api = {
  // ── 认证 ──
  login(password)                    { return http.post('/auth/login', { password }).then(r => r.data); },
  logout()                           { return http.post('/auth/logout').then(r => r.data); },
  checkAuth()                        { return http.get('/auth/check').then(r => r.data).catch(() => ({ authenticated: false })); },
  changePassword(old_password, new_password) {
    return http.post('/auth/change-password', { old_password, new_password }).then(r => r.data);
  },

  // ── 配置 ──
  getConfig()          { return http.get('/config').then(r => r.data); },
  saveConfig(data)     { return http.post('/config', data).then(r => r.data); },
  testConnection(p)    { return http.post('/test-connection', p).then(r => r.data); },
  getStatus()          { return http.get('/status').then(r => r.data); },
  clearLogs()          { return http.post('/logs/clear').then(r => r.data); },

  // ── 安全 ──
  getSecurityRules()               { return http.get('/security/rules').then(r => r.data); },
  updateSecurityRule(ruleId, data)  { return http.put(`/security/rules/${ruleId}`, data).then(r => r.data); },
  getSecurityBans()                { return http.get('/security/bans').then(r => r.data); },
  banIp(data)                      { return http.post('/security/bans', data).then(r => r.data); },
  unbanIp(ip)                      { return http.delete(`/security/bans/${ip}`).then(r => r.data); },


  // ── 好友验证 ──
  generateFriendToken(qq_number)   { return http.post('/friend/generate-token', { qq_number }).then(r => r.data); },
};

export default api;
