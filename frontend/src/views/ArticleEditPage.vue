<template>
  <div class="page-container">
    <!-- 顶部导航与操作栏 -->
    <div class="header-section">
      <div class="header-left">
        <el-button link @click="router.back()" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <span class="divider">|</span>
        <span class="page-title">编辑软文</span>
        <div class="meta-tags" v-if="article">
          <el-tag size="small" type="info" effect="plain">ID: {{ article.id }}</el-tag>
          <el-tag size="small" type="info" effect="plain">{{ formatTime(article.created_at) }}</el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="danger" plain :loading="deleting" @click="onDelete" :disabled="!articleId">
          删除
        </el-button>
        <el-button type="warning" @click="onOpenPublish" :disabled="!articleId || loading">
          一键发布
        </el-button>
        <el-button type="primary" :loading="saving" @click="onSave" :disabled="!articleId">
          保存更改
        </el-button>
      </div>
    </div>

    <!-- 主体内容区：左侧编辑，右侧AI辅助 -->
    <div class="main-layout">
      <!-- 左侧编辑区 -->
      <div class="editor-section">
        <div class="meta-inputs">
          <el-input
            v-model="form.title"
            placeholder="请输入文章标题"
            class="title-input"
            size="large"
          />
          <el-input
            v-model="form.summary"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="请输入摘要或导语（可选）"
            class="summary-input"
          />
        </div>
        
        <div class="editor-wrapper">
          <MdEditor 
            ref="editorRef"
            v-model="form.content_md" 
            :preview="true"
            :toolbars-exclude="['github']"
            class="md-editor-instance"
          />
        </div>
      </div>

      <!-- 右侧 AI 助手侧边栏 -->
      <div class="sidebar-section">
        <el-card class="ai-card" shadow="never" :body-style="{ padding: '16px' }">
          <template #header>
            <div class="ai-header">
              <span class="ai-title">✨ AI 助手</span>
              <el-tag size="small" type="warning" effect="dark">Beta</el-tag>
            </div>
          </template>

          <el-form label-position="top" size="small">
            <el-form-item label="执行操作">
              <el-radio-group v-model="aiForm.action" size="small" class="w-full">
                <el-radio-button label="rewrite">重写</el-radio-button>
                <el-radio-button label="continue">续写</el-radio-button>
                <el-radio-button label="translate">翻译</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="模型选择">
              <ModelProviderSelect v-model="aiForm.provider" clearable placeholder="默认后端配置" class="w-full" />
            </el-form-item>

            <el-form-item label="指令要求">
              <el-input 
                v-model="aiForm.instruction" 
                type="textarea" 
                :rows="2"
                placeholder="例如：更专业一点、加入emoji、扩充篇幅..." 
              />
            </el-form-item>

            <el-form-item v-if="aiForm.action === 'translate'" label="目标语言" required>
              <el-input v-model="aiForm.target_language" placeholder="如：English, Japanese" />
            </el-form-item>

            <el-button 
              type="primary" 
              class="w-full" 
              :loading="aiLoading" 
              @click="runAi"
            >
              开始生成
            </el-button>
          </el-form>

          <!-- AI 结果展示与应用 -->
          <div v-if="aiResult.content_md" class="ai-result-area">
            <div class="result-header">
              <span>生成结果预览</span>
              <div class="result-actions">
                <el-button link type="primary" size="small" @click="applyAiToEditor">
                  应用到正文
                </el-button>
                <el-button link type="info" size="small" @click="clearAiResult">
                  清空
                </el-button>
              </div>
            </div>
            <div class="result-content-preview">
              {{ aiResult.content_md }}
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <PublishToWechatDialog
      v-model="publishDialogVisible"
      :article-id="article?.id || null"
      :default-digest="form.summary"
      @success="onPublishSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";
import ModelProviderSelect from "@/components/ModelProviderSelect.vue";
import PublishToWechatDialog from "@/components/PublishToWechatDialog.vue";
import { MdEditor } from 'md-editor-v3';
import 'md-editor-v3/lib/style.css';

import type { Article, ArticleAiEditResponse } from "@/types";
import { aiEditArticle, deleteArticle, getArticle, updateArticle } from "@/api/articles";

