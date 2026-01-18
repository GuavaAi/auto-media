<template>
  <div class="resource-sidebar">
    <div class="sidebar-header">
      <div class="header-left">
        <span class="sidebar-title">资源</span>
        <span v-if="basket.count" class="basket-badge-minimal">
          {{ basket.selectedCount }}/{{ basket.count }}
        </span>
      </div>
    </div>

    <el-tabs v-model="tab" class="sidebar-tabs-custom">
      <el-tab-pane label="素材篮" name="basket">
        <div class="basket-panel">
          <div class="basket-header-toolbar">
            <div class="toolbar-left">
              <el-checkbox
                v-model="basketAllChecked"
                :indeterminate="basketIndeterminate"
                :disabled="basket.count === 0"
              >
                全选
              </el-checkbox>
            </div>
            <el-button size="small" type="danger" link @click="basket.clear" :disabled="basket.count === 0">
              <el-icon><Delete /></el-icon>
              清空
            </el-button>
          </div>

          <div v-if="basket.count === 0" class="empty-placeholder">
            <el-icon class="placeholder-icon"><Box /></el-icon>
            <div class="placeholder-text">素材篮为空</div>
            <div class="placeholder-hint">在发现页添加素材</div>
          </div>

          <div v-else class="basket-scroll-area">
            <div 
              v-for="it in basket.items" 
              :key="it._key" 
              class="basket-item-modern"
              :class="{ 'is-selected': it.selected }"
            >
              <div class="item-header" @click="openBasketPreview(it)">
                <el-checkbox
                  :model-value="!!it.selected"
                  @click.stop
                  @update:model-value="(v: boolean) => basket.setSelectedByKey(it._key, v)"
                />
                <div class="item-info">
                  <div class="item-title-text">{{ _candTitle(it) }}</div>
                  <div class="item-desc">{{ _candPreview(it) }}</div>
                </div>
                <div class="basket-actions" @click.stop>
                  <span class="basket-action-slot">
                    <el-tooltip content="预览" placement="left">
                      <el-button
                        type="primary"
                        size="small"
                        circle
                        link
                        class="basket-action-btn"
                        @click="openBasketPreview(it)"
                      >
                        <el-icon><View /></el-icon>
                      </el-button>
                    </el-tooltip>
                  </span>
                  <span class="basket-action-slot">
                    <el-button
                      type="danger"
                      size="small"
                      circle
                      link
                      class="basket-action-btn delete-action"
                      title="移除"
                      @click="confirmRemoveBasketItem(it._key)"
                    >
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="发现" name="discovery">
        <div class="discovery-content">
          <div class="mode-selector">
            <el-segmented v-model="discoveryMode" :options="discoveryOptions" size="small" />
          </div>

          <div v-if="discoveryMode === 'search'" class="discovery-body">
            <UnifiedSearchForm v-model="searchForm" mode="compact" :loading="loading" @submit="runDiscovery" />
          </div>

          <div v-else-if="discoveryMode === 'url'" class="discovery-body">
            <div class="search-input-row">
              <el-input 
                v-model="urlInput" 
                placeholder="粘贴文章链接 (http/https)..." 
                clearable 
                class="main-search-input"
                @keyup.enter="runDiscovery" 
              >
                <template #prefix>
                  <el-icon><Link /></el-icon>
                </template>
              </el-input>
              <el-button type="primary" :loading="loading" @click="runDiscovery" class="search-go-btn">
                抓取
              </el-button>
            </div>
          </div>

          <div v-else class="discovery-body">
            <el-input 
              v-model="pasteText" 
              type="textarea" 
              :rows="6" 
              placeholder="在这里粘贴正文或笔记内容..."
              resize="none"
              class="paste-textarea"
            />
            <div class="paste-actions">
              <el-button type="primary" :disabled="!pasteText.trim()" @click="runDiscovery" class="identify-btn">
                <el-icon><DocumentAdd /></el-icon>
                <span>识别为素材</span>
              </el-button>
              <el-button :disabled="!pasteText.trim()" @click="pasteText = ''" plain size="small">清空</el-button>
            </div>
          </div>

          <div class="results-header">
            <span class="header-text">候选结果</span>
            <div class="header-line"></div>
            <div v-if="candidates.length" class="results-actions">
              <el-button
                size="small"
                :disabled="selectableCandidateCount === 0"
                @click="selectAllCandidates"
              >
                全选
              </el-button>
              <el-button
                size="small"
                :disabled="selectedCandidateKeys.size === 0"
                @click="clearCandidateSelection"
              >
                全不选
              </el-button>
              <el-button 
                size="small" 
                type="primary" 
                :disabled="selectedCandidateKeys.size === 0"
                @click="addSelectedCandidates"
              >
                添加选中 ({{ selectedCandidateKeys.size }})
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                link
                :disabled="selectedCandidateKeys.size === 0"
                @click="removeSelectedCandidates"
              >
                删除选中
              </el-button>
            </div>
          </div>

          <div v-if="!candidates.length" class="empty-placeholder">
            <el-icon class="placeholder-icon"><FolderOpened /></el-icon>
            <div class="placeholder-text">暂无结果</div>
            <div class="placeholder-hint">使用上方工具获取素材</div>
          </div>
          <div v-else class="candidates-scroll-area">
            <div 
              v-for="c in candidates" 
              :key="_candKey(c)" 
              class="candidate-item-modern"
              :class="{ 
                'is-added': isCandidateAdded(c),
                'is-checked': selectedCandidateKeys.has(_candKey(c)),
                'add-animation': justAddedKeys.has(_candKey(c))
              }"
            >
              <el-checkbox
                :model-value="selectedCandidateKeys.has(_candKey(c))"
                :disabled="isCandidateAdded(c)"
                @change="(v: boolean) => toggleCandidateSelection(_candKey(c), v)"
                @click.stop
                class="candidate-checkbox"
              />
              <div class="item-body" @click="!isCandidateAdded(c) && toggleCandidateSelection(_candKey(c))">
                <div class="item-title">{{ _candTitle(c) }}</div>
                <div class="item-desc">{{ _candPreview(c) }}</div>
                <div class="item-actions">
                  <el-button 
                    type="primary" 
                    size="small" 
                    circle 
                    link
                    class="action-btn preview-btn"
                    title="预览"
                    @click.stop="openPreview(c)"
                  >
                    <el-icon><View /></el-icon>
                  </el-button>
                  <el-button 
                    v-if="!isCandidateAdded(c)"
                    type="primary" 
                    size="small" 
                    circle 
                    link
                    class="action-btn add-btn"
                    title="加入素材篮"
                    @click.stop="addCandidateWithAnimation(c)"
                  >
                    <el-icon><Plus /></el-icon>
                  </el-button>
                  <div v-else class="added-status">
                    <el-icon class="check-icon"><CircleCheck /></el-icon>
                  </div>
                  <el-button 
                    type="danger" 
                    size="small" 
                    circle 
                    link
                    class="action-btn remove-btn"
                    title="移除候选"
                    @click.stop="removeCandidate(c)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

    </el-tabs>

    <!-- 候选预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      title="素材预览"
      width="600px"
      append-to-body
      class="material-preview-dialog"
    >
      <div class="preview-container">
        <div class="preview-header-meta">
          <el-tag size="small" type="info" effect="plain">{{ previewItem?.item_type }}</el-tag>
          <el-link 
            v-if="previewItem?.source_url" 
            :href="previewItem.source_url" 
            target="_blank" 
            type="primary" 
            class="source-link"
          >
            查看原文 <el-icon><TopRight /></el-icon>
          </el-link>
        </div>
        <div class="preview-body-text">
          {{ previewItem?.text }}
        </div>
      </div>
      <template #footer>
        <div class="preview-footer">
          <el-button @click="previewVisible = false">关闭</el-button>
          <el-button @click="copyPreviewText">复制内容</el-button>
          <el-button 
            v-if="previewItem && !isCandidateAdded(previewItem)" 
            type="primary" 
            @click="addFromPreview"
          >
            加入素材篮
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 素材篮预览弹窗 -->
    <el-dialog
      v-model="basketPreviewVisible"
      title="素材详情"
      width="640px"
      append-to-body
      class="material-preview-dialog"
    >
      <div class="preview-container">
        <div class="preview-header-meta">
          <div class="preview-title-block">
            <div class="preview-title">{{ basketPreviewTitle }}</div>
            <div class="preview-tags">
              <el-tag size="small" type="info" effect="plain">{{ basketPreviewItem?.item_type }}</el-tag>
              <el-tag v-if="basketPreviewSourceHost" size="small" type="success" effect="plain">
                {{ basketPreviewSourceHost }}
              </el-tag>
              <el-tag v-if="basketPreviewItem?.selected" size="small" type="warning" effect="plain">已选</el-tag>
            </div>
          </div>
          <el-link
            v-if="basketPreviewItem?.source_url"
            :href="basketPreviewItem.source_url"
            target="_blank"
            type="primary"
            class="source-link"
          >
            查看原文 <el-icon><TopRight /></el-icon>
          </el-link>
        </div>
        <div class="preview-summary">
          {{ basketPreviewSummary }}
        </div>
        <el-input
          type="textarea"
          :rows="10"
          v-model="basketPreviewText"
          resize="none"
          class="edit-textarea"
        />
      </div>
      <template #footer>
        <div class="preview-footer">
          <el-button @click="basketPreviewVisible = false">关闭</el-button>
          <el-button @click="copyBasketPreviewText">复制内容</el-button>
          <el-button type="primary" @click="saveBasketPreview">保存修改</el-button>
          <el-button type="danger" link @click="removeBasketPreview">移除</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Link, DocumentAdd, FolderOpened, Plus, Delete, Box, View, TopRight, CircleCheck } from "@element-plus/icons-vue";
