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
        <h2 class="page-title">{{ detail?.event.title || "热点详情" }}</h2>
        <p class="page-desc">{{ detail?.event.summary || "暂无摘要" }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="fetchDetail" :loading="loading">
          <el-icon class="el-icon--left"><Refresh /></el-icon>
          刷新
        </el-button>

        <el-button :disabled="!detail" @click="openSmartFilter">
          <el-icon class="el-icon--left"><MagicStick /></el-icon>
          智能筛选
        </el-button>

        <el-button type="success" :disabled="!detail" @click="addToBasket">
          加入素材篮
        </el-button>

        <el-button type="warning" :disabled="!detail" @click="openExportToPack">
          写入素材包
        </el-button>
        
        <el-dropdown trigger="click" @command="handleExport">
          <el-button type="primary" :disabled="!detail">
            导出 / 复制
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="copyMd">复制 Markdown</el-dropdown-item>
              <el-dropdown-item command="downloadMd" divided>导出 Markdown 文件</el-dropdown-item>
              <el-dropdown-item command="downloadJson">导出 JSON 文件</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-row :gutter="24" class="main-row">
      <!-- 左侧：内容筛选 (要点 + 引用) -->
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
              :key="b.id"
              :type="selectedBullets[b.id] ? 'primary' : ''"
              :hollow="!selectedBullets[b.id]"
              :timestamp="`#${b.position}`"
              placement="top"
            >
              <div class="bullet-item" :class="{ selected: selectedBullets[b.id] }">
                <el-checkbox v-model="selectedBullets[b.id]" class="bullet-checkbox">
                  <span class="checkbox-label">{{ b.text }}</span>
                </el-checkbox>
                <div class="item-source" v-if="b.source_url">
                  <span class="label">Source:</span>
                  <a :href="b.source_url" target="_blank" class="link">查看来源</a>
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
              :key="q.id" 
              class="quote-card"
              :class="{ selected: selectedQuotes[q.id] }"
              @click="toggleQuote(q.id)"
            >
              <div class="quote-header">
                <el-checkbox v-model="selectedQuotes[q.id]" @click.stop />
                <span class="quote-text">{{ q.text }}</span>
              </div>
              <div class="quote-footer" v-if="q.source_url">
                <a :href="q.source_url" target="_blank" class="link" @click.stop>来源链接</a>
              </div>
            </div>
          </div>
        </el-card>

        <el-card class="content-card mt-4" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="title-with-icon">
                <el-icon class="icon"><ChatLineSquare /></el-icon>
                <span>事实信息 ({{ facts.length }})</span>
              </div>
              <div class="card-actions">
                <el-button link type="primary" size="small" :disabled="!facts.length" @click="selectAllFacts">全选</el-button>
                <el-button link size="small" :disabled="!facts.length" @click="clearFacts">清空</el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!loading && !facts.length" description="暂无事实数据" />
          <div v-else class="quote-grid">
            <div
              v-for="f in facts"
              :key="f.id"
              class="quote-card"
              :class="{ selected: selectedFacts[f.id] }"
              @click="toggleFact(f.id)"
            >
              <div class="quote-header">
                <el-checkbox v-model="selectedFacts[f.id]" @click.stop />
                <span class="quote-text">{{ f.text }}</span>
              </div>
              <div class="quote-footer" v-if="f.source_url">
                <a :href="f.source_url" target="_blank" class="link" @click.stop>来源链接</a>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：元数据 + 来源列表 -->
      <el-col :span="8" class="right-col">
        <el-card class="meta-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">事件元数据</span>
            </div>
          </template>
          
          <div class="meta-list">
            <div class="meta-item">
              <span class="label">日期</span>
              <span class="value">{{ detail?.event.day || '-' }}</span>
            </div>
            <el-divider direction="horizontal" class="meta-divider" />
            <div class="meta-item">
              <span class="label">热度值</span>
              <span class="value hot">{{ detail?.event.hot_score?.toLocaleString() || 0 }}</span>
            </div>
            <el-divider direction="horizontal" class="meta-divider" />
            <div class="meta-item">
              <span class="label">来源数</span>
              <span class="value">{{ detail?.event.source_count || 0 }}</span>
            </div>
            <el-divider direction="horizontal" class="meta-divider" />
            <div class="meta-item">
              <span class="label">更新时间</span>
              <span class="value text-sm">{{ detail?.event.created_at }}</span>
            </div>
          </div>
        </el-card>

        <el-card class="source-card mt-4" shadow="never">
          <template #header>
            <div class="card-header">
              <div class="title-with-icon">
                <el-icon class="icon"><Link /></el-icon>
                <span>来源列表 ({{ sources.length }})</span>
              </div>
            </div>
          </template>

          <el-scrollbar max-height="400px">
            <div v-if="sources.length" class="source-list">
              <div v-for="s in sources" :key="s.id" class="source-item">
                <div class="source-main">
                  <div class="source-title" :title="s.title || s.url || ''">{{ s.title || s.url || "未知标题" }}</div>
                  <div class="source-url">
                    <a v-if="s.url" :href="s.url || ''" target="_blank">{{ s.url }}</a>
                  </div>
                </div>
              </div>
            </div>
            <el-empty v-else description="无来源" :image-size="60" />
          </el-scrollbar>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="smartVisible" title="智能筛选（模型判断相关性）" width="860px">
      <el-form :model="smartForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="14">
            <el-form-item label="筛选指令（可选）">
              <el-input v-model="smartForm.instruction" placeholder="例如：更偏 AI / 财经 / 政策解读" />
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="参与类型">
              <el-select v-model="smartForm.include_types" multiple clearable placeholder="默认全部" style="width: 100%">
                <el-option label="bullet" value="bullet" />
                <el-option label="quote" value="quote" />
                <el-option label="fact" value="fact" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="5">
            <el-form-item label="最多条目">
              <el-input v-model.number="smartForm.max_items" type="number" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-table :data="smartDecisions" v-loading="smartLoading" height="360" style="width: 100%">
          <el-table-column label="选" width="70" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.checked" />
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="90" />
          <el-table-column prop="score" label="评分" width="90" />
          <el-table-column prop="reason" label="原因" width="220" />
          <el-table-column prop="text" label="内容" min-width="360" show-overflow-tooltip />
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="smartVisible = false">取消</el-button>
        <el-button :loading="smartLoading" @click="runSmartFilter">重新筛选</el-button>
        <el-button type="primary" :disabled="smartDecisions.length === 0" @click="applySmartSelection">
          应用到当前勾选
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportToPackVisible" title="写入到素材包" width="560px">
      <el-form label-position="top">
        <el-form-item label="目标素材包" required>
          <el-select
            v-model="exportToPackId"
            filterable
            clearable
            placeholder="选择要写入的素材包"
            style="width: 100%"
          >
            <el-option
              v-for="p in exportPackOptions"
              :key="p.id"
              :label="`#${p.id} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-alert
          :title="`将写入 ${selectedCount} 条素材（本地已去重；可在详情页手动取消勾选）。`"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="exportToPackVisible = false">取消</el-button>
        <el-button type="primary" :loading="exportToPackLoading" @click="onExportToPack">写入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { 
  ArrowLeft, 
  Refresh, 
  ArrowDown, 
  List, 
  ChatLineSquare, 
  Link,
  MagicStick
} from "@element-plus/icons-vue";
import type {
  DailyHotspotDetailResponse,
  DailyHotspotItem,
  DailyHotspotSource,
  DailyHotspotSmartFilterDecision,
  MaterialItemCreate,
  MaterialPack,
} from "@/types";
import { getDailyHotspotDetail, smartFilterDailyHotspot } from "@/api/dailyHotspots";
import { batchCreateMaterialItems, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";

const route = useRoute();
const router = useRouter();

const id = computed(() => Number(route.params.id));

const loading = ref(false);
const detail = ref<DailyHotspotDetailResponse | null>(null);

const basket = useMaterialBasketStore();

const selectedBullets = ref<Record<number, boolean>>({});
const selectedQuotes = ref<Record<number, boolean>>({});
const selectedFacts = ref<Record<number, boolean>>({});

const bullets = computed<DailyHotspotItem[]>(() => detail.value?.bullets || []);
const quotes = computed<DailyHotspotItem[]>(() => detail.value?.quotes || []);
const facts = computed<DailyHotspotItem[]>(() => detail.value?.facts || []);
const sources = computed<DailyHotspotSource[]>(() => detail.value?.sources || []);

const fetchDetail = async () => {
  loading.value = true;
  try {
    detail.value = await getDailyHotspotDetail(id.value);
    // 默认全选
    selectAllBullets();
    selectAllQuotes();
    selectAllFacts();
  } catch (err: any) {
    ElMessage.error(err.message || "获取热点详情失败");
  } finally {
    loading.value = false;
  }
};

const buildSelectedMaterialItems = (): MaterialItemCreate[] => {
  if (!detail.value) return [];
  const evt = detail.value.event;

  const selBullets = _selectedItems(bullets.value, selectedBullets.value);
  const selQuotes = _selectedItems(quotes.value, selectedQuotes.value);
  const selFacts = _selectedItems(facts.value, selectedFacts.value);

  const toAdd: MaterialItemCreate[] = [];

  for (const b of selBullets) {
    toAdd.push({
      item_type: "bullet",
      text: b.text,
      source_url: b.source_url || undefined,
      source_content_id: b.source_content_id || undefined,
      source_event_id: evt.id,
      meta: {
        day: evt.day,
        position: b.position,
      },
    });
  }

  for (const q of selQuotes) {
    toAdd.push({
      item_type: "quote",
      text: q.text,
      source_url: q.source_url || undefined,
      source_content_id: q.source_content_id || undefined,
      source_event_id: evt.id,
      meta: {
        day: evt.day,
        position: q.position,
      },
    });
  }

  for (const f of selFacts) {
    toAdd.push({
      item_type: "fact",
      text: f.text,
      source_url: f.source_url || undefined,
      source_content_id: f.source_content_id || undefined,
      source_event_id: evt.id,
      meta: {
        day: evt.day,
        position: f.position,
      },
    });
  }

  return toAdd;
};

const selectedCount = computed(() => buildSelectedMaterialItems().length);

const addToBasket = () => {
  const toAdd = buildSelectedMaterialItems();
  if (toAdd.length === 0) {
    ElMessage.warning("未选择任何条目");
    return;
  }
  basket.addMany(toAdd);
  ElMessage.success(`已加入素材篮：${toAdd.length} 条（素材篮共 ${basket.count} 条）`);
};

const selectAllBullets = () => {
  const m: Record<number, boolean> = {};
  for (const b of bullets.value) m[b.id] = true;
  selectedBullets.value = m;
};

const clearBullets = () => {
  selectedBullets.value = {};
};

const selectAllQuotes = () => {
  const m: Record<number, boolean> = {};
  for (const q of quotes.value) m[q.id] = true;
  selectedQuotes.value = m;
};

const clearQuotes = () => {
  selectedQuotes.value = {};
};

const toggleQuote = (qid: number) => {
  selectedQuotes.value[qid] = !selectedQuotes.value[qid];
};

const selectAllFacts = () => {
  const m: Record<number, boolean> = {};
  for (const f of facts.value) m[f.id] = true;
  selectedFacts.value = m;
};

const clearFacts = () => {
  selectedFacts.value = {};
};

const toggleFact = (fid: number) => {
  selectedFacts.value[fid] = !selectedFacts.value[fid];
};

const _selectedItems = (items: DailyHotspotItem[], selected: Record<number, boolean>) =>
  items.filter((it) => selected[it.id]);

const buildMaterialJson = () => {
  if (!detail.value) return null;
  const payload = {
    event: detail.value.event,
    bullets: _selectedItems(bullets.value, selectedBullets.value),
    quotes: _selectedItems(quotes.value, selectedQuotes.value),
    sources: sources.value,
  };
  return payload;
};

const buildMaterialMarkdown = () => {
  if (!detail.value) return "";
  const evt = detail.value.event;
  const selBullets = _selectedItems(bullets.value, selectedBullets.value);
  const selQuotes = _selectedItems(quotes.value, selectedQuotes.value);

  const lines: string[] = [];
  lines.push(`# ${evt.title}`);
  if (evt.summary) lines.push(`\n> ${evt.summary}`);
  lines.push(`\n- 日期：${evt.day}`);
  lines.push(`- 热度：${evt.hot_score}`);
  lines.push(`- 来源数：${evt.source_count}`);

  lines.push("\n## 核心要点");
  if (selBullets.length === 0) {
    lines.push("（未选择）");
  } else {
    for (const b of selBullets) {
      lines.push(`- ${b.text}`);
      if (b.source_url) lines.push(`  - 来源：${b.source_url}`);
    }
  }

  lines.push("\n## 相关引用");
  if (selQuotes.length === 0) {
    lines.push("（未选择）");
  } else {
    for (const q of selQuotes) {
      lines.push(`> ${q.text}`);
      if (q.source_url) lines.push(`> 来源：${q.source_url}`);
      lines.push("");
    }
  }

  lines.push("\n## 来源列表");
  if (sources.value.length === 0) {
    lines.push("- （无）");
  } else {
    for (const s of sources.value) {
      lines.push(`- ${s.title || s.url || "-"}`);
      if (s.url) lines.push(`  - ${s.url}`);
    }
  }

  return lines.join("\n").trim() + "\n";
};

const downloadText = (filename: string, content: string, mime: string) => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

const handleExport = (cmd: string) => {
  if (!detail.value) return;
  const evt = detail.value.event;

  if (cmd === 'copyMd') {
    const md = buildMaterialMarkdown();
    navigator.clipboard.writeText(md).then(() => {
      ElMessage.success("已复制 Markdown 到剪贴板");
    });
  } else if (cmd === 'downloadMd') {
    const md = buildMaterialMarkdown();
    downloadText(`hotspot_${evt.id}_${evt.day}.md`, md, "text/markdown;charset=utf-8");
    ElMessage.success("已导出 Markdown");
  } else if (cmd === 'downloadJson') {
    const payload = buildMaterialJson();
    if (payload) {
      downloadText(
        `hotspot_${evt.id}_${evt.day}.json`,
        JSON.stringify(payload, null, 2),
        "application/json;charset=utf-8"
      );
      ElMessage.success("已导出 JSON");
    }
  }
};

const goBack = () => router.push({ path: "/daily-hotspots", query: route.query });

const smartVisible = ref(false);
const smartLoading = ref(false);
const smartForm = ref({
  instruction: "",
  include_types: [] as string[],
  max_items: 30,
  temperature: 0.2,
});

type _SmartRow = DailyHotspotSmartFilterDecision & { checked: boolean; text: string };
const smartDecisions = ref<_SmartRow[]>([]);

const openSmartFilter = async () => {
  smartVisible.value = true;
  await runSmartFilter();
};

const runSmartFilter = async () => {
  if (!detail.value) return;
  smartLoading.value = true;
  try {
    const resp = await smartFilterDailyHotspot(id.value, {
      instruction: smartForm.value.instruction || undefined,
      include_types: smartForm.value.include_types.length ? smartForm.value.include_types : undefined,
      max_items: smartForm.value.max_items,
      temperature: smartForm.value.temperature,
    });

    const textMap: Record<number, string> = {};
    for (const b of bullets.value) textMap[b.id] = b.text;
    for (const q of quotes.value) textMap[q.id] = q.text;
    for (const f of facts.value) textMap[f.id] = f.text;

    smartDecisions.value = (resp.decisions || []).map((d) => ({
      ...d,
      checked: !!d.recommended,
      text: textMap[d.id] || "",
    }));
  } catch (err: any) {
    ElMessage.error(err.message || "智能筛选失败");
  } finally {
    smartLoading.value = false;
  }
};

const applySmartSelection = () => {
  const sb: Record<number, boolean> = {};
  const sq: Record<number, boolean> = {};
  const sf: Record<number, boolean> = {};
  for (const d of smartDecisions.value) {
    if (!d.checked) continue;
    const t = (d.type || "").toLowerCase();
    if (t === "bullet") sb[d.id] = true;
    if (t === "quote") sq[d.id] = true;
    if (t === "fact") sf[d.id] = true;
  }
  selectedBullets.value = sb;
  selectedQuotes.value = sq;
  selectedFacts.value = sf;
  smartVisible.value = false;
  ElMessage.success("已应用智能筛选结果，可继续手动调整");
};

const exportToPackVisible = ref(false);
const exportToPackLoading = ref(false);
const exportToPackId = ref<number | null>(null);
const exportPackOptions = ref<MaterialPack[]>([]);

const loadExportPackOptions = async () => {
  try {
    const resp = await listMaterialPacks({ keyword: undefined, limit: 200, offset: 0 });
    exportPackOptions.value = resp.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "加载素材包列表失败");
  }
};

const openExportToPack = async () => {
  exportToPackId.value = null;
  exportToPackVisible.value = true;
  await loadExportPackOptions();
};

const onExportToPack = async () => {
  if (!exportToPackId.value) {
    ElMessage.warning("请选择目标素材包");
    return;
  }
  const items = buildSelectedMaterialItems();
  if (items.length === 0) {
    ElMessage.warning("未选择任何条目");
    return;
  }

  exportToPackLoading.value = true;
  try {
    await batchCreateMaterialItems(exportToPackId.value, { items });
    ElMessage.success("已写入到素材包");
    exportToPackVisible.value = false;
    router.push(`/materials/packs/${exportToPackId.value}`);
  } catch (err: any) {
    ElMessage.error(err.message || "写入失败");
  } finally {
    exportToPackLoading.value = false;
  }
};

onMounted(async () => {
  await fetchDetail();
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
}

.header-content {
  flex: 1;
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
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}

.page-desc {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.5;
  max-width: 800px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.main-row {
  align-items: flex-start;
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
  font-size: 16px;
  color: #303133;
}

.icon {
  color: #409eff;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.bullet-timeline {
  padding-left: 10px;
}

.bullet-item {
  background: #f9fafb;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.bullet-item.selected {
  background: #ecf5ff;
  border-color: #c6e2ff;
}

.bullet-checkbox {
  display: flex;
  align-items: flex-start;
  white-space: normal;
  height: auto;
}

.bullet-checkbox :deep(.el-checkbox__label) {
  white-space: normal;
  overflow: visible;
  text-overflow: unset;
  word-break: break-word;
}

.checkbox-label {
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.item-source {
  margin-top: 8px;
  margin-left: 24px;
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 6px;
}

.link {
  color: #409eff;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.mt-4 {
  margin-top: 16px;
}

.quote-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.quote-card {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.quote-card:hover {
  border-color: #b3d8ff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.quote-card.selected {
  background: #fdf6ec;
  border-color: #f3d19e;
}

.quote-header {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.quote-text {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  font-style: italic;
  flex: 1;
  min-width: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.quote-footer {
  margin-top: 8px;
  margin-left: 22px;
  font-size: 12px;
  text-align: right;
}

.meta-list {
  display: flex;
  flex-direction: column;
}

.meta-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.meta-item .label {
  color: #909399;
  font-size: 13px;
}

.meta-item .value {
  font-weight: 500;
  color: #303133;
}

.meta-item .value.hot {
  color: #f56c6c;
  font-weight: 700;
}

.meta-item .value.text-sm {
  font-size: 12px;
}

.meta-divider {
  margin: 12px 0;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-item {
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid #f1f5f9;
}

.source-title {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-url a {
  color: #909399;
  font-size: 12px;
  text-decoration: none;
  word-break: break-all;
}

.source-url a:hover {
  color: #409eff;
  text-decoration: underline;
}
</style>
