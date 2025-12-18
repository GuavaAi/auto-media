<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">Prompt 模板管理</h2>
        <p class="page-desc">
          可视化编辑与版本控制。支持变量占位：{topic} {outline} {keywords} {tone} {length} {summary_hint} {sources}
        </p>
      </div>
      <div class="header-actions">
        <el-button :loading="loading" @click="loadTemplates">
          <el-icon class="el-icon--left"><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="main-row">
      <!-- 左侧：模板列表 + 版本记录 -->
      <el-col :span="8" class="left-col">
        <el-card class="list-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">模板列表</span>
              <el-input
                v-model="keyKeyword"
                placeholder="搜索 Key..."
                size="default"
                clearable
                class="search-input"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
          </template>

          <div class="new-key-box">
             <el-input
                v-model="newKey"
                placeholder="输入新 Key 创建..."
                size="default"
                clearable
                @keyup.enter="confirmNewKey"
              >
                <template #append>
                  <el-button @click="confirmNewKey">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                </template>
              </el-input>
          </div>

          <el-scrollbar height="calc(100vh - 450px)" class="keys-scroll">
            <div
              v-for="k in filteredKeys"
              :key="k"
              class="key-item"
              :class="{ active: k === selectedKey }"
              @click="selectKey(k)"
            >
              <div class="key-main">
                <span class="key-name">{{ k }}</span>
                <el-tag size="small" type="info" effect="plain" class="version-tag">v{{ getLatestVersion(k) ?? '-' }}</el-tag>
              </div>
              <div class="key-meta">
                <span class="count">{{ getVersionCount(k) }} 个版本</span>
                <el-icon class="arrow-icon"><ArrowRight /></el-icon>
              </div>
            </div>
            <el-empty v-if="!filteredKeys.length" description="无匹配模板" :image-size="60" />
          </el-scrollbar>
        </el-card>

        <el-card v-if="selectedKey" class="version-card mt-4" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">历史版本 ({{ selectedKey }})</span>
            </div>
          </template>

          <el-table :data="versions" size="small" height="250" stripe :show-header="true">
            <el-table-column prop="version" label="Ver" width="60" align="center">
               <template #default="{ row }">
                 <span class="ver-badge">v{{ row.version }}</span>
               </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="130" align="right">
              <template #default="scope">
                <el-button link type="primary" size="small" @click="loadFromRow(scope.row)">加载</el-button>
                <el-button link type="warning" size="small" @click="rollbackFromRow(scope.row)">回滚</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：编辑 + 预览 -->
      <el-col :span="16" class="right-col">
        <el-card class="editor-card" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="left">
                <span class="title">模板编辑</span>
                <el-tag v-if="dirty" type="warning" effect="light" size="small" class="status-tag">未保存</el-tag>
                <el-tag v-else type="success" effect="plain" size="small" class="status-tag">已同步</el-tag>
              </div>
              <div class="right actions">
                <el-button :disabled="!selectedKey" @click="loadLatest">重置为 Latest</el-button>
                <el-button v-if="canDelete" type="danger" :loading="deleting" @click="deleteCurrentKey">
                  <el-icon class="el-icon--left"><Delete /></el-icon>
                  删除模板
                </el-button>
                <el-button type="primary" :loading="saving" :disabled="!canPublish" @click="publish">
                  <el-icon class="el-icon--left"><Upload /></el-icon>
                  发布新版本
                </el-button>
              </div>
            </div>
          </template>

          <div class="vars-bar">
            <span class="label">插入变量:</span>
            <div class="chips">
              <el-tag 
                v-for="v in variableChips" 
                :key="v" 
                class="var-chip" 
                effect="plain"
                @click="insertVar(v)"
              >
                {{ v }}
              </el-tag>
            </div>

            <div class="preset-box">
              <span class="label">内置软文模板:</span>
              <el-select
                v-model="selectedPresetKey"
                class="preset-select"
                placeholder="选择后自动填充"
                clearable
                filterable
                @change="applyPreset"
              >
                <el-option
                  v-for="p in builtinPresets"
                  :key="p.key"
                  :label="p.label"
                  :value="p.key"
                />
              </el-select>
            </div>
          </div>

          <el-input
            v-model="editor"
            type="textarea"
            :rows="18"
            placeholder="在此编辑 Prompt 模板内容..."
            class="editor-input"
            spellcheck="false"
          />

          <div class="preview-section">
            <div class="preview-header">
               <div class="meta-info">
                  <span>当前预览: </span>
                  <el-tag v-if="selectedKey" size="small">{{ selectedKey }}</el-tag>
                  <el-tag v-if="selectedVersion != null" type="info" size="small">v{{ selectedVersion }}</el-tag>
               </div>
               <el-button link type="primary" size="small" @click="copyContent">
                 <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
                 复制内容
               </el-button>
            </div>
            <div class="preview-box">
              <div class="preview-label">渲染结果示例:</div>
              <pre class="preview-content">{{ previewContent }}</pre>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { 
  Refresh, 
  Search, 
  Plus, 
  ArrowRight, 
  Upload, 
  Delete,
  DocumentCopy 
} from "@element-plus/icons-vue";
import { createPromptTemplate, deletePromptTemplate, listPromptTemplates } from "@/api/articles";
import type { PromptTemplate } from "@/types";