import UnifiedSearchForm, { type UnifiedSearchEngine, type UnifiedSearchFormValue } from "@/components/UnifiedSearchForm.vue";
import type { MaterialItemCreate } from "@/types";
import { useMaterialBasketStore, type MaterialBasketItem } from "@/stores/materialBasket";

type DiscoveryMode = "search" | "url" | "paste";

type SearchEngine = UnifiedSearchEngine;

const props = defineProps<{
  onSearch: (payload: { engine: SearchEngine; query: string; limit: number }) => Promise<MaterialItemCreate[]>;
  onUrl: (payload: { url: string }) => Promise<MaterialItemCreate[]>;
  onPaste: (payload: { text: string }) => Promise<MaterialItemCreate[]>;
}>();

const basket = useMaterialBasketStore();

const tab = ref<"discovery" | "basket">("basket");
const discoveryMode = ref<DiscoveryMode>("search");

const discoveryOptions = [
  { label: "搜索", value: "search" },
  { label: "URL", value: "url" },
  { label: "粘贴", value: "paste" },
];

const searchForm = ref<UnifiedSearchFormValue>({
  engine: "aliyun",
  query: "",
  limit: 8,
});

const urlInput = ref("");
const pasteText = ref("");

const loading = ref(false);
const candidates = ref<MaterialItemCreate[]>([]);
const previewVisible = ref(false);
const previewItem = ref<MaterialItemCreate | null>(null);
const basketPreviewVisible = ref(false);
const basketPreviewItem = ref<MaterialBasketItem | null>(null);
const basketPreviewText = ref("");

