<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <div class="nav-row">
          <el-button link @click="goBack" class="back-btn">
            <el-icon><ArrowLeft /></el-icon>
            返回榜单
          </el-button>
        </div>
        <h2 class="page-title">{{ detail?.title || "窗口热点详情" }}</h2>
        <p class="page-desc">{{ detail?.summary || "暂无摘要" }}</p>
      </div>
      <div class="header-actions">
        <div class="action-group">
          <el-button @click="fetchDetail" :loading="loading">
            <el-icon class="el-icon--left"><Refresh /></el-icon>
            刷新
          </el-button>

          <el-button type="success" :disabled="!detail" @click="addToBasket">
            加入素材篮
          </el-button>

          <el-button type="warning" :disabled="!detail" @click="openImportDialog">
            一键导入素材包
            <span v-if="selectedCount" style="margin-left: 6px">({{ selectedCount }})</span>
          </el-button>
        </div>
      </div>
    </div>

    <el-row :gutter="24" class="main-row">
      <el-col :span="16" class="left-col">
        <el-card class="content-card" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="title-with-icon">
                <el-icon class="icon"><List /></el-icon>
                <span>核心要点 ({{ bullets.length }})</span>
              </div>
              <div class="card-actions">
                <el-button link type="primary" size="small" :disabled="!bullets.length" @click="selectAllBullets">全选</el-button>
                <el-button link size="small" :disabled="!bullets.length" @click="clearBullets">清空</el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!loading && !bullets.length" description="暂无要点数据" />
          <el-timeline v-else class="bullet-timeline">
            <el-timeline-item
              v-for="b in bullets"
              :key="b._key"
              :type="selectedBullets[b._key] ? 'primary' : ''"
              :hollow="!selectedBullets[b._key]"
              :timestamp="`#${b.position}`"
              placement="top"
            >
              <div class="bullet-item" :class="{ selected: selectedBullets[b._key] }">
                <div class="item-selector">
                  <el-checkbox v-model="selectedBullets[b._key]" />
                </div>
                <div class="item-body">
                  <div class="checkbox-label" @click="selectedBullets[b._key] = !selectedBullets[b._key]">
                    {{ b.text }}
                  </div>
                  <div class="item-source" v-if="b.source_url">
                    <span class="label">来源:</span>
                    <a :href="b.source_url" target="_blank" class="link" @click.stop>查看原文</a>
                  </div>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>

        <el-card class="content-card mt-4" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="title-with-icon">
                <el-icon class="icon"><ChatLineSquare /></el-icon>
                <span>相关引用 ({{ quotes.length }})</span>
              </div>
              <div class="card-actions">
                <el-button link type="primary" size="small" :disabled="!quotes.length" @click="selectAllQuotes">全选</el-button>
                <el-button link size="small" :disabled="!quotes.length" @click="clearQuotes">清空</el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!loading && !quotes.length" description="暂无引用数据" />
          <div v-else class="quote-grid">
            <div
              v-for="q in quotes"
              :key="q._key"
              class="quote-card"
              :class="{ selected: selectedQuotes[q._key] }"
            >
              <div class="item-selector">
                <el-checkbox v-model="selectedQuotes[q._key]" />
              </div>
              <div class="item-body">
                <div class="quote-text" @click="toggleQuote(q._key)">
                  {{ q.text }}
                </div>
                <div class="quote-footer" v-if="q.source_url">
                  <a :href="q.source_url" target="_blank" class="link" @click.stop>查看原文</a>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8" class="right-col">
        <el-card class="meta-card" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="title-with-icon">
                <el-icon class="icon"><Link /></el-icon>
                <span>来源与指标</span>
              </div>
            </div>
          </template>

          <el-empty v-if="!detail" description="详情数据已失效，请返回列表重新打开" :image-size="140" />
          <template v-else>
            <div class="meta-row">
              <el-tag size="small" type="info" effect="plain">{{ windowLabel(detail.window) }}</el-tag>
              <el-tag
                v-if="(detail.flags || {}).list_parent_fallback || ((detail.extra || {}) as any).is_list_parent"
                size="small"
                type="warning"
                effect="plain"
              >
                聚合页兜底
              </el-tag>
              <el-tag
                v-else-if="(detail.flags || {}).has_list_parent || ((detail.extra || {}) as any).has_list_parent"
                size="small"
                type="info"
                effect="plain"
              >
                含聚合页来源
              </el-tag>
            </div>

            <div class="meta-block">
              <div class="meta-line">事件时间：{{ formatDateTime(detail.event_time_start) || "-" }} ~ {{ formatDateTime(detail.event_time_end) || "-" }}</div>
              <div class="meta-line">热度：{{ Number(detail.hot_score || 0).toLocaleString() }}</div>
              <div class="meta-line">来源：{{ detail.source_count }}</div>
            </div>

            <el-divider />

            <div class="source-list">
              <div v-for="s in sources" :key="`${s.content_id || ''}_${s.url || ''}`" class="source-item">
                <div class="source-title">{{ s.title || s.url || "-" }}</div>
                <div class="source-meta">
                  <el-tag v-if="s.is_list_parent" size="small" type="warning" effect="plain">聚合页</el-tag>
                  <span class="meta-text">{{ s.domain || "-" }}</span>
                  <span class="meta-text">置信度：{{ Number(s.time_confidence || 0).toFixed(2) }}</span>
                </div>
                <div v-if="s.url" class="source-meta">
                  <a :href="s.url" target="_blank" class="link">打开原文</a>
                </div>
              </div>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="importDialogVisible" title="一键导入素材包" width="760px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="素材包名称（必填）" required>
          <el-select
            v-model="importPackName"
            placeholder="输入或选择素材包"
            filterable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option v-for="p in importPackOptions" :key="p.id" :label="`#${p.id} ${p.name}`" :value="p.name" />
          </el-select>
        </el-form-item>

        <el-form-item label="描述（可选)">
          <el-input v-model="importPackDesc" placeholder="例如：窗口热点一键导入" />
        </el-form-item>

        <el-alert :title="importAlertTitle" type="info" show-icon :closable="false" />
      </el-form>

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importPackName.trim()" @click="confirmImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowLeft, Refresh, List, ChatLineSquare, Link } from "@element-plus/icons-vue";

