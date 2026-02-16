/**
 * token-app.js — 好友验证 Token 页面 Vue 应用
 */
const { createApp, ref } = Vue;
const { ElMessage } = ElementPlus;

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
});

const TokenApp = {
  setup() {
    const qqNumber = ref('');
    const token = ref('');
    const error = ref('');
    const loading = ref(false);

    const generate = async () => {
      error.value = '';
      token.value = '';
      const qq = qqNumber.value.trim();
      if (!qq) { error.value = '请输入 QQ 号'; return; }
      if (!/^[1-9]\d{4,11}$/.test(qq)) { error.value = 'QQ 号为 5-12 位数字且不以 0 开头'; return; }

      loading.value = true;
      try {
        const resp = await http.post('/friend/generate-token', { qq_number: qq });
        token.value = resp.data.token;
      } catch (e) {
        error.value = e.response?.data?.detail || e.message || '生成失败';
      } finally {
        loading.value = false;
      }
    };

    const copyToken = async () => {
      try {
        await navigator.clipboard.writeText(token.value);
        ElMessage.success('已复制到剪贴板');
      } catch {
        ElMessage.info('请手动复制');
      }
    };

    return { qqNumber, token, error, loading, generate, copyToken };
  }
};

const app = createApp(TokenApp);
app.use(ElementPlus);
app.mount('#token-app');
