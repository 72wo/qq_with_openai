/**
 * VisionConfig.js — Vision model configuration
 */
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
              <span class="az-helper">开启后视觉模型复用 OpenAI 主配置</span>
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
    </div>
  `,
  setup() { return {}; }
};
