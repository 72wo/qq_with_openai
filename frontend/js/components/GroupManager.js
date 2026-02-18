/**
 * GroupManager.js — 群聊管理面板
 * 支持加载群列表、前端搜索、退出群聊（含确认）
 */
import api from '/static/js/api.js';

const { ref, computed, onMounted } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export default {
  name: 'GroupManager',
  props: ['status', 'config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="groupIcon"></span>
        群聊管理
      </div>

      <!-- Offline banner -->
      <div v-if="!status.napcat_connected" class="az-status-banner az-status-banner--err">
        <span class="az-status-banner__icon" v-html="icons.errorCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">NapCat 未连接</div>
          <div class="az-status-banner__desc">无法获取群聊列表，请先确保 NapCat 服务在线</div>
        </div>
      </div>

      <div v-else class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">群聊列表 ({{ filteredGroups.length }} / {{ groups.length }})</span>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-input
              v-model="searchText"
              placeholder="搜索群号 / 群名"
              :prefix-icon="Search"
              clearable
              size="small"
              style="width:240px;"
            />
            <el-button size="small" @click="loadGroups" :loading="loading">
              <el-icon><Refresh /></el-icon>
              <span style="margin-left:4px;">刷新</span>
            </el-button>
          </div>
        </div>

        <div class="az-card__body--flush">
          <!-- Loading skeleton -->
          <div v-if="loading" style="padding:20px;">
            <div class="az-skeleton">
              <div class="az-skeleton__block" style="width:100%;height:40px;"></div>
              <div class="az-skeleton__block" style="width:100%;height:40px;"></div>
              <div class="az-skeleton__block" style="width:80%;height:40px;"></div>
            </div>
          </div>

          <!-- Empty state -->
          <div v-else-if="groups.length === 0" style="padding:40px;text-align:center;color:var(--color-text-tertiary);">
            暂无群聊数据
          </div>

          <!-- Group table -->
          <div v-else class="az-friend-table-wrap">
            <table class="az-friend-table">
              <thead>
                <tr>
                  <th style="width:50px;">#</th>
                  <th style="width:140px;">群号</th>
                  <th>群名</th>
                  <th style="width:90px;text-align:center;">成员数</th>
                  <th style="width:90px;text-align:center;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredGroups.length === 0">
                  <td colspan="5" style="text-align:center;color:var(--color-text-tertiary);padding:24px;">
                    未找到匹配的群聊
                  </td>
                </tr>
                <tr v-for="(g, idx) in pagedGroups" :key="g.group_id">
                  <td class="az-friend-table__idx">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
                  <td class="az-friend-table__qq">{{ g.group_id }}</td>
                  <td>{{ g.group_name || '-' }}</td>
                  <td style="text-align:center;">{{ g.member_count ?? '-' }}</td>
                  <td style="text-align:center;">
                    <el-button
                      type="danger"
                      size="small"
                      plain
                      @click="confirmQuit(g)"
                      :loading="quittingId === g.group_id"
                    >退出</el-button>
                  </td>
                </tr>
              </tbody>
            </table>

            <!-- Pagination -->
            <div v-if="filteredGroups.length > pageSize" class="az-friend-pagination">
              <el-pagination
                v-model:current-page="currentPage"
                :page-size="pageSize"
                :total="filteredGroups.length"
                layout="prev, pager, next, total"
                small
                background
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  `,

  setup(props) {
    const groups = ref([]);
    const searchText = ref('');
    const loading = ref(false);
    const quittingId = ref('');
    const currentPage = ref(1);
    const pageSize = 50;

    const groupIcon = `<svg viewBox="0 0 16 16"><circle cx="4.5" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="11.5" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="4" r="2.3" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M1 13c0-2 1.6-3.5 3.5-3.5.4 0 .8.1 1.1.2" fill="none" stroke="currentColor" stroke-width="1.1"/><path d="M10.4 9.7c.3-.1.7-.2 1.1-.2C13.4 9.5 15 11 15 13" fill="none" stroke="currentColor" stroke-width="1.1"/><path d="M4.5 13c0-2 1.6-3.5 3.5-3.5S11.5 11 11.5 13" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>`;

    const filteredGroups = computed(() => {
      const q = searchText.value.trim().toLowerCase();
      if (!q) return groups.value;
      return groups.value.filter(g =>
        g.group_id.includes(q) ||
        (g.group_name && g.group_name.toLowerCase().includes(q))
      );
    });

    const pagedGroups = computed(() => {
      const start = (currentPage.value - 1) * pageSize;
      return filteredGroups.value.slice(start, start + pageSize);
    });

    const { watch } = Vue;
    watch(searchText, () => { currentPage.value = 1; });

    const loadGroups = async () => {
      loading.value = true;
      try {
        const res = await api.getGroupList();
        groups.value = res.groups || [];
        currentPage.value = 1;
      } catch {
        // 全局拦截器已处理
      } finally {
        loading.value = false;
      }
    };

    const confirmQuit = async (group) => {
      const label = group.group_name || group.group_id;
      try {
        await ElMessageBox.confirm(
          `确定要退出群聊 "${label}" (${group.group_id}) 吗？此操作不可撤销。`,
          '确认退出',
          {
            confirmButtonText: '退出',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger',
          }
        );
      } catch {
        return;
      }

      quittingId.value = group.group_id;
      try {
        await api.quitGroup(group.group_id);
        ElMessage.success(`已退出群聊: ${label}`);
        groups.value = groups.value.filter(g => g.group_id !== group.group_id);
      } catch {
        // 全局拦截器已处理
      } finally {
        quittingId.value = '';
      }
    };

    onMounted(() => {
      if (props.status.napcat_connected) {
        loadGroups();
      }
    });

    return {
      groups, searchText, loading, quittingId, currentPage, pageSize,
      groupIcon, filteredGroups, pagedGroups,
      loadGroups, confirmQuit,
      Search: ElementPlusIconsVue.Search,
    };
  }
};