const route = useRoute();
const router = useRouter();
const editorRef = ref<any>(null);

// 计算属性：文章ID
const articleId = computed(() => {
  const id = Number(route.params.id);
  return Number.isNaN(id) ? null : id;
});

// 状态定义
const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);
const aiLoading = ref(false);
const article = ref<Article | null>(null);
const publishDialogVisible = ref(false);

// 编辑器表单数据
const form = reactive({
  title: "",
  summary: "",
  content_md: "",
});

const hasUnsavedChanges = computed(() => {
  if (!article.value) return false;
  return (
    (form.title || "") !== (article.value.title || "") ||
    (form.summary || "") !== (article.value.summary || "") ||
    (form.content_md || "") !== (article.value.content_md || "")
  );
});

// AI 助手表单数据
const aiForm = reactive({
  action: "rewrite" as "rewrite" | "continue" | "translate",
  provider: undefined as string | undefined,
  instruction: "",
  target_language: "",
});

// AI 结果数据
const aiResult = reactive<ArticleAiEditResponse>({
  content_md: "",
  content_html: "",
  prompt_text: null,
});

// 工具函数：格式化时间
const formatTime = (timeStr?: string | Date) => {
  if (!timeStr) return '';
  return new Date(timeStr).toLocaleString();
};

const onOpenPublish = async () => {
  if (!articleId.value) return;
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm(
        "你有未保存的更改。发布将使用后端当前保存的文章内容，是否继续？",
        "确认发布",
        {
          type: "warning",
          confirmButtonText: "继续发布",
          cancelButtonText: "取消",
        }
      );
    } catch {
      return;
    }
  }
  publishDialogVisible.value = true;
};

const onPublishSuccess = () => {
  // 成功提示已由弹窗组件统一处理
};

// 获取文章详情
const fetchArticle = async () => {
  if (!articleId.value) {
    ElMessage.error("无效的文章ID");
    return;
  }
  loading.value = true;
  try {
    const data = await getArticle(articleId.value);
    article.value = data;
    form.title = data.title || "";
    form.summary = data.summary || "";
    form.content_md = data.content_md || "";
  } catch (err: any) {
    ElMessage.error(err.message || "加载文章失败");
  } finally {
    loading.value = false;
  }
};

// 保存文章
const onSave = async () => {
  if (!articleId.value) return;
  if (!form.title.trim()) {
    ElMessage.warning("请输入标题");
    return;
  }
  
  saving.value = true;
  try {
    const updated = await updateArticle(articleId.value, {
      title: form.title,
      summary: form.summary,
      content_md: form.content_md,
      // content_html 由后端根据 markdown 自动生成，此处无需传递
    });
    article.value = updated;
    ElMessage.success("保存成功");
  } catch (err: any) {
    ElMessage.error(err.message || "保存失败");
  } finally {
    saving.value = false;
  }
};

// 删除文章
const onDelete = async () => {
  if (!articleId.value) return;
  try {
    await ElMessageBox.confirm("确定要删除这篇文章吗？此操作不可恢复。", "删除确认", {
      type: "warning",
      confirmButtonText: "确定删除",
      cancelButtonText: "取消",
    });
    
    deleting.value = true;
    const resp = await deleteArticle(articleId.value);
    if (resp && resp.ok) {
      ElMessage.success("已删除");
      router.push("/articles");
    } else {
      throw new Error("删除失败");
    }
  } catch (err: any) {
    if (err !== 'cancel') {
      ElMessage.error(err.message || "删除操作失败");
    }
  } finally {
    deleting.value = false;
  }
};

