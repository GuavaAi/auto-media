<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <div class="nav-row">
          <el-button link @click="router.back()" class="back-btn">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </el-button>
        </div>
        <h2 class="page-title">{{ article?.title || "加载中..." }}</h2>
        <div class="meta-row" v-if="article">
          <el-tag size="small" effect="plain" type="info">{{ article.created_at }}</el-tag>
          <span class="separator">·</span>
          <span class="summary">{{ article.summary || "暂无摘要" }}</span>
        </div>
      </div>
      <div class="header-actions">
        <el-button @click="copyText(article?.content_md || '')">
          <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
          复制 Markdown
        </el-button>
        <el-button type="primary" @click="copyHtml(article?.content_html || '')">
          <el-icon class="el-icon--left"><CopyDocument /></el-icon>
          复制 HTML
        </el-button>

        <el-button type="warning" @click="openPublish" :disabled="!article?.id">
          一键发布
        </el-button>

        <el-button type="success" @click="goEdit" :disabled="!article?.id">
          编辑
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <el-skeleton v-if="loading" :rows="10" animated />
      <div v-else-if="article" class="article-body">
        <div class="source-refs" v-if="article.material_pack_id">
          <span class="label">素材包：</span>
          <div class="tags">
            <el-tag size="small" type="success" effect="light">
              #{{ article.material_pack_id }}
            </el-tag>
          </div>
        </div>

        <div class="source-refs" v-if="article.material_refs">
          <span class="label">素材引用：</span>
          <div class="tags">
            <el-tag
              v-for="(id, idx) in materialItemIdsToShow"
              :key="`mi-${idx}-${id}`"
              size="small"
              type="info"
              effect="light"
            >
              item#{{ id }}
            </el-tag>
            <el-tag
              v-for="(eid, idx) in materialEventIdsToShow"
              :key="`me-${idx}-${eid}`"
              size="small"
              type="warning"
              effect="light"
            >
              event#{{ eid }}
            </el-tag>
            <el-tag
              v-for="(cid, idx) in materialContentIdsToShow"
              :key="`mc-${idx}-${cid}`"
              size="small"
              type="warning"
              effect="light"
            >
              content#{{ cid }}
            </el-tag>

            <el-button
              v-if="materialRefsHasMore"
              link
              type="primary"
              size="small"
              class="toggle-btn"
              @click="materialRefsExpanded = !materialRefsExpanded"
            >
              {{ materialRefsExpanded ? '收起' : '展开查看全部' }}
            </el-button>
          </div>
          <div class="links" v-if="materialSourceUrlsToShow.length">
            <a
              v-for="(u, idx) in materialSourceUrlsToShow"
              :key="`mu-${idx}-${u}`"
              :href="u"
              target="_blank"
              class="source-link"
            >
              {{ u }}
            </a>
          </div>
        </div>

        <el-divider v-if="article.material_pack_id || article.material_refs" />

        <div class="source-refs" v-if="article.source_refs?.length">
          <span class="label">引用源：</span>
          <div class="tags">
            <el-tag 
              v-for="(ref, idx) in sourceRefsToShow" 
              :key="idx" 
              size="small" 
              type="info" 
              effect="light"
            >
              {{ ref }}
            </el-tag>

            <el-button
              v-if="sourceRefsHasMore"
              link
              type="primary"
              size="small"
              class="toggle-btn"
              @click="sourceRefsExpanded = !sourceRefsExpanded"
            >
              {{ sourceRefsExpanded ? '收起' : '展开查看全部' }}
            </el-button>
          </div>
        </div>
        
        <el-divider v-if="article.source_refs?.length" />
        
        <div class="content-preview" v-html="article.content_html" />
      </div>
      <el-empty v-else description="未找到文章信息" />
    </el-card>

    <PublishToWechatDialog
      v-model="publishDialogVisible"
      :article-id="article?.id || null"
      :default-digest="article?.summary || ''"
      @success="onPublishSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowLeft, DocumentCopy, CopyDocument } from "@element-plus/icons-vue";
import { getArticle } from "@/api/articles";
import type { Article } from "@/types";
import type { PublishTask } from "@/types";
import PublishToWechatDialog from "@/components/PublishToWechatDialog.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const article = ref<Article | null>(null);
const publishDialogVisible = ref(false);

const materialRefsExpanded = ref(false);
const sourceRefsExpanded = ref(false);

const MATERIAL_TAG_LIMIT = 8;
const MATERIAL_URL_LIMIT = 3;
const SOURCE_REF_LIMIT = 10;

const materialItemIds = computed<number[]>(() => {
  const xs = article.value?.material_refs?.item_ids;
  return Array.isArray(xs) ? xs : [];
});
const materialEventIds = computed<number[]>(() => {
  const xs = article.value?.material_refs?.source_event_ids;
  return Array.isArray(xs) ? xs : [];
});
const materialContentIds = computed<number[]>(() => {
  const xs = article.value?.material_refs?.source_content_ids;
  return Array.isArray(xs) ? xs : [];
});
const materialSourceUrls = computed<string[]>(() => {
  const xs = article.value?.material_refs?.source_urls;
  return Array.isArray(xs) ? xs : [];
});

