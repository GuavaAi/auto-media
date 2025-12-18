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
          :disabled="isSearching"
          @keyup.enter="handleSearch"
        />
      </div>
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

      <!-- Active Inspiration Loading Overlay -->
      <el-dialog
        v-model="isSearching"
        :show-close="false"
        :close-on-click-modal="false"
        :close-on-press-escape="false"
        width="30%"
        center
        align-center
        style="background: transparent; box-shadow: none;"
      >
        <div style="background: white; border-radius: 16px; padding: 20px;">
          <AIThinking :steps="['正在全网搜索素材...', '阅读相关报道...', '提取核心观点...', '构建文章框架...', '生成初稿...']" />
        </div>
      </el-dialog>

      <div v-if="loading" class="loading-state">
        <AIThinking :steps="['正在获取热点数据...', '分析今日趋势...', '整理推荐内容...']" />
      </div>

      <div v-else-if="!hotspots.length" class="empty-state">
        <el-empty description="今日暂无热点榜单">
          <el-button type="primary" @click="buildToday">生成今日榜单</el-button>
        </el-empty>
      </div>

      <div v-else class="cards-grid">
        <div v-for="item in hotspots" :key="item.id" class="feed-card">
          <div class="card-body">
            <div class="card-meta">
              <span class="hot-score">🔥 {{ item.hot_score?.toFixed(1) || '-' }}</span>
              <span class="source-count">{{ item.source_count }} 个来源</span>
            </div>
            <h3 class="card-title">{{ item.title }}</h3>
            <p class="card-summary">{{ item.summary }}</p>
          </div>
          <div class="card-actions">
            <el-button 
              class="action-btn draft-btn" 
              type="primary" 
              :loading="generatingId === item.id"
              @click="handleQuickDraft(item)"
            >
              {{ generatingId === item.id ? '正在生成...' : '⚡ 一键生成' }}
            </el-button>
            <el-button class="action-btn" plain @click="goDetail(item.id)">
              查看详情
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { Search } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import dayjs from "dayjs";
import { listDailyHotspots, buildDailyHotspots, quickGenerateFromEvent, quickGenerateFromTopic } from "@/api/dailyHotspots";
import AIThinking from "@/components/AIThinking.vue";
import type { DailyHotspotEventOut } from "@/types";

const router = useRouter();
const searchQuery = ref("");
const loading = ref(false);
const hotspots = ref<DailyHotspotEventOut[]>([]);
const generatingId = ref<number | null>(null);
const isSearching = ref(false);

const todayStr = computed(() => dayjs().format("YYYY-MM-DD"));

const fetchHotspots = async () => {
  loading.value = true;
  try {
    const res = await listDailyHotspots(todayStr.value, 10);
    hotspots.value = res.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "加载热点失败");
  } finally {
    loading.value = false;
  }
};

const buildToday = async () => {
  loading.value = true;
  try {
    await buildDailyHotspots(todayStr.value, 20);
    ElMessage.success("榜单生成成功");
    await fetchHotspots();
  } catch (err: any) {
    const msg = err?.message || "生成榜单失败";

    // 中文说明：当日没有可用采集数据时，引导运营同学直接去“数据源管理”触发抓取
    if (typeof msg === "string" && msg.includes("当日无可用采集数据")) {
      loading.value = false;
      try {
        await ElMessageBox.confirm(
          "今天还没有可用采集数据，是否现在前往“数据源管理”去采集？",
          "需要先采集数据",
          {
            confirmButtonText: "去采集",
            cancelButtonText: "取消",
            type: "warning",
          }
        );
        router.push("/datasources");
      } catch {
        // 用户取消时不做处理
      }
      return;
    }

    ElMessage.error(msg);
  }
  finally {
    loading.value = false;
  }
};

const handleQuickDraft = async (item: DailyHotspotEventOut) => {
  generatingId.value = item.id;
  try {
    ElMessage.info("AI 正在阅读素材、构思文章...");
    const article = await quickGenerateFromEvent(item.id);
    ElMessage.success("草稿已生成！");
    router.push(`/articles/${article.id}`);
  } catch (err: any) {
    ElMessage.error(err.message || "生成失败");
  } finally {
    generatingId.value = null;
  }
};

const goDetail = (id: number) => {
  router.push(`/daily-hotspots/${id}`);
};

const handleSearch = async () => {
  const q = searchQuery.value.trim();
  if (!q) return;
  
  isSearching.value = true;
  try {
    // 场景 B: Active Inspiration
    // 实时联网搜索 -> 生成
    const article = await quickGenerateFromTopic(q);
    ElMessage.success("灵感生成成功！");
    router.push(`/articles/${article.id}`);
  } catch (err: any) {
    ElMessage.error(err.message || "生成失败，请重试");
    isSearching.value = false;
  }
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
  -webkit-text-fill-color: transparent;
  margin-bottom: 28px;
  letter-spacing: -1px;
}

.search-bar {
  max-width: 560px;
  margin: 0 auto;
}

:deep(.immersive-search .el-input__wrapper) {
  border-radius: 20px;
  padding: 8px 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

:deep(.immersive-search .el-input__wrapper:hover),
:deep(.immersive-search.is-focus .el-input__wrapper) {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

:deep(.immersive-search .el-input__inner) {
  font-size: 16px;
  height: 44px;
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
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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
