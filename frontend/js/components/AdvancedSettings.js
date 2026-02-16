/**
 * AdvancedSettings.js — System advanced settings
 */
export default {
  name: 'AdvancedSettings',
  props: ['config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.advanced"></span>
        高级设置
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">网络与认证</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.advanced" label-width="160px" class="az-form">
            <el-form-item label="NapCat Token">
              <el-input v-model="config.advanced.napcat_token" type="password" show-password placeholder="与 NapCat 配置保持一致" style="max-width:280px;"></el-input>
              <span class="az-helper">用于 WebSocket 鉴权，需与 NapCat 端一致</span>
            </el-form-item>
            <el-form-item label="本地服务端口">
              <el-input-number v-model="config.advanced.service_port" :min="1024" :max="65535" controls-position="right"></el-input-number>
              <span class="az-helper">控制台与 NapCat 服务所监听的端口</span>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">日志配置</span>
        </div>
        <div class="az-card__body">
          <el-form :model="config.advanced" label-width="160px" class="az-form">
            <el-form-item label="日志级别">
              <el-select v-model="config.advanced.log_level" style="width:180px;">
                <el-option label="DEBUG" value="DEBUG"></el-option>
                <el-option label="INFO" value="INFO"></el-option>
                <el-option label="WARNING" value="WARNING"></el-option>
                <el-option label="ERROR" value="ERROR"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="日志最大条数">
              <el-input-number v-model="config.advanced.log_max_length" :min="20" :max="2000" controls-position="right"></el-input-number>
              <span class="az-helper">活动日志保留的最大条数</span>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  `,
  setup() { return {}; }
};