import type { MaterialItemCreate, MaterialPack, WindowHotspotEvent } from "@/types";
import { batchCreateMaterialItems, createMaterialPack, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";

const route = useRoute();
const router = useRouter();
const basket = useMaterialBasketStore();

const detail = ref<WindowHotspotEvent | null>(null);

const loading = ref(false);

type _PickedItem = {
  _key: string;
  type: "bullet" | "quote";
  text: string;
  position: number;
  score?: number;
  source_url?: string | null;
  source_content_id?: number | null;
};

const selectedBullets = ref<Record<string, boolean>>({});
const selectedQuotes = ref<Record<string, boolean>>({});

const bullets = computed<_PickedItem[]>(() => {
  const ev = detail.value;
  if (!ev) return [];
  return (ev.bullets || []).map((b: any) => ({
    _key: `b_${b.position}_${(b.text || "").slice(0, 32)}`,
    type: "bullet",
    text: String(b.text || ""),
    position: Number(b.position || 0),
    score: Number(b.score || 0),
    source_url: b.source_url || null,
    source_content_id: b.source_content_id || null,
  }));
});

const quotes = computed<_PickedItem[]>(() => {
  const ev = detail.value;
  if (!ev) return [];
  return (ev.quotes || []).map((q: any) => ({
    _key: `q_${q.position}_${(q.text || "").slice(0, 32)}`,
    type: "quote",
    text: String(q.text || ""),
    position: Number(q.position || 0),
    score: Number(q.score || 0),
    source_url: q.source_url || null,
    source_content_id: q.source_content_id || null,
  }));
});

const sources = computed(() => detail.value?.sources || []);

const importDialogVisible = ref(false);
const importing = ref(false);
const importPackName = ref("");
const importPackDesc = ref("");
const importPackOptions = ref<MaterialPack[]>([]);

const formatDateTime = (s?: string | null) => {
  if (!s) return "";
  return String(s).replace("T", " ").replace("Z", "");
};

const windowLabel = (w?: string | null) => {
  const map: Record<string, string> = { today: "今日", week: "本周", month: "本月" };
  const k = String(w || "");
  return map[k] || k || "窗口热点";
};

const goBack = () => {
  router.push({ path: "/daily-hotspots", query: route.query });
};

const _selectedItems = (items: _PickedItem[], selected: Record<string, boolean>) => items.filter((it) => selected[it._key]);

const buildSelectedMaterialItems = (): MaterialItemCreate[] => {
  if (!detail.value) return [];
  const ev = detail.value;

  const map: Record<string, string> = { today: "今日", week: "本周", month: "本月" };
  const baseMeta = {
    event_title: ev.title,
    window: ev.window,
    window_key: ev.window,
    window_label: map[String(ev.window || "")] || String(ev.window || ""),
    event_time_end: ev.event_time_end,
    event_time_start: ev.event_time_start,
    flags: ev.flags || undefined,
    _source: "window_hotspot",
  };

  const selBullets = _selectedItems(bullets.value, selectedBullets.value);
  const selQuotes = _selectedItems(quotes.value, selectedQuotes.value);

  const toAdd: MaterialItemCreate[] = [];

  for (const b of selBullets) {
    toAdd.push({
      item_type: "bullet",
      text: b.text,
      source_url: b.source_url || undefined,
      source_content_id: b.source_content_id || undefined,
      meta: { ...baseMeta, position: b.position, score: b.score },
    });
  }

  for (const q of selQuotes) {
    toAdd.push({
      item_type: "quote",
      text: q.text,
      source_url: q.source_url || undefined,
      source_content_id: q.source_content_id || undefined,
      meta: { ...baseMeta, position: q.position, score: q.score },
    });
  }

  return toAdd;
};

const selectedCount = computed(() => buildSelectedMaterialItems().length);

const selectAllBullets = () => {
  const m: Record<string, boolean> = {};
  for (const b of bullets.value) m[b._key] = true;
  selectedBullets.value = m;
};

const clearBullets = () => {
  selectedBullets.value = {};
};

const selectAllQuotes = () => {
  const m: Record<string, boolean> = {};
  for (const q of quotes.value) m[q._key] = true;
  selectedQuotes.value = m;
};

const clearQuotes = () => {
  selectedQuotes.value = {};
};

const toggleQuote = (key: string) => {
  selectedQuotes.value[key] = !selectedQuotes.value[key];
};

const fetchDetail = async () => {
  loading.value = true;
  try {
    const id = String(route.params.id || "");
    const key = decodeURIComponent(id);
    const raw = sessionStorage.getItem(`window_hotspot_detail:${key}`);
    if (!raw) {
      detail.value = null;
      return;
    }
    detail.value = JSON.parse(raw) as WindowHotspotEvent;
    selectAllBullets();
    selectAllQuotes();
  } catch (err: any) {
    ElMessage.error(err.message || "获取热点详情失败");
  } finally {
    loading.value = false;
  }
};

const addToBasket = () => {
  if (!detail.value) return;
  const items = buildSelectedMaterialItems();
  if (!items.length) {
    ElMessage.warning("未选择任何条目");
    return;
  }
  basket.addMany(items);
  ElMessage.success(`已加入素材篮：${items.length} 条（素材篮共 ${basket.count} 条）`);
};

const importAlertTitle = computed(() => {
  return `将导入 ${selectedCount.value} 条素材到素材包中`;
});

const _defaultWindowPackName = () => {
  const map: Record<string, string> = { today: "今日", week: "本周", month: "本月" };
  const k = String(detail.value?.window || "");
  return `${map[k] || k || "窗口"}热点素材`;
};

const _pickOrCreatePackByName = async (name: string): Promise<MaterialPack> => {
  const n = name.trim();
  const existed = importPackOptions.value.find((p) => (p.name || "").trim() === n);
  if (existed) return existed;
  const resp = await listMaterialPacks({ keyword: n, limit: 50, offset: 0 });
  const existed2 = (resp.items || []).find((p) => (p.name || "").trim() === n);
  if (existed2) return existed2;
  return await createMaterialPack({ name: n, description: (importPackDesc.value || "").trim() || undefined });
};

const openImportDialog = async () => {
  if (!detail.value) return;
  importPackName.value = importPackName.value.trim() || _defaultWindowPackName();
  importPackDesc.value = importPackDesc.value || `窗口热点一键导入：${String(detail.value.window || "")}`;

  try {
    const resp = await listMaterialPacks({ limit: 200, offset: 0 });
    importPackOptions.value = resp.items || [];
  } catch {
    importPackOptions.value = [];
  }

  importDialogVisible.value = true;
};

const confirmImport = async () => {
  const name = (importPackName.value || "").trim();
  if (!name) {
    ElMessage.warning("请先填写素材包名称");
    return;
  }
  if (!detail.value) return;

  const items = buildSelectedMaterialItems();
  if (!items.length) {
    ElMessage.warning("未选择任何条目");
    return;
  }

  importing.value = true;
  try {
    const pack = await _pickOrCreatePackByName(name);
    await batchCreateMaterialItems(pack.id, { items });
    importDialogVisible.value = false;
    ElMessage.success(`已导入素材包「${pack.name}」：${items.length} 条`);
  } catch (err: any) {
    ElMessage.error(err.message || "导入素材包失败");
  } finally {
    importing.value = false;
  }
};

onMounted(() => {
  fetchDetail();
});
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

.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: flex-end;
  min-width: 320px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
  word-break: break-all;
}

