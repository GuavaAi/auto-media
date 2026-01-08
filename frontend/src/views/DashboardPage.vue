<template>
  <div class="daily-feed-container">
    <!-- 顶部问候与搜索 -->
    <div class="feed-header">
      <h1 class="greeting">今天，创造点什么？</h1>
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="输入主题，AI 帮你写..."
          class="immersive-search"
          :prefix-icon="Search"
          size="large"
          @keyup.enter="enqueueTopicFromInput"
        >
          <template #append>
            <el-button
              ref="generateBtnRef"
              class="premium-generate-btn"
              type="primary"
              :disabled="!searchQuery.trim()"
              @click="enqueueTopicFromInput"
            >
              生成
            </el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 任务队列悬浮按钮: 靠右侧固定 -->
    <div 
      ref="floatingQueueRef"
      class="floating-queue-trigger" 
      :class="{ 'bump-anim': bumpQueue }"
      @click="queueVisible = true"
    >
      <el-badge :value="queue.queuedCount" :hidden="queue.queuedCount === 0" class="queue-badge">
        <div class="queue-fab">
          <el-icon :size="20"><List /></el-icon>
          <span class="fab-text">任务队列</span>
        </div>
      </el-badge>
    </div>

    <!-- 今日热点 -->
    <div class="feed-content">
      <div class="section-title">
        <span>今日灵感</span>
        <span class="date-badge">{{ todayStr }}</span>
        <el-button 
          v-if="!loading && hotspots.length" 
          link 
          type="primary" 
          @click="fetchHotspots"
        >
          刷新
        </el-button>
      </div>

      <div v-if="loading" class="loading-state">
        <AIThinking :steps="['正在获取热点数据...', '分析今日趋势...', '整理推荐内容...']" />
      </div>

      <div v-else-if="!hotspots.length" class="empty-state">
        <el-empty description="今日暂无窗口热点">
          <el-button type="primary" @click="fetchHotspots">生成今日热点</el-button>
        </el-empty>
      </div>

      <div v-else class="cards-grid">
        <div v-for="item in hotspots" :key="itemKey(item)" class="feed-card">
          <div class="card-body">
            <div class="card-meta">
              <span class="hot-score">🔥 {{ item.hot_score?.toFixed(1) || '-' }}</span>
              <span class="source-count">{{ item.source_count }} 个来源</span>
              <el-tag
                v-if="(item.flags || {}).list_parent_fallback"
                size="small"
                type="warning"
                effect="plain"
              >
                聚合页兜底
              </el-tag>
            </div>
            <h3 class="card-title">{{ item.title }}</h3>
            <p class="card-summary">{{ item.summary || '暂无摘要' }}</p>
          </div>
          <div class="card-actions">
            <el-button
              class="action-btn draft-btn"
              type="primary"
              @click="handleQuickDraft(item)"
            >
              ⚡ 一键生成
            </el-button>
            <el-button class="action-btn" plain @click="goDetail(item)">
              查看详情
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 任务队列：不阻塞用户其它操作，后台串行执行 -->
    <el-drawer v-model="queueVisible" title="任务队列" size="420px">
      <div v-if="!queue.tasks.length" class="empty-queue">
        <el-empty description="暂无任务" />
      </div>
      <div v-else class="queue-list">
        <div v-for="t in queue.tasks" :key="t.id" class="queue-item">
          <div class="queue-item-main">
            <div class="queue-item-title">
              <span class="queue-item-label">{{ t.label }}</span>
              <el-tag
                size="small"
                :type="queue.statusTagType(t.status)"
                effect="light"
              >
                {{ queue.statusText(t.status) }}
              </el-tag>
            </div>
            <div v-if="t.errorMessage" class="queue-item-error">{{ t.errorMessage }}</div>
          </div>

          <div class="queue-item-actions">
            <el-button
              v-if="t.status === 'success' && t.articleId"
              size="small"
              type="primary"
              plain
              @click="openArticle(t.articleId)"
            >
              打开文章
            </el-button>
            <el-button
              v-if="t.status === 'failed'"
              size="small"
              @click="queue.retryTask(t.id)"
            >
              重试
            </el-button>
            <el-button
              v-if="t.status !== 'running'"
              size="small"
              type="danger"
              plain
              @click="queue.removeTask(t.id)"
            >
              移除
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { Search, List } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import dayjs from "dayjs";
import { buildWindowHotspots } from "@/api/windowHotspots";
import AIThinking from "@/components/AIThinking.vue";
import type { WindowHotspotEvent } from "@/types";
import { useTaskQueueStore } from "@/stores/taskQueue";