const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);

const templates = ref<PromptTemplate[]>([]);
const keyKeyword = ref("");
const newKey = ref("");
const selectedKey = ref<string>("");
const selectedVersion = ref<number | null>(null);
const editor = ref<string>("");
const dirty = ref(false);
const settingEditor = ref(false);

const selectedPresetKey = ref<string>("");

const builtinPresets = [
  {
    key: "copywriting.basic.v1",
    label: "通用软文｜痛点-方案-证据-步骤-CTA",
    content: `你是一位资深自媒体内容编辑，请基于给定信息生成一篇高质量软文（中文），用于公众号/知乎等。

【主题】{topic}
【关键词】{keywords}
【语气/风格】{tone}
【目标字数】{length}
【大纲(如有)】\n{outline}
【写作重点提示】{summary_hint}
【参考资料(如有)】\n{sources}

写作要求：
1) 输出 Markdown。
2) 先给出 10 个候选标题（不超过 28 字，包含关键词但不生硬），再从中选择 1 个作为最终标题。
3) 正文结构：开场钩子(3-5句) → 痛点/现状 → 解决方案(分点) → 证据/案例/数据(可基于资料合理概括，避免编造具体数字) → 可执行步骤(3-7条) → 总结与行动号召(CTA)。
4) 每个小节尽量短段落，避免大段堆砌；适当使用列表。
5) 如资料不足，用“可能/通常/建议”表述，不要杜撰可核验细节。
6) 结尾追加：\n- 3 条可用于朋友圈的短文案（每条 30-60 字）\n- 5 个配图提示词（便于生成配图）。

现在开始输出。`,
  },
  {
    key: "copywriting.story.v1",
    label: "故事型软文｜场景故事+反转+干货",
    content: `你是一位擅长故事化表达的自媒体作者，请围绕主题创作一篇“故事型软文”。

【主题】{topic}
【关键词】{keywords}
【语气/风格】{tone}
【目标字数】{length}
【大纲(如有)】\n{outline}
【写作重点提示】{summary_hint}
【参考资料(如有)】\n{sources}

写作要求（Markdown 输出）：
1) 开头 120 字内用具体场景 + 情绪描写引入（让读者代入）。
2) 讲一个 1-2 个主角的短故事：困境 → 尝试失败 → 关键转折 → 找到方法 → 结果变化。
3) 故事之后提炼“3-5 条可迁移的方法论/干货”，每条包含：做法 + 为什么有效 + 示例。
4) 结尾用 3 句话总结并给出 CTA（关注/收藏/评论引导），语气自然不生硬。
5) 不要出现“作为AI”字样；避免夸大承诺。

请开始输出。`,
  },
  {
    key: "copywriting.product.v1",
    label: "工具/产品软文｜对比测评+上手教程",
    content: `你是一个严谨的测评型自媒体作者，请生成一篇工具/产品推荐软文。

【主题】{topic}
【关键词】{keywords}
【语气/风格】{tone}
【目标字数】{length}
【大纲(如有)】\n{outline}
【写作重点提示】{summary_hint}
【参考资料(如有)】\n{sources}

输出格式：Markdown。

内容结构：
1) 一句话总结：适合谁/解决什么。
2) 典型使用场景（3 个）。
3) 核心亮点（3-6 点），每点写清“对用户的直接收益”。
4) 对比（可与“传统做法/常见方案”对比，不点名竞品）：从成本、时间、学习门槛、风险四个维度。
5) 上手教程：分步骤 5-8 步，尽量可操作。
6) 注意事项与边界：列出 3-5 条（风险、误区、适用范围）。
7) 结尾 CTA：引导读者留言问题/收藏。

请开始输出。`,
  },
  {
    key: "copywriting.hotspot.v1",
    label: "热点借势软文｜事件解读+观点+建议",
    content: `你是一位观点清晰、逻辑严密的自媒体作者，请基于热点/事件主题写一篇借势软文。

【主题】{topic}
【关键词】{keywords}
【语气/风格】{tone}
【目标字数】{length}
【大纲(如有)】\n{outline}
【写作重点提示】{summary_hint}
【参考资料(如有)】\n{sources}

写作要求（Markdown）：
1) 开头用 3 句话概括事件/背景，并抛出一个争议点或问题。
2) 主体用“观点 → 论据 → 反方可能的质疑 → 你的回应”的结构，至少 2 轮。
3) 给出 5 条可执行建议（面向普通读者/从业者均可）。
4) 避免站队/攻击性语言；对不确定信息要标注“不确定/尚无权威结论”。
5) 结尾输出：\n- 5 个评论区提问引导（用于互动）\n- 1 段 80-120 字的摘要（用于文章摘要/导语）。

请开始输出。`,
  },
];

