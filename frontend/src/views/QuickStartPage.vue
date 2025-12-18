<template>
  <div class="page-container">
    <div class="content-layout">
      <div v-if="!loading && md" class="catalog-panel">
        <el-card class="catalog-card" shadow="never">
          <template #header>
            <div class="catalog-title">目录</div>
          </template>
          <MdCatalog
            :editorId="editorId"
            :scrollElement="scrollElement"
          />
        </el-card>
      </div>

      <el-card class="main-card" shadow="never">
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <div class="card-title-main">{{ titleMain }}</div>
              <div class="card-title-sub">{{ titleSub }}</div>
            </div>
            <div class="card-actions">
              <el-button :loading="loading" @click="load">
                <el-icon class="el-icon--left"><Refresh /></el-icon>
                刷新
              </el-button>
              <el-button :disabled="!md" @click="copy">
                <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
                复制 Markdown
              </el-button>
            </div>
          </div>
        </template>
        <el-skeleton v-if="loading" :rows="12" animated />
        <el-empty v-else-if="!md" description="暂无教程内容" :image-size="120" />
        <div v-else class="preview-wrap">
          <MdPreview :editorId="editorId" :modelValue="md" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, DocumentCopy } from "@element-plus/icons-vue";
import { MdCatalog, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";

import { getConfigGuideMarkdown, getUserGuideMarkdown } from "@/api/docs";

const route = useRoute();

const loading = ref(false);
const md = ref<string>("");

const editorId = "quickstart-preview";
const scrollElement = ref<string | HTMLElement>(".main-content");

const isConfigGuide = computed(() => route.path.startsWith("/config-guide"));

const titleMain = computed(() => (isConfigGuide.value ? "配置教程" : "运营手册"));
const titleSub = computed(() =>
  isConfigGuide.value ? "阅读系统初始化配置教程（Markdown 动态加载）" : "阅读系统运营手册（Markdown 动态加载）"
);

const load = async () => {
  loading.value = true;
  try {
    md.value = isConfigGuide.value ? await getConfigGuideMarkdown() : await getUserGuideMarkdown();
  } catch (err: any) {
    ElMessage.error(err.message || (isConfigGuide.value ? "加载配置教程失败" : "加载运营手册失败"));
    md.value = "";
  } finally {
    loading.value = false;
  }
};

const copy = async () => {
  if (!md.value) return;
  await navigator.clipboard.writeText(md.value);
  ElMessage.success("已复制 Markdown");
};

onMounted(load);

watch(
  () => route.path,
  () => {
    load();
  }
);
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-title {
  display: flex;
  flex-direction: column;
}

.card-title-main {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.card-title-sub {
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
}

.card-actions {
  display: flex;
  gap: 12px;
}

.main-card {
  border-radius: 8px;
  flex: 1;
}

.content-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.catalog-panel {
  width: 260px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
}

.catalog-card {
  border-radius: 8px;
}

.catalog-card :deep(.el-card__body) {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  overscroll-behavior-y: contain;
}

.catalog-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.preview-wrap {
  min-height: 400px;
  width: 100%;
  padding-top: 1px;
}
</style>