const basketAllChecked = computed({
  get: () => basket.count > 0 && basket.selectedCount === basket.count,
  set: (val: boolean) => {
    toggleBasketAll(val);
  },
});

const basketIndeterminate = computed(() => {
  if (basket.count === 0) return false;
  return basket.selectedCount > 0 && basket.selectedCount < basket.count;
});

const basketPreviewTitle = computed(() =>
  basketPreviewItem.value ? _candTitle(basketPreviewItem.value) : ""
);

const basketPreviewSummary = computed(() =>
  basketPreviewItem.value ? _candPreview(basketPreviewItem.value) : ""
);

const basketPreviewSourceHost = computed(() => {
  const url = basketPreviewItem.value?.source_url || "";
  if (!url) return "";
  try {
    return new URL(url).hostname || "";
  } catch {
    return "";
  }
});

const openPreview = (item: MaterialItemCreate) => {
  previewItem.value = item;
  previewVisible.value = true;
};

const addFromPreview = () => {
  if (previewItem.value) {
    addCandidateWithAnimation(previewItem.value);
    previewVisible.value = false;
  }
};

const copyPreviewText = async () => {
  if (!previewItem.value?.text) return;
  await navigator.clipboard.writeText(previewItem.value.text);
  ElMessage.success("内容已复制到剪贴板");
};