const PROTECTED_TEMPLATE_KEYS = new Set<string>([
  "default_article",
  ...builtinPresets.map((p) => p.key),
]);

const variableChips = [
  "{topic}",
  "{outline}",
  "{keywords}",
  "{tone}",
  "{length}",
  "{summary_hint}",
  "{sources}",
];

const templateKeys = computed(() => {
  const set = new Set<string>();
  templates.value.forEach((t) => set.add(t.key));
  return Array.from(set).sort();
});

const filteredKeys = computed(() => {
  if (!keyKeyword.value.trim()) return templateKeys.value;
  return templateKeys.value.filter((k) => k.toLowerCase().includes(keyKeyword.value.trim().toLowerCase()));
});

const versions = computed(() => {
  if (!selectedKey.value) return [] as PromptTemplate[];
  return templates.value
    .filter((t) => t.key === selectedKey.value)
    .slice()
    .sort((a, b) => b.version - a.version);
});

const templateVersions = computed(() => versions.value.map((t) => t.version));

const latestVersion = computed(() => {
  const v = templateVersions.value;
  if (!v.length) return null;
  return v.slice().sort((a, b) => b - a)[0];
});

const previewContent = computed(() => {
  const sample = {
    topic: "示例主题：AI 提效自媒体写作",
    outline: "- 现状与痛点\n- 模型能力\n- 风险与把关\n- 落地建议",
    keywords: "AI, 自动化, 提效",
    tone: "专业且亲和",
    length: "800",
    summary_hint: "突出提效与安全性",
    sources: "数据源 A：公众号; 数据源 B：自有素材库",
  };
  return renderPreview(editor.value || "", sample);
});

const renderPreview = (tpl: string, vars: Record<string, string>) => {
  return (tpl || "").replace(/\{(\w+)\}/g, (_, key: string) => {
    return vars[key] ?? "";
  });
};

const canPublish = computed(() => {
  if (!selectedKey.value) return false;
  return !!editor.value?.trim();
});

const canDelete = computed(() => {
  if (!selectedKey.value) return false;
  return !PROTECTED_TEMPLATE_KEYS.has(selectedKey.value);
});

const loadTemplates = async () => {
  loading.value = true;
  try {
    templates.value = await listPromptTemplates();
  } catch (err: any) {
    ElMessage.error(err.message || "加载模板失败");
  } finally {
    loading.value = false;
  }
};

const _setEditor = (content: string) => {
  settingEditor.value = true;
  editor.value = content || "";
  dirty.value = false;
  nextTick(() => {
    settingEditor.value = false;
  });
};

