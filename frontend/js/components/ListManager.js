/**
 * ListManager.js — Blacklist / Whitelist management (table-based)
 */
const { ref, computed } = Vue;

export default {
  name: 'ListManager',
  props: ['config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="icons.list"></span>
        黑白名单
      </div>

      <!-- Sub-tabs (Azure pivot) -->
      <div class="az-subtabs">
        <div class="az-subtab" :class="{ 'az-subtab--active': tab === 'black' }" @click="tab='black'">黑名单</div>
        <div class="az-subtab" :class="{ 'az-subtab--active': tab === 'white' }" @click="tab='white'">白名单</div>
      </div>

      <!-- Blacklist -->
      <template v-if="tab === 'black'">
        <div class="az-card">
          <div class="az-card__header">
            <span class="az-card__title">黑名单配置</span>
          </div>
          <div class="az-card__body">
            <el-form label-width="80px" class="az-form" style="margin-bottom:16px;">
              <el-form-item label="模式">
                <el-select v-model="config.blacklist.mode" style="width:200px;" :disabled="config.whitelist.mode !== 'disabled'" @change="onBlacklistModeChange">
                  <el-option label="禁用" value="disabled"></el-option>
                  <el-option label="用户黑名单" value="for_users"></el-option>
                  <el-option label="群聊黑名单" value="for_groups"></el-option>
                </el-select>
                <span class="az-helper" v-if="config.whitelist.mode !== 'disabled'" style="color:var(--color-danger);">白名单已启用，黑名单不可用</span>
              </el-form-item>
            </el-form>

            <template v-if="config.blacklist.mode !== 'disabled'">
              <div class="az-add-row">
                <el-input v-model="blackInput" :placeholder="config.blacklist.mode === 'for_users' ? '输入用户 ID' : '输入群聊 ID'" @keyup.enter="addBlack"></el-input>
                <el-button type="primary" @click="addBlack">确认添加</el-button>
              </div>
              <el-table :data="blackData" border style="width:100%;" empty-text="暂无数据">
                <el-table-column prop="id" label="ID" min-width="200"></el-table-column>
                <el-table-column prop="type" label="类型" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.type==='用户'?'primary':'warning'" size="small">{{ row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" align="center">
                  <template #default="{ row }">
                    <el-button type="danger" link size="small" @click="removeBlack(row.id)">移除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </div>
        </div>
      </template>

      <!-- Whitelist -->
      <template v-if="tab === 'white'">
        <div class="az-card">
          <div class="az-card__header">
            <span class="az-card__title">白名单配置</span>
          </div>
          <div class="az-card__body">
            <el-form label-width="80px" class="az-form" style="margin-bottom:16px;">
              <el-form-item label="模式">
                <el-select v-model="config.whitelist.mode" style="width:200px;" :disabled="config.blacklist.mode !== 'disabled'" @change="onWhitelistModeChange">
                  <el-option label="禁用" value="disabled"></el-option>
                  <el-option label="用户白名单" value="for_users"></el-option>
                  <el-option label="群聊白名单" value="for_groups"></el-option>
                </el-select>
                <span class="az-helper" v-if="config.blacklist.mode !== 'disabled'" style="color:var(--color-danger);">黑名单已启用，白名单不可用</span>
              </el-form-item>
            </el-form>

            <template v-if="config.whitelist.mode !== 'disabled'">
              <div class="az-add-row">
                <el-input v-model="whiteInput" :placeholder="config.whitelist.mode === 'for_users' ? '输入用户 ID' : '输入群聊 ID'" @keyup.enter="addWhite"></el-input>
                <el-button type="primary" @click="addWhite">确认添加</el-button>
              </div>
              <el-table :data="whiteData" border style="width:100%;" empty-text="暂无数据">
                <el-table-column prop="id" label="ID" min-width="200"></el-table-column>
                <el-table-column prop="type" label="类型" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.type==='用户'?'primary':'warning'" size="small">{{ row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" align="center">
                  <template #default="{ row }">
                    <el-button type="danger" link size="small" @click="removeWhite(row.id)">移除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </div>
        </div>
      </template>
    </div>
  `,

  setup(props) {
    const tab = ref('black');
    const blackInput = ref('');
    const whiteInput = ref('');

    const blackData = computed(() => {
      const r = [];
      (props.config.blacklist.users||[]).forEach(id => r.push({ id, type:'用户' }));
      (props.config.blacklist.groups||[]).forEach(id => r.push({ id, type:'群聊' }));
      return r;
    });
    const addBlack = () => {
      const v = blackInput.value.trim(); if (!v) return;
      const l = props.config.blacklist;
      if (l.mode==='for_users') { if (!l.users.includes(v)) l.users.push(v); }
      else if (l.mode==='for_groups') { if (!l.groups.includes(v)) l.groups.push(v); }
      blackInput.value = '';
    };
    const removeBlack = id => {
      const l = props.config.blacklist;
      l.users = l.users.filter(u => u !== id);
      l.groups = l.groups.filter(g => g !== id);
    };

    const whiteData = computed(() => {
      const r = [];
      (props.config.whitelist.users||[]).forEach(id => r.push({ id, type:'用户' }));
      (props.config.whitelist.groups||[]).forEach(id => r.push({ id, type:'群聊' }));
      return r;
    });
    const addWhite = () => {
      const v = whiteInput.value.trim(); if (!v) return;
      const l = props.config.whitelist;
      if (l.mode==='for_users') { if (!l.users.includes(v)) l.users.push(v); }
      else if (l.mode==='for_groups') { if (!l.groups.includes(v)) l.groups.push(v); }
      whiteInput.value = '';
    };
    const removeWhite = id => {
      const l = props.config.whitelist;
      l.users = l.users.filter(u => u !== id);
      l.groups = l.groups.filter(g => g !== id);
    };

    // 黑白名单互斥：启用一个时自动禁用另一个
    const onBlacklistModeChange = (val) => {
      if (val !== 'disabled') {
        props.config.whitelist.mode = 'disabled';
      }
    };
    const onWhitelistModeChange = (val) => {
      if (val !== 'disabled') {
        props.config.blacklist.mode = 'disabled';
      }
    };

    return { tab, blackInput, whiteInput, blackData, whiteData, addBlack, removeBlack, addWhite, removeWhite, onBlacklistModeChange, onWhitelistModeChange };
  }
};
