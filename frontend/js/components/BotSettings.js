/**
 * BotSettings.js — Bot customization (Azure blade sections)
 */

export default {
  name: 'BotSettings',
  props: ['config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.settings"></span>
        自定义设置
      </div>

      <!-- System Prompt -->
      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">System Prompt</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.bot" label-position="top" class="az-form" style="max-width:100%;">
            <el-form-item label="系统提示词" class="az-form-item--block">
              <el-input v-model="config.bot.prompt" type="textarea" :rows="5" resize="vertical" placeholder="定义 AI 的人设与行为逻辑..."></el-input>
              <span class="az-helper">决定 AI 的说话语气、角色设定及回复逻辑</span>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- Basic settings -->
      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">基础设置</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="160px" class="az-form">
            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="自动回复">
                  <el-switch v-model="config.bot.auto_reply"></el-switch>
                  <span class="az-helper">开启后自动响应收到的消息</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="群聊仅@时回复">
                  <el-switch v-model="config.bot.group_only_at"></el-switch>
                  <span class="az-helper">{{ config.bot.group_only_at ? '被 @ 时触发回复' : '群聊不回复任何消息' }}</span>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="48" v-if="config.bot.group_only_at">
              <el-col :span="12">
                <el-form-item label="@所有人时也回复">
                  <el-switch v-model="config.bot.group_reply_at_all"></el-switch>
                  <span class="az-helper">开启后群聊 @所有人 也会触发回复</span>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
      </div>

      <!-- Feature toggles -->
      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">功能开关</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="160px" class="az-form">
            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="图像识别处理">
                  <el-switch v-model="config.features.image_processing" :disabled="!config.vision.enabled" @change="onImageProcessingChange"></el-switch>
                  <span class="az-helper">{{ config.vision.enabled ? '处理图片消息并识别内容' : '需先启用视觉模型' }}</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="表情转义">
                  <el-switch v-model="config.features.emotion_conversion"></el-switch>
                  <span class="az-helper">将用户发送的 QQ 表情转换为文字供 AI 理解</span>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="模拟人工打字">
                  <el-switch v-model="config.features.simulate_typing_enabled"></el-switch>
                  <span class="az-helper">模拟真实用户的打字延迟效果</span>
                </el-form-item>
              </el-col>
            </el-row>

            <template v-if="config.features.simulate_typing_enabled">
              <el-form-item label="打字速度倍率">
                <el-input-number class="typing-multiplier-input" v-model="config.features.typing_multiplier" :min="0.2" :max="3" :step="0.1" controls-position="right"></el-input-number>
                <span class="az-helper">调整打字速度，数值越大打字越快</span>
              </el-form-item>
            </template>
          </el-form>
        </div>
      </div>

      <!-- Context & Memory -->
      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">上下文与记忆</span>
        </div>
        <div class="az-card__body">
          <el-form label-width="180px" class="az-form">
            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="启用上下文">
                  <el-switch v-model="config.features.context_enabled"></el-switch>
                  <span class="az-helper">保留历史对话以提供连贯的回复</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="启用上下文压缩">
                  <el-switch v-model="config.features.context_compression_enabled"></el-switch>
                  <span class="az-helper">旧对话压缩为摘要而非丢弃</span>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="上下文回溯条数">
                  <el-input-number class="typing-multiplier-input" v-model="config.features.context_max_messages" :min="1" :max="200" controls-position="right"></el-input-number>
                  <span class="az-helper">保留的历史对话轮数</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="单条消息建议长度">
                  <el-input-number class="typing-multiplier-input" v-model="config.features.context_message_max_chars" :min="0" :max="5000" :value-on-clear="0" placeholder="0" controls-position="right"></el-input-number>
                  <span class="az-helper">建议 AI 回复的字符数，0 表示不限制</span>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="48">
              <el-col :span="12">
                <el-form-item label="图片缓存大小 (MB)">
                  <el-input-number class="typing-multiplier-input" v-model="config.features.image_context_cache_size" :min="10" :max="500" controls-position="right"></el-input-number>
                  <span class="az-helper">图片上下文缓存限制</span>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
      </div>
    </div>
  `,
  setup(props) {
    // 视觉模型未启用时强制关闭图像处理
    const onImageProcessingChange = (val) => {
      if (!props.config.vision.enabled) {
        props.config.features.image_processing = false;
      }
    };

    return { onImageProcessingChange };
  }
};