const materialRefsHasMore = computed(() => {
  return (
    materialItemIds.value.length > MATERIAL_TAG_LIMIT ||
    materialEventIds.value.length > MATERIAL_TAG_LIMIT ||
    materialContentIds.value.length > MATERIAL_TAG_LIMIT ||
    materialSourceUrls.value.length > MATERIAL_URL_LIMIT
  );
});

const materialItemIdsToShow = computed(() =>
  materialRefsExpanded.value ? materialItemIds.value : materialItemIds.value.slice(0, MATERIAL_TAG_LIMIT)
);
const materialEventIdsToShow = computed(() =>
  materialRefsExpanded.value ? materialEventIds.value : materialEventIds.value.slice(0, MATERIAL_TAG_LIMIT)
);
const materialContentIdsToShow = computed(() =>
  materialRefsExpanded.value ? materialContentIds.value : materialContentIds.value.slice(0, MATERIAL_TAG_LIMIT)
);
const materialSourceUrlsToShow = computed(() =>
  materialRefsExpanded.value ? materialSourceUrls.value : materialSourceUrls.value.slice(0, MATERIAL_URL_LIMIT)
);

const sourceRefs = computed<number[]>(() => {
  const xs = article.value?.source_refs;
  return Array.isArray(xs) ? xs : [];
});
const sourceRefsHasMore = computed(() => sourceRefs.value.length > SOURCE_REF_LIMIT);
const sourceRefsToShow = computed(() =>
  sourceRefsExpanded.value ? sourceRefs.value : sourceRefs.value.slice(0, SOURCE_REF_LIMIT)
);

const fetchArticle = async () => {
  const id = Number(route.params.id);
  if (Number.isNaN(id)) {
    ElMessage.error("文章 ID 无效");
    return;
  }
  loading.value = true;
  try {
    article.value = await getArticle(id);
  } catch (err: any) {
    ElMessage.error(err.message || "获取文章失败");
  } finally {
    loading.value = false;
  }
};

onMounted(fetchArticle);

const openPublish = () => {
  if (!article.value?.id) return;
  publishDialogVisible.value = true;
};

const onPublishSuccess = (task: PublishTask) => {
  // 关键提示：发布任务创建成功后，引导去发布页查看进度
  ElMessage.success(`已创建发布任务 #${task.id}`);
};

const copyText = async (text: string) => {
  if (!text) {
    ElMessage.warning("内容为空");
    return;
  }
  await navigator.clipboard.writeText(text);
  ElMessage.success("已复制 Markdown");
};

const copyHtml = async (html: string) => {
  if (!html) {
    ElMessage.warning("HTML 内容为空");
    return;
  }
  const listener = (e: ClipboardEvent) => {
    e.preventDefault();
    if (e.clipboardData) {
      e.clipboardData.setData("text/html", html);
      e.clipboardData.setData("text/plain", html);
    }
  };
  document.addEventListener("copy", listener);
  document.execCommand("copy");
  document.removeEventListener("copy", listener);
  ElMessage.success("已复制 HTML");
};

const goEdit = () => {
  if (!article.value?.id) return;
  router.push(`/articles/${article.value.id}/edit`);
};
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.header-content {
  flex: 1;
  min-width: 0;
}

.nav-row {
  margin-bottom: 8px;
}

.back-btn {
  padding-left: 0;
  color: #606266;
}

.back-btn:hover {
  color: #409eff;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 13px;
  flex-wrap: wrap;
}

.separator {
  color: #dcdfe6;
}

.summary {
  max-width: 800px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.main-card {
  border-radius: 8px;
  min-height: 400px;
}

.source-refs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.source-refs .label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.links {
  margin-left: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.source-link {
  color: #409eff;
  text-decoration: none;
  word-break: break-all;
}

.source-link:hover {
  text-decoration: underline;
}

.toggle-btn {
  padding-left: 4px;
  padding-right: 4px;
}

.content-preview {
  background: #fff;
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
}

/* 简单的文章样式重置，确保 HTML 预览正常 */
.content-preview :deep(h1) { font-size: 1.8em; margin-bottom: 0.6em; }
.content-preview :deep(h2) { font-size: 1.5em; margin-top: 1.2em; margin-bottom: 0.6em; }
.content-preview :deep(h3) { font-size: 1.25em; margin-top: 1.1em; margin-bottom: 0.5em; }
.content-preview :deep(p) { margin-bottom: 1em; text-align: justify; }
.content-preview :deep(ul), .content-preview :deep(ol) { margin-bottom: 1em; padding-left: 1.5em; }
.content-preview :deep(li) { margin-bottom: 0.4em; }
.content-preview :deep(blockquote) { 
  border-left: 4px solid #dcdfe6; 
  margin: 0 0 1em 0; 
  padding: 0.5em 1em; 
  background-color: #f4f6f8; 
  color: #606266; 
}
.content-preview :deep(code) { 
  background-color: #f2f4f7; 
  padding: 2px 4px; 
  border-radius: 4px; 
  font-family: monospace; 
}
.content-preview :deep(img) { max-width: 100%; border-radius: 4px; margin: 1em 0; }
</style>