const toggleBasketAll = (checked: boolean) => {
  if (checked) {
    basket.selectAll();
  } else {
    basket.clearSelection();
  }
};

const openBasketPreview = (item: MaterialBasketItem) => {
  basketPreviewItem.value = item;
  basketPreviewText.value = item.text || "";
  basketPreviewVisible.value = true;
};

const saveBasketPreview = () => {
  if (!basketPreviewItem.value) return;
  basket.updateTextByKey(basketPreviewItem.value._key, basketPreviewText.value);
  ElMessage.success("已保存修改");
};

const removeBasketPreview = () => {
  if (!basketPreviewItem.value) return;
  confirmRemoveBasketItem(basketPreviewItem.value._key).then(() => {
    basketPreviewVisible.value = false;
  });
};

const confirmRemoveBasketItem = async (key: string) => {
  try {
    await ElMessageBox.confirm("确认移除该素材吗？", "删除确认", {
      confirmButtonText: "移除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  basket.removeByKey(key);
};

const copyBasketPreviewText = async () => {
  if (!basketPreviewText.value) return;
  await navigator.clipboard.writeText(basketPreviewText.value);
  ElMessage.success("内容已复制到剪贴板");
};

// 追加候选结果（去重）
const appendCandidates = (newItems: MaterialItemCreate[]) => {
  if (!Array.isArray(newItems) || !newItems.length) return;
  const existedKeys = new Set(candidates.value.map((c) => _candKey(c)));
  const toAdd = newItems.filter((c) => !existedKeys.has(_candKey(c)));
  if (toAdd.length) {
    candidates.value = [...candidates.value, ...toAdd];
    ElMessage.success(`新增 ${toAdd.length} 条候选`);
  } else {
    ElMessage.info("没有新增候选（已存在）");
  }
};

const runDiscovery = async (payload?: UnifiedSearchFormValue) => {
  loading.value = true;
  try {
    if (discoveryMode.value === "search") {
      const current = payload || searchForm.value;
      const q = (current.query || "").trim();
      if (!q) {
        ElMessage.warning("请先输入搜索关键词");
        return;
      }
      const res = await props.onSearch({
        engine: current.engine as SearchEngine,
        query: q,
        limit: Number(current.limit || 8),
      });
      appendCandidates(res);
    } else if (discoveryMode.value === "url") {
      const url = (urlInput.value || "").trim();
      if (!url) {
        ElMessage.warning("请先输入 URL");
        return;
      }
      const res = await props.onUrl({ url });
      appendCandidates(res);
    } else {
      const t = (pasteText.value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
      if (!t) {
        ElMessage.warning("粘贴内容为空");
        return;
      }
      const res = await props.onPaste({ text: t });
      appendCandidates(res);
    }
  } catch (err: any) {
    ElMessage.error(err?.message || "获取候选失败");
  } finally {
    loading.value = false;
  }
};

// 候选结果多选相关
const selectedCandidateKeys = ref<Set<string>>(new Set());
const justAddedKeys = ref<Set<string>>(new Set());

const selectableCandidateCount = computed(() => {
  return (candidates.value || []).filter((c) => !isCandidateAdded(c)).length;
});

// 判断候选是否已添加到素材篮
const isCandidateAdded = (c: MaterialItemCreate) => {
  const key = _candKey(c);
  return basket.items.some(it => {
    const itKey = `${it.item_type}|${it.source_url || ""}|${(it as any).source_content_id || ""}|${(it.text || "").slice(0, 80)}`;
    return itKey === key;
  });
};

// 切换候选选中状态
const toggleCandidateSelection = (key: string, forceValue?: boolean) => {
  const newSet = new Set(selectedCandidateKeys.value);
  if (forceValue === undefined) {
    if (newSet.has(key)) {
      newSet.delete(key);
    } else {
      newSet.add(key);
    }
  } else if (forceValue) {
    newSet.add(key);
  } else {
    newSet.delete(key);
  }
  selectedCandidateKeys.value = newSet;
};

const selectAllCandidates = () => {
  const keys = (candidates.value || [])
    .filter((c) => !isCandidateAdded(c))
    .map((c) => _candKey(c));
  selectedCandidateKeys.value = new Set(keys);
};

const clearCandidateSelection = () => {
  selectedCandidateKeys.value = new Set();
};

// 添加单个候选（带动效）
const addCandidateWithAnimation = (c: MaterialItemCreate) => {
  const key = _candKey(c);
  basket.addMany([c]);
  {
    const s = new Set(justAddedKeys.value);
    s.add(key);
    justAddedKeys.value = s;
  }
  setTimeout(() => {
    const s = new Set(justAddedKeys.value);
    s.delete(key);
    justAddedKeys.value = s;
  }, 600);
  ElMessage.success("已加入素材篮");
};

// 添加选中的候选
const addSelectedCandidates = () => {
  const toAdd = candidates.value.filter(c => {
    const key = _candKey(c);
    return selectedCandidateKeys.value.has(key) && !isCandidateAdded(c);
  });
  if (!toAdd.length) {
    ElMessage.warning("没有可添加的候选");
    return;
  }
  basket.addMany(toAdd);
  // 添加动效
  {
    const s = new Set(justAddedKeys.value);
    toAdd.forEach((c) => s.add(_candKey(c)));
    justAddedKeys.value = s;
  }
  setTimeout(() => {
    const s = new Set(justAddedKeys.value);
    toAdd.forEach((c) => s.delete(_candKey(c)));
    justAddedKeys.value = s;
  }, 600);
  selectedCandidateKeys.value = new Set();
  ElMessage.success(`已加入素材篮：${toAdd.length} 条`);
};

// 删除单个候选
const removeCandidate = (c: MaterialItemCreate) => {
  const key = _candKey(c);
  candidates.value = candidates.value.filter(x => _candKey(x) !== key);
  {
    const s = new Set(selectedCandidateKeys.value);
    s.delete(key);
    selectedCandidateKeys.value = s;
  }
};

// 删除选中的候选
const removeSelectedCandidates = () => {
  const toRemove = new Set(selectedCandidateKeys.value);
  candidates.value = candidates.value.filter(c => !toRemove.has(_candKey(c)));
  selectedCandidateKeys.value = new Set();
  ElMessage.success("已删除选中候选");
};

const addCandidate = (c: MaterialItemCreate) => {
  basket.addMany([c]);
  ElMessage.success("已加入素材篮：1 条");
};

const _candKey = (c: MaterialItemCreate) => {
  const t = String(c.item_type || "");
  const s = String(c.source_url || "");
  const id = String((c as any).source_content_id || "");
  const text = String(c.text || "").slice(0, 80);
  return `${t}|${s}|${id}|${text}`;
};

const _candTitle = (c: MaterialItemCreate) => {
  const text = String(c.text || "").trim();
  if (!text) return "(空)";
  const firstLine = text.split("\n")[0].trim();
  return firstLine.slice(0, 60) || "(空)";
};

const _candPreview = (c: MaterialItemCreate) => {
  const text = String(c.text || "").trim();
  if (!text) return "";
  const t = text.replace(/\s+/g, " ");
  return t.length > 140 ? t.slice(0, 140) + "..." : t;
};
</script>

<style scoped>
.resource-sidebar {
  width: 320px;
  min-width: 320px;
  position: sticky;
  top: 0;
  align-self: flex-start;
  max-height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #eef2f6;
  z-index: 10;
  flex-shrink: 0;
}

/* 左侧资源区滚动条 */
.resource-sidebar::-webkit-scrollbar {
  width: 5px;
}

.resource-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.resource-sidebar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}

.resource-sidebar::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}

.sidebar-header {
  padding: 16px 20px 8px;
  background: #fff;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-title {
  font-weight: 600;
  font-size: 16px;
  color: #1e293b;
}

.basket-badge-minimal {
  font-size: 11px;
  color: #3b82f6;
  background: #eff6ff;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.sidebar-tabs-custom {
  display: flex;
  flex-direction: column;
}

.sidebar-tabs-custom :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
}

.sidebar-tabs-custom :deep(.el-tabs__nav-scroll) {
  padding-left: 0;
}

.sidebar-tabs-custom :deep(.el-tabs__item:first-child) {
  padding-left: 0 !important;
}

.sidebar-tabs-custom :deep(.el-tabs__item) {
  font-size: 13px;
  padding: 0 !important;
  margin-right: 20px;
  height: 36px;
  line-height: 36px;
  color: #64748b;
}

.sidebar-tabs-custom :deep(.el-tabs__item.is-active) {
  color: #3b82f6;
  font-weight: 600;
}

.sidebar-tabs-custom :deep(.el-tabs__active-bar) {
  background-color: #3b82f6;
  height: 2px;
}

.sidebar-tabs-custom :deep(.el-tabs__content) {
  overflow: visible;
}

.sidebar-tabs-custom :deep(.el-tab-pane) {
  padding: 20px;
  background: #fcfdfe;
}

.discovery-content,
.basket-panel {
  display: flex;
  flex-direction: column;
}

.mode-selector {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-start;
}

.discovery-body {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-label {
  font-size: 12px;
  color: #909399;
  width: 32px;
  flex-shrink: 0;
}

.engine-picker {
  flex: none;
}

.search-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.main-search-input {
  flex: 1;
}

.main-search-input :deep(.el-input__wrapper) {
  border-radius: 6px;
  padding-left: 8px;
}

.search-go-btn {
  padding: 8px 12px;
}

.paste-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  background: #fff;
}

.paste-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.identify-btn {
  flex: 1;
}

.results-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 20px 0 12px;
}