const router = useRouter();
const queue = useTaskQueueStore();
const searchQuery = ref("");
const loading = ref(false);
const hotspots = ref<WindowHotspotEvent[]>([]);
const queueVisible = ref(false);

const generateBtnRef = ref<HTMLElement | null>(null);
const floatingQueueRef = ref<HTMLElement | null>(null);
const bumpQueue = ref(false);

const startFlyAnimation = () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const btnEl = (generateBtnRef.value as any)?.$el;
  if (!btnEl || !floatingQueueRef.value) return;

  const startRect = btnEl.getBoundingClientRect();
  const endRect = floatingQueueRef.value.getBoundingClientRect();

  // 创建飞行元素
  const flyer = document.createElement("div");
  flyer.textContent = "✨";
  flyer.style.position = "fixed";
  flyer.style.left = `${startRect.right - 40}px`;
  flyer.style.top = `${startRect.top + 10}px`;
  flyer.style.zIndex = "9999";
  flyer.style.fontSize = "20px";
  flyer.style.pointerEvents = "none";
  flyer.style.transition = "all 0.8s cubic-bezier(0.19, 1, 0.22, 1)";
  flyer.style.opacity = "1";
  flyer.style.transform = "scale(1)";

  document.body.appendChild(flyer);

  // 下一帧开始动画
  requestAnimationFrame(() => {
    flyer.style.left = `${endRect.left + 15}px`;
    flyer.style.top = `${endRect.top + 10}px`;
    flyer.style.opacity = "0";
    flyer.style.transform = "scale(0.5)";
  });

  // 动画结束清理
  flyer.addEventListener("transitionend", () => {
    if (flyer.parentNode) {
      flyer.parentNode.removeChild(flyer);
    }
    // 触发队列图标弹跳
    bumpQueue.value = true;
    setTimeout(() => {
      bumpQueue.value = false;
    }, 300);
  });
};

const todayStr = computed(() => dayjs().format("YYYY-MM-DD"));

const fetchHotspots = async () => {
  loading.value = true;
  try {
    const res = await buildWindowHotspots({
      window: "today",
      limit: 10,
      use_llm: false,
    });
    hotspots.value = res.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "加载今日热点失败");
  } finally {
    loading.value = false;
  }
};

const handleQuickDraft = (item: WindowHotspotEvent) => {
  // 中文说明：窗口热点没有数据库 ID，一键生成改为按标题主题入队
  queue.enqueueTopic(item.title);
};

const goDetail = (item: WindowHotspotEvent) => {
  const key = itemKey(item);
  try {
    sessionStorage.setItem(`window_hotspot_detail:${key}`, JSON.stringify(item));
  } catch {
    // ignore
  }
  router.push({
    path: `/window-hotspots/${encodeURIComponent(key)}`,
    query: { window: "today" },
  });
};

const itemKey = (row: WindowHotspotEvent) => {
  const t = (row?.title || "").trim();
  const te = (row?.event_time_end || "").trim();
  const u = ((row?.sources || [])[0]?.url || "").trim();
  return `${row.window || "today"}|${t}|${te}|${u}`;
};

const openArticle = (articleId: number) => {
  router.push(`/articles/${articleId}`);
};

const enqueueTopicFromInput = () => {
  const q = searchQuery.value.trim();
  if (!q) return;

  // 触发动画
  startFlyAnimation();

  queue.enqueueTopic(q);
  searchQuery.value = "";
};

onMounted(() => {
  fetchHotspots();
});
</script>

<style scoped>
.daily-feed-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 20px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", Roboto, sans-serif;
}

/* 头部 */
.feed-header {
  text-align: center;
  margin-bottom: 50px;
  animation: fadeIn 0.8s ease-out;
}