const _findTemplate = (key: string, version: number | null) => {
  if (!key || version == null) return null;
  return templates.value.find((t) => t.key === key && t.version === version) || null;
};

const selectKey = async (key: string) => {
  if (dirty.value && key !== selectedKey.value) {
    try {
      await ElMessageBox.confirm("当前编辑内容未发布，切换 key 会丢失未保存修改，是否继续？", "提示", {
        confirmButtonText: "继续",
        cancelButtonText: "取消",
        type: "warning",
      });
    } catch {
      return;
    }
  }
  selectedPresetKey.value = "";
  selectedKey.value = key;
  await loadLatest();
};

const confirmNewKey = async () => {
  if (!newKey.value.trim()) {
    ElMessage.warning("请输入新 key");
    return;
  }
  const key = newKey.value.trim();
  
  if (dirty.value) {
     try {
       await ElMessageBox.confirm("当前编辑内容未发布，切换 key 会丢失未保存修改，是否继续？", "提示", {
        confirmButtonText: "继续",
        cancelButtonText: "取消",
        type: "warning",
      });
     } catch {
       return;
     }
  }
  
  selectedPresetKey.value = "";
  selectedKey.value = key;
  newKey.value = "";
  selectedVersion.value = null;
  _setEditor("");
  dirty.value = false;
  ElMessage.info("新 key 已选中，请编辑内容后发布新版本");
};

const applyPreset = async (presetKey?: string) => {
  if (!presetKey) return;
  const preset = builtinPresets.find((p) => p.key === presetKey);
  if (!preset) return;

  if (dirty.value) {
    try {
      await ElMessageBox.confirm("当前编辑内容未发布，应用内置模板会丢失未保存修改，是否继续？", "提示", {
        confirmButtonText: "继续",
        cancelButtonText: "取消",
        type: "warning",
      });
    } catch {
      selectedPresetKey.value = "";
      return;
    }
  }

  selectedKey.value = preset.key;
  selectedVersion.value = null;
  newKey.value = "";
  _setEditor(preset.content);
  dirty.value = true;
  ElMessage.success("已填充内置模板，可直接发布新版本");
};

const getLatestVersion = (key: string) => {
  const list = templates.value.filter((t) => t.key === key);
  if (!list.length) return null;
  return list.map((t) => t.version).sort((a, b) => b - a)[0];
};

const getVersionCount = (key: string) => templates.value.filter((t) => t.key === key).length;

const loadLatest = async () => {
  if (!selectedKey.value) return;
  const v = latestVersion.value;
  if (v == null) {
    _setEditor("");
    selectedVersion.value = null;
    return;
  }
  selectedVersion.value = v;
  const tpl = _findTemplate(selectedKey.value, v);
  _setEditor(tpl?.content || "");
};

const loadFromRow = async (row: PromptTemplate) => {
  if (!selectedKey.value) return;
  if (dirty.value) {
    try {
      await ElMessageBox.confirm("当前编辑内容未发布，加载版本会丢失未保存修改，是否继续？", "提示", {
        confirmButtonText: "继续",
        cancelButtonText: "取消",
        type: "warning",
      });
    } catch {
      return;
    }
  }
  selectedVersion.value = row.version;
  _setEditor(row.content);
};