.page-desc {
  margin: 12px 0 0;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.6;
}

.nav-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.meta-text {
  font-size: 12px;
  color: #909399;
}


.main-row {
  margin-top: 4px;
}

.content-card,
.meta-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.icon {
  color: #409eff;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bullet-item {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

.bullet-item.selected {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 2px 12px 0 rgba(64, 158, 255, 0.1);
}

.item-selector {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.item-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-label {
  cursor: pointer;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
  font-size: 14px;
  line-height: 1.6;
}

.item-source {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}

.quote-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.quote-card {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

.quote-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 2px 12px 0 rgba(64, 158, 255, 0.1);
}

.quote-text {
  cursor: pointer;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
}

.quote-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.link {
  color: #409eff;
  text-decoration: none;
  transition: color 0.2s;
}

.link:hover {
  color: #66b1ff;
  text-decoration: underline;
}

.meta-block {
  margin-top: 12px;
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
}

.meta-line {
  font-size: 12px;
  color: #64748b;
  margin: 4px 0;
  display: flex;
  justify-content: space-between;
}

.source-item {
  padding: 12px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  margin-bottom: 10px;
  transition: border-color 0.3s;
}

.source-item:hover {
  border-color: #409eff;
}

.source-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  line-height: 1.5;
  word-break: break-word;
}

.source-meta {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #909399;
  align-items: center;
}
</style>