.greeting {
  font-size: 42px;
  font-weight: 800;
  background: linear-gradient(120deg, #1a1a1a 0%, #555 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 28px;
  letter-spacing: -1px;
}

/* 搜索栏与生成按钮 */
.search-bar {
  max-width: 600px;
  margin: 0 auto;
}

:deep(.immersive-search) {
  --el-input-height: 54px; /* 定义一个基准高度 */
}

:deep(.immersive-search .el-input__wrapper) {
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  height: var(--el-input-height) !important;
  padding-right: 0 !important;
}

:deep(.immersive-search .el-input-group__append) {
  background-color: transparent !important;
  border: none !important;
  padding: 0 !important;
  border-radius: 0 20px 20px 0 !important;
  overflow: hidden;
  box-shadow: 4px 4px 16px rgba(0, 0, 0, 0.06);
  margin-left: -1px; /* 消除微小缝隙 */
}

.premium-generate-btn {
  background: linear-gradient(135deg, #1a1a1a 0%, #434343 100%) !important;
  border: none !important;
  color: white !important;
  font-weight: 600 !important;
  padding: 0 30px !important;
  height: var(--el-input-height) !important; /* 强制与输入框高度一致 */
  border-radius: 0 20px 20px 0 !important;
  transition: all 0.3s ease !important;
  margin: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

.premium-generate-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateX(2px);
}

.premium-generate-btn:disabled {
  background: #ccc !important;
  cursor: not-allowed;
}

/* 悬浮任务队列按钮 */
.floating-queue-trigger {
  position: fixed;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1000;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.bump-anim {
  animation: bump 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes bump {
  0% { transform: translateY(-50%) scale(1); }
  50% { transform: translateY(-50%) scale(1.2); }
  100% { transform: translateY(-50%) scale(1); }
}

.queue-fab {
  background: #fff;
  padding: 12px 8px;
  border-radius: 12px 0 0 12px;
  box-shadow: -4px 0 15px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-right: none;
  width: 44px;
  transition: width 0.3s;
  overflow: hidden;
  white-space: nowrap;
}

.fab-text {
  font-size: 12px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  color: #1a1a1a;
  font-weight: 500;
  letter-spacing: 2px;
}

.floating-queue-trigger:hover {
  transform: translateY(-50%) translateX(-5px);
}

.floating-queue-trigger:hover .queue-fab {
  background: #1a1a1a;
}

.floating-queue-trigger:hover .fab-text,
.floating-queue-trigger:hover :deep(.el-icon) {
  color: #fff;
}

.queue-badge :deep(.el-badge__content) {
  top: 5px;
  right: 5px;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.queue-item {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.queue-item-main {
  flex: 1;
  min-width: 0;
}

.queue-item-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.queue-item-label {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.queue-item-error {
  margin-top: 6px;
  font-size: 12px;
  color: #d93026;
  line-height: 1.4;
  word-break: break-all;
}

.queue-item-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.immersive-search .el-input__wrapper) {
  border-radius: 20px;
  padding: 0 20px;
  transition: all 0.3s ease;
}

:deep(.immersive-search.is-focus .el-input__wrapper) {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

:deep(.immersive-search .el-input__inner) {
  font-size: 16px;
  height: 100%; /* 显式设置高度，确保 wrapper 撑开 */
}

/* 内容区 */
.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.date-badge {
  font-size: 13px;
  font-weight: 500;
  color: #888;
  background: #f5f5f5;
  padding: 4px 12px;
  border-radius: 10px;
}

/* 卡片 */
.cards-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

.feed-card {
  background: #fff;
  border-radius: 14px;
  padding: 22px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feed-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.06);
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #888;
  font-weight: 500;
}

.hot-score {
  color: #ff6b6b;
}

.card-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
  line-height: 1.4;
}

.card-summary {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  display: -webkit-box;
  overflow: hidden;
}

.card-actions {
  display: flex;
  gap: 10px;
  margin-top: auto;
}

.action-btn {
  border-radius: 8px;
  font-weight: 600;
  padding: 10px 20px;
  height: 40px;
}

.draft-btn {
  background: #1a1a1a;
  border-color: #1a1a1a;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  transition: all 0.25s;
}

.draft-btn:hover {
  background: #333;
  border-color: #333;
  transform: scale(1.02);
}

/* 快捷入口 */
.quick-links {
  margin-top: 40px;
}

.quick-card {
  border-radius: 12px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.quick-item:hover {
  background: #f9fafb;
}

.quick-icon {
  font-size: 28px;
}

.quick-label {
  font-size: 14px;
  color: #555;
  font-weight: 500;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .greeting { font-size: 32px; }
  .feed-card { padding: 18px; }
  .quick-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