const rollbackFromRow = async (row: PromptTemplate) => {
  if (!row?.key) return;
  try {
    await ElMessageBox.confirm(
      `确认回滚：将 ${row.key}@v${row.version} 的内容发布为一个新的版本（version+1）？`,
      "回滚确认",
      {
        confirmButtonText: "回滚发布",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
  } catch {
    return;
  }

  saving.value = true;
  try {
    const created = await createPromptTemplate({ key: row.key, content: row.content });
    ElMessage.success(`回滚成功：已发布 ${created.key}@v${created.version}`);
    await loadTemplates();
    selectedKey.value = row.key;
    selectedVersion.value = created.version;
    _setEditor(created.content);
  } catch (err: any) {
    ElMessage.error(err.message || "回滚失败");
  } finally {
    saving.value = false;
  }
};

const deleteCurrentKey = async () => {
  if (!selectedKey.value) return;
  const key = selectedKey.value;
  if (PROTECTED_TEMPLATE_KEYS.has(key)) {
    ElMessage.warning("系统默认/内置模板不允许删除");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认删除模板：${key}\n\n将删除该 key 的全部历史版本，且不可恢复。`,
      "删除确认",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
  } catch {
    return;
  }

  deleting.value = true;
  try {
    await deletePromptTemplate(key);
    ElMessage.success("删除成功");
    selectedPresetKey.value = "";
    selectedKey.value = "";
    selectedVersion.value = null;
    _setEditor("");
    dirty.value = false;
    await loadTemplates();
  } catch (err: any) {
    ElMessage.error(err.message || "删除失败");
  } finally {
    deleting.value = false;
  }
};

const publish = async () => {
  if (!selectedKey.value) {
    ElMessage.warning("请先选择或输入 key");
    return;
  }
  if (!editor.value?.trim()) {
    ElMessage.warning("请填写模板内容");
    return;
  }

  saving.value = true;
  try {
    const created = await createPromptTemplate({ key: selectedKey.value, content: editor.value });
    ElMessage.success(`发布成功：${created.key}@v${created.version}`);
    await loadTemplates();
    selectedKey.value = created.key;
    selectedVersion.value = created.version;
    _setEditor(created.content);
  } catch (err: any) {
    ElMessage.error(err.message || "发布失败");
  } finally {
    saving.value = false;
  }
};

const insertVar = (v: string) => {
  const input = document.querySelector(".editor-input textarea") as HTMLTextAreaElement;
  if (input) {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const text = editor.value || "";
    editor.value = text.substring(0, start) + v + text.substring(end);
    nextTick(() => {
      input.setSelectionRange(start + v.length, start + v.length);
      input.focus();
    });
  } else {
    editor.value = `${editor.value || ""}${v}`;
  }
  dirty.value = true;
};

const copyContent = async () => {
  if (!editor.value) {
    ElMessage.info("内容为空，无需复制");
    return;
  }
  await navigator.clipboard.writeText(editor.value);
  ElMessage.success("已复制当前内容");
};

watch(
  () => editor.value,
  (val, oldVal) => {
    if (val === oldVal) return;
    if (saving.value) return;
    if (settingEditor.value) return;
    if (!dirty.value) dirty.value = true;
  }
);

onMounted(async () => {
  await loadTemplates();
});
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: calc(100vh - 48px); /* 适配 MainLayout padding */
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.page-desc {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 14px;
}

.main-row {
  flex: 1;
  overflow: hidden;
}

.left-col, .right-col {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  max-height: 60%;
  border-radius: 8px;
}

.version-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  overflow: hidden;
}

.editor-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
}

.editor-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-weight: 600;
  font-size: 16px;
  margin-right: 12px;
  white-space: nowrap;
}

.search-input {
  width: 160px;
}

.new-key-box {
  margin-bottom: 12px;
}

.keys-scroll {
  flex: 1;
}

.key-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  transition: all 0.2s;
}

.key-item:hover {
  background: #f3f4f6;
}

.key-item.active {
  background: #e6f7ff;
  border: 1px solid #bae7ff;
}

.key-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.key-name {
  font-weight: 500;
  color: #303133;
}

.version-tag {
  width: fit-content;
}

.key-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.arrow-icon {
  opacity: 0;
  transition: opacity 0.2s;
}

.key-item.active .arrow-icon {
  opacity: 1;
  color: #409eff;
}

.mt-4 {
  margin-top: 16px;
}

.status-tag {
  margin-left: 12px;
}

.vars-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.preset-box {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-select {
  width: 240px;
}

.vars-bar .label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.var-chip {
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
}

.var-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.editor-input {
  flex: 1;
  font-family: 'Fira Code', monospace;
}

.editor-input :deep(.el-textarea__inner) {
  height: 100%;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
}

.preview-section {
  margin-top: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  height: 200px;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.meta-info {
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-box {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  display: flex;
  flex-direction: column;
}

.preview-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.preview-content {
  margin: 0;
  font-size: 12px;
  color: #333;
  white-space: pre-wrap;
}

.ver-badge {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #606266;
}
</style>