.header-text {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  white-space: nowrap;
}

.header-line {
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

.empty-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: #94a3b8;
  text-align: center;
}

.placeholder-icon {
  font-size: 40px;
  margin-bottom: 12px;
  color: #cbd5e1;
}

.placeholder-text {
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  margin-bottom: 4px;
}

.placeholder-hint {
  font-size: 12px;
  color: #94a3b8;
}

.candidates-scroll-area,
.basket-scroll-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 20px;
}

.candidates-scroll-area::-webkit-scrollbar,
.basket-scroll-area::-webkit-scrollbar {
  width: 5px;
}

.candidates-scroll-area::-webkit-scrollbar-track,
.basket-scroll-area::-webkit-scrollbar-track {
  background: transparent;
}

.candidates-scroll-area::-webkit-scrollbar-thumb,
.basket-scroll-area::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}

.candidates-scroll-area::-webkit-scrollbar-thumb:hover,
.basket-scroll-area::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}

.candidate-item-modern {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f1f5f9;
  transition: all 0.2s ease;
}

.candidate-item-modern:hover {
  border-color: #e2e8f0;
  background: #f8fafc;
}

/* 已添加状态：置灰 */
.candidate-item-modern.is-added {
  opacity: 0.6;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.candidate-item-modern.is-added .item-title,
.candidate-item-modern.is-added .item-desc {
  color: #94a3b8;
}

.candidate-item-modern.is-added:hover {
  opacity: 0.7;
}

/* 选中状态 */
.candidate-item-modern.is-checked {
  border-color: #3b82f6;
  background: #f0f9ff;
}

/* 添加动效 */
.candidate-item-modern.add-animation {
  animation: addPulse 0.6s ease-out;
}

@keyframes addPulse {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
  }
  50% {
    transform: scale(0.98);
    box-shadow: 0 0 0 6px rgba(59, 130, 246, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
  }
}

.candidate-checkbox {
  flex-shrink: 0;
}

.added-status {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  width: 24px;
}

.check-icon {
  font-size: 16px;
  color: #10b981;
}

/* 按钮组优化 */
.action-btn {
  opacity: 0;
  transition: all 0.2s ease;
  transform: scale(0.9);
  width: 24px !important;
  height: 24px !important;
}

.candidate-item-modern:hover .action-btn {
  opacity: 1;
  transform: scale(1);
}

.preview-btn:hover {
  background-color: #eff6ff !important;
  color: #3b82f6 !important;
}

.remove-btn:hover {
  background-color: #fef2f2 !important;
  color: #ef4444 !important;
}

.add-btn:hover {
  background-color: #f0fdf4 !important;
  color: #10b981 !important;
}

.item-body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.item-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
  width: 100%;
}

