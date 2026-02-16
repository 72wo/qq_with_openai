/**
 * api.js — Axios 封装
 */
const { ElMessage } = ElementPlus;

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

http.interceptors.response.use(
  (r) => r,
  (error) => {
    const msg = error.response?.data?.detail
      || error.response?.data?.message
      || error.message
      || '网络异常';
    ElMessage.error(msg);
    return Promise.reject(error);
  }
);

const api = {
  getConfig()          { return http.get('/config').then(r => r.data); },
  saveConfig(data)     { return http.post('/config', data).then(r => r.data); },
  testConnection(p)    { return http.post('/test-connection', p).then(r => r.data); },
  getStatus()          { return http.get('/status').then(r => r.data); },
  clearLogs()          { return http.post('/logs/clear').then(r => r.data); }
};

export default api;
