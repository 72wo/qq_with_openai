/**
 * OpenAIConfig.js — Chat model configuration (Azure blade style)
 */
import api from '/static/js/api.js';
const { ref } = Vue;

export default {
  name: 'OpenAIConfig',
  props: ['config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.openai"></span>
        聊天模型配置
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">API 连接设置</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.openai" label-width="140px" class="az-form">
            <el-form-item label="Base URL">
              <el-input v-model="config.openai.baseurl" placeholder="https://api.openai.com/v1"></el-input>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="config.openai.apikey" type="password" show-password></el-input>
            </el-form-item>
            <el-form-item label="Model">
              <el-input v-model="config.openai.model" placeholder="gpt-4"></el-input>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">回复参数</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="140px" class="az-form">
            <el-form-item label="平均回复长度">
              <el-input-number v-model="config.openai.reply_avg_length" :min="10" :max="2000" controls-position="right"></el-input-number>
              <span class="az-helper">影响 AI 每次回复的平均字数</span>
            </el-form-item>
            <el-form-item label="最大回复 Token">
              <el-input-number v-model="config.openai.max_tokens" :min="10" :max="4096" controls-position="right"></el-input-number>
              <span class="az-helper">单次回复允许的最大 Token 数量</span>
            </el-form-item>
            <el-form-item label="回复超时 (秒)">
              <el-input-number v-model="config.openai.reply_timeout_sec" :min="5" :max="300" controls-position="right"></el-input-number>
              <span class="az-helper">等待 AI 回复的最长时间</span>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">连接测试</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="140px" class="az-form">
            <el-form-item label="测试连接">
              <el-button type="primary" @click="handleTest" :loading="testing">测试连接</el-button>
              <div class="az-test-result" :class="{ show: result.show, success: result.success, error: !result.success }">
                {{ result.message }}
              </div>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  `,

  setup(props) {
    const testing = ref(false);
    const result = ref({ show: false, success: false, message: '' });
    const { ElMessage } = ElementPlus;

    const handleTest = async () => {
      testing.value = true;
      result.value.show = false;
      try {
        const start = Date.now();
        const d = await api.testConnection({ baseurl: props.config.openai.baseurl, apikey: props.config.openai.apikey, model: props.config.openai.model });
        const ms = Date.now() - start;
        if (d.success) {
          // 成功用 toast 提示，避免按钮下沉
          ElMessage.success('连接成功，延迟 ' + ms + 'ms');
          result.value = { show: false, success: true, message: '' };
        } else {
          // 失败使用 toast 提示，隐藏内联错误显示
          ElMessage.error('连接失败: ' + d.message);
          result.value = { show: false, success: false, message: '' };
        }
      } catch (e) {
        const errMsg = e.response?.data?.message || e.message || '网络错误';
        ElMessage.error('连接失败: ' + errMsg);
        result.value = { show: false, success: false, message: '' };
      } finally { testing.value = false; }
    };

    return { testing, result, handleTest };
  }
};
