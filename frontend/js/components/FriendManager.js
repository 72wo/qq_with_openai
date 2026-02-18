/**
 * FriendManager.js — 好友管理面板
 * 支持高性能加载好友列表、前端搜索、删除好友（含确认）
 */
import api from '/static/js/api.js';

const { ref, computed, onMounted } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

export default {
  name: 'FriendManager',
  props: ['status', 'config', 'icons'],
  template: `
    <div>
      <div class="az-page-title">
        <span class="az-page-title__icon" v-html="friendIcon"></span>
        好友管理
      </div>

      <!-- Offline banner -->
      <div v-if="!status.napcat_connected" class="az-status-banner az-status-banner--err">
        <span class="az-status-banner__icon" v-html="icons.errorCircle"></span>
        <div class="az-status-banner__text">
          <div class="az-status-banner__title">NapCat 未连接</div>
          <div class="az-status-banner__desc">无法获取好友列表，请先确保 NapCat 服务在线</div>
        </div>
      </div>

      <div v-else class="az-card">
        <div class="az-card__header">
          <span class="az-card__title">好友列表 ({{ filteredFriends.length }} / {{ friends.length }})</span>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-input
              v-model="searchText"
              placeholder="搜索 QQ号 / 昵称 / 备注"
              :prefix-icon="Search"
              clearable
              size="small"
              style="width:240px;"
            />
            <el-button size="small" @click="loadFriends" :loading="loading">
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
          <div v-else-if="friends.length === 0" style="padding:40px;text-align:center;color:var(--color-text-tertiary);">
            暂无好友数据
          </div>

          <!-- Friend table -->
          <div v-else class="az-friend-table-wrap">
            <table class="az-friend-table">
              <thead>
                <tr>
                  <th style="width:50px;">#</th>
                  <th style="width:140px;">QQ 号</th>
                  <th>昵称</th>
                  <th>备注</th>
                  <th style="width:90px;text-align:center;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredFriends.length === 0">
                  <td colspan="5" style="text-align:center;color:var(--color-text-tertiary);padding:24px;">
                    未找到匹配的好友
                  </td>
                </tr>
                <tr v-for="(f, idx) in pagedFriends" :key="f.user_id">
                  <td class="az-friend-table__idx">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
                  <td class="az-friend-table__qq">{{ f.user_id }}</td>
                  <td>{{ f.nickname || '-' }}</td>
                  <td>{{ f.remark || '-' }}</td>
                  <td style="text-align:center;">
                    <el-button
                      type="danger"
                      size="small"
                      plain
                      @click="confirmDelete(f)"
                      :loading="deletingId === f.user_id"
                    >删除</el-button>
                  </td>
                </tr>
              </tbody>
            </table>

            <!-- Pagination -->
            <div v-if="filteredFriends.length > pageSize" class="az-friend-pagination">
              <el-pagination
                v-model:current-page="currentPage"
                :page-size="pageSize"
                :total="filteredFriends.length"
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
    const friends = ref([]);
    const searchText = ref('');
    const loading = ref(false);
    const deletingId = ref('');
    const currentPage = ref(1);
    const pageSize = 50;

    const friendIcon = `<svg viewBox="0 0 16 16"><circle cx="6" cy="4.5" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M1 13c0-2.8 2.2-5 5-5s5 2.2 5 5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M11 6.5a2 2 0 110-4" fill="none" stroke="currentColor" stroke-width="1.1"/><path d="M12 8c1.7 0 3 1.3 3.5 3" fill="none" stroke="currentColor" stroke-width="1.1"/></svg>`;

    const filteredFriends = computed(() => {
      const q = searchText.value.trim().toLowerCase();
      if (!q) return friends.value;
      return friends.value.filter(f =>
        f.user_id.includes(q) ||
        (f.nickname && f.nickname.toLowerCase().includes(q)) ||
        (f.remark && f.remark.toLowerCase().includes(q))
      );
    });

    const pagedFriends = computed(() => {
      const start = (currentPage.value - 1) * pageSize;
      return filteredFriends.value.slice(start, start + pageSize);
    });

    // 搜索变化时重置页码
    const resetPage = () => { currentPage.value = 1; };

    const loadFriends = async () => {
      loading.value = true;
      try {
        const res = await api.getFriendList();
        friends.value = res.friends || [];
        currentPage.value = 1;
      } catch (e) {
        // api.js 全局拦截器已处理错误提示
      } finally {
        loading.value = false;
      }
    };

    const confirmDelete = async (friend) => {
      const label = friend.remark || friend.nickname || friend.user_id;
      try {
        await ElMessageBox.confirm(
          `确定要删除好友 "${label}" (${friend.user_id}) 吗？此操作不可撤销。`,
          '确认删除',
          {
            confirmButtonText: '删除',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger',
          }
        );
      } catch {
        return; // 用户取消
      }

      deletingId.value = friend.user_id;
      try {
        await api.deleteFriend(friend.user_id);
        ElMessage.success(`已删除好友: ${label}`);
        // 从本地列表移除，避免重新加载全量数据
        friends.value = friends.value.filter(f => f.user_id !== friend.user_id);
      } catch {
        // 错误由全局拦截器处理
      } finally {
        deletingId.value = '';
      }
    };

    // 监听搜索变化重置页码
    const { watch } = Vue;
    watch(searchText, resetPage);

    onMounted(() => {
      if (props.status.napcat_connected) {
        loadFriends();
      }
    });

    return {
      friends, searchText, loading, deletingId, currentPage, pageSize,
      friendIcon, filteredFriends, pagedFriends,
      loadFriends, confirmDelete,
      Search: ElementPlusIconsVue.Search,
    };
  }
};
