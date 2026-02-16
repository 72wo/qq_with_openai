/**
 * VisionConfig.js — Vision model configuration
 */
import api from '/static/js/api.js';
const { ref } = Vue;

export default {
  name: 'VisionConfig',
  props: ['config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.eye"></span>
        视觉模型配置
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">基本开关</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.vision" label-width="180px" class="az-form">
            <el-form-item label="启用视觉模型">
              <el-switch v-model="config.vision.enabled"></el-switch>
              <span class="az-helper">{{ config.vision.enabled ? '已启用' : '已禁用' }}</span>
            </el-form-item>
            <el-form-item label="使用回复模型配置">
              <el-switch v-model="config.vision.use_reply_config"></el-switch>
              <span class="az-helper">开启后视觉模型复用聊天模型主配置</span>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card" v-if="!config.vision.use_reply_config">
        <div class="az-card__header">
          <span class="az-card__title">独立视觉模型配置</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.vision" label-width="180px" class="az-form">
            <el-form-item label="Base URL">
              <el-input v-model="config.vision.baseurl" placeholder="https://api.openai.com/v1"></el-input>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="config.vision.apikey" type="password" show-password></el-input>
            </el-form-item>
            <el-form-item label="Model">
              <el-input v-model="config.vision.model" placeholder="gpt-4-vision-preview"></el-input>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card" v-if="!config.vision.use_reply_config">
        <div class="az-card__header">
          <span class="az-card__title">连接测试</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="180px" class="az-form">
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
        // 如果视觉模型复用主配置则使用 openai，否则使用 vision
        const cfg = props.config.vision.use_reply_config ? props.config.openai : props.config.vision;
        const d = await api.testConnection({ baseurl: cfg.baseurl, apikey: cfg.apikey, model: cfg.model });
        const ms = Date.now() - start;
        if (d.success) {
          ElMessage.success('连接成功，延迟 ' + ms + 'ms');
          result.value = { show: false, success: true, message: '' };
        } else {
          ElMessage.error('连接失败: ' + d.message);
          result.value = { show: false, success: false, message: '' };
        }
      } catch (e) {
        const errMsg = e.response?.data?.message || e.message || '网络错误';
        ElMessage.error('连接失败: ' + errMsg);
        result.value = { show: false, success: false, message: '' };
      } finally {
        testing.value = false;
      }
    };

    return { testing, result, handleTest };
  }
};