.results-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  width: 100%;
}

.item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 2px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 预览弹窗样式 */
.material-preview-dialog :deep(.el-dialog__body) {
  padding: 20px;
  background: #fcfdfe;
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-header-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-body-text {
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
  background: #fff;
  padding: 16px;
  border: 1px solid #eef2f6;
  border-radius: 8px;
}

.source-link {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.basket-header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.basket-item-modern {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f1f5f9;
  overflow: hidden;
  transition: all 0.2s ease;
}

.basket-item-modern:hover {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.basket-item-modern.is-selected {
  border-color: #e0f2fe;
  background: #f0f9ff;
}


.item-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
}

.item-header:hover .arrow-icon {
  color: #3b82f6;
}

 .item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
 }

.item-title-text {
  font-size: 12px;
  font-weight: 500;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.basket-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  min-width: 28px;
  justify-content: center;
}

.basket-action-slot {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.basket-action-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.basket-action-btn.delete-action {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.basket-item-modern:hover .basket-action-btn.delete-action {
  opacity: 1;
  pointer-events: auto;
}

.type-tag {
  font-size: 10px;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
}

.arrow-icon {
  margin-left: auto;
  font-size: 14px;
  color: #94a3b8;
  transition: color 0.2s ease;
}

.preview-title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preview-summary {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  background: #f8fafc;
  border: 1px solid #eef2f6;
  border-radius: 8px;
  padding: 10px 12px;
}

.edit-textarea :deep(.el-textarea__inner) {
  margin-top: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px;
  background: #fff;
}

 .edit-textarea :deep(.el-textarea__inner:focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.12);
 }

 .edit-textarea :deep(.el-textarea__inner)::-webkit-scrollbar {
  width: 6px;
 }

 .edit-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-track {
  background: transparent;
 }

 .edit-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-thumb {
  background: #dbe3ee;
  border-radius: 10px;
 }

 .edit-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
 }

.item-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

/* 自定义滚动条美化 */
.sidebar-tabs-custom :deep(.el-tab-pane)::-webkit-scrollbar {
  width: 5px;
}

.sidebar-tabs-custom :deep(.el-tab-pane)::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-tabs-custom :deep(.el-tab-pane)::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}

.sidebar-tabs-custom :deep(.el-tab-pane)::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}

/* 移除重复的样式定义 */
</style>