// 运行 AI 任务
const runAi = async () => {
  if (!articleId.value) return;
  if (aiForm.action === "translate" && !aiForm.target_language.trim()) {
    ElMessage.warning("请填写翻译目标语言");
    return;
  }

  // 获取选中内容
  const selectedText = editorRef.value?.getSelectedText() || "";
  
  // 校验：除非是续写且有指令，否则必须选中内容
  if (!selectedText.trim() && !(aiForm.action === 'continue' && aiForm.instruction)) {
    ElMessage.warning("请先在左侧编辑器中选中要处理的文本片段");
    return;
  }

  aiLoading.value = true;
  try {
    const resp = await aiEditArticle(articleId.value, {
      action: aiForm.action,
      provider: aiForm.provider,
      instruction: aiForm.instruction || undefined,
      target_language: aiForm.action === "translate" ? aiForm.target_language : undefined,
      selected_text: selectedText
    });
    
    // 更新结果
    aiResult.content_md = resp.content_md;
    aiResult.content_html = resp.content_html;
    aiResult.prompt_text = resp.prompt_text;
    
    ElMessage.success("AI 生成完成，请确认后应用");
  } catch (err: any) {
    ElMessage.error(err.message || "AI 请求失败");
  } finally {
    aiLoading.value = false;
  }
};

// 应用 AI 结果到编辑器
const applyAiToEditor = () => {
  if (!aiResult.content_md || !editorRef.value) return;
  
  editorRef.value.insert((selected: string) => {
    // 构造插入内容
    // 如果是续写，保留选中内容并追加结果
    // 如果是重写/翻译，直接替换选中内容
    // MdEditor 的 insert 方法会自动处理：如果有选中则替换，无选中则插入光标处
    
    let targetValue = aiResult.content_md;
    
    if (aiForm.action === 'continue') {
      // 续写模式：如果当前有选中内容，应该保留它，并在后面追加
      // 注意：selected 是当前编辑器中实际选中的文本（可能用户在生成后改变了选择）
      if (selected) {
        targetValue = selected + '\n' + targetValue;
      } else {
        // 如果没选中，直接插入光标处，前面加个换行可能更好
        targetValue = '\n' + targetValue;
      }
    }
    
    return {
      targetValue,
      select: true, // 插入后选中新内容，方便用户查看或再次修改
      deviationStart: 0,
      deviationEnd: 0
    };
  });
  
  ElMessage.success("已应用到编辑器");
};

const clearAiResult = () => {
  aiResult.content_md = "";
  aiResult.content_html = "";
  aiResult.prompt_text = null;
};

onMounted(fetchArticle);
</script>

<style scoped>
.page-container {
  height: calc(100vh - 84px); /* 减去顶部导航的高度，如果有的话。这里假设是在 MainLayout 内 */
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg);
  overflow: hidden;
}

/* 顶部 Header */
.header-section {
  flex-shrink: 0;
  height: 64px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider {
  color: #d1d5db;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  font-family: var(--font-serif);
}

.meta-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
}

/* 主布局 */
.main-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
  padding: 16px 24px;
  gap: 20px;
}

/* 左侧编辑区 */
.editor-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0; /* 防止 flex 子项溢出 */
}

.meta-inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title-input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
  padding-left: 0;
  border-bottom: 1px solid #e5e7eb;
  border-radius: 0;
}

.title-input :deep(.el-input__inner) {
  font-family: var(--font-serif); /* 标题使用衬线体 */
  letter-spacing: -0.02em;
  transition: all 0.3s ease;
}

.summary-input :deep(.el-textarea__inner) {
  background: transparent; /* 移除背景 */
  border: none;
  border-left: 3px solid var(--color-accent-light); /* 仅保留左侧引用线 */
  border-radius: 0;
  padding: 8px 16px;
  font-size: 15px;
  font-family: var(--font-serif);
  color: var(--color-text-secondary);
  resize: none;
  font-style: italic;
}

.summary-input :deep(.el-textarea__inner):focus {
  border-left-color: var(--color-accent);
  box-shadow: none;
}

.editor-wrapper {
  flex: 1;
  border: none; /* 移除边框，更沉浸 */
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: white;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.02); /* 极淡的阴影 */
  transition: box-shadow 0.3s ease;
}

.editor-wrapper:hover, .editor-wrapper:focus-within {
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.05);
}

.md-editor-instance {
  height: 100%;
}

/* 右侧侧边栏 */
.sidebar-section {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.ai-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
}

.ai-card :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ai-title {
  font-weight: 600;
  font-size: 16px;
  color: #374151;
}

.w-full {
  width: 100%;
}

.ai-result-area {
  margin-top: 24px;
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #4b5563;
}

.result-content-preview {
  flex: 1;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  color: #374151;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.6;
}
</style>
