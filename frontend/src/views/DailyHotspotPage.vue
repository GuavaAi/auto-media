<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">全网热点榜单</h2>
        <p class="page-desc">
          汇聚多平台热点事件，通过 AI 智能分析生成摘要。选择日期查看历史榜单，或手动触发 Build 生成今日最新热点。
        </p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" :loading="windowLoading" @click="fetchWindowList">
          <el-icon class="el-icon--left"><MagicStick /></el-icon>
          生成窗口热点
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="left-panel">
            <el-radio-group v-model="limit" size="default" @change="onLimitChange">
              <el-radio-button :value="20">Top 20</el-radio-button>
              <el-radio-button :value="50">Top 50</el-radio-button>
              <el-radio-button :value="100">Top 100</el-radio-button>
            </el-radio-group>

            <el-divider direction="vertical" />
            <el-radio-group v-model="windowKey" size="default" @change="fetchWindowList">
              <el-radio-button :value="'today'">今日</el-radio-button>
              <el-radio-button :value="'week'">本周</el-radio-button>
              <el-radio-button :value="'month'">本月</el-radio-button>
              <el-radio-button :value="'range'">范围</el-radio-button>
            </el-radio-group>

            <el-date-picker
              v-if="windowKey === 'range'"
              v-model="rangeValue"
              type="daterange"
              unlink-panels
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              @change="onRangeChange"
              style="margin-left: 12px"
            />
          </div>
          <div class="right-panel">
            <el-button @click="openBasket">素材篮 ({{ basket.count }})</el-button>

            <el-button :disabled="windowItems.length === 0" @click="openTopicFilter">
              <el-icon class="el-icon--left"><MagicStick /></el-icon>
              主题智能筛选
            </el-button>

            <el-button
              type="warning"
              :disabled="selectedWindowRows.length === 0"
              :loading="addingToBasket"
              @click="addSelectedWindowToBasket"
            >
              加入素材篮
              <span v-if="selectedWindowRows.length" style="margin-left: 6px">({{ selectedWindowRows.length }})</span>
            </el-button>

            <el-button
              type="success"
              :disabled="selectedWindowRows.length === 0"
              :loading="importing"
              @click="openWindowImportDialog"
            >
              一键导入素材包
              <span v-if="selectedWindowRows.length" style="margin-left: 6px">({{ selectedWindowRows.length }})</span>
            </el-button>

            <el-button v-if="topicFilterApplied" @click="clearTopicFilter">清除筛选</el-button>

            <el-tooltip content="刷新列表" placement="top">
              <el-button circle @click="refreshCurrent" :loading="windowLoading">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <el-empty
        v-if="!windowLoading && displayItems.length === 0"
        description="暂无窗口热点数据"
        :image-size="200"
      >
        <el-button type="primary" plain @click="fetchWindowList">立即生成</el-button>
      </el-empty>

      <el-table
        v-else
        :data="displayItems"
        stripe
        size="default"
        class="data-table"
        v-loading="windowLoading"
        highlight-current-row
        :row-key="windowRowKey"
        @row-click="onWindowRowClick"
        @selection-change="onWindowSelectionChange"
      >
        <el-table-column type="selection" width="52" align="center" />
        <el-table-column label="排名" width="80" align="center">
          <template #default="{ $index }">
            <span class="rank-num" :class="getRankClass($index + 1)">{{ $index + 1 }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="热点事件" min-width="220">
          <template #default="{ row }">
            <div class="event-title">
              {{ row.title }}
              <el-tag
                v-if="(row.flags || {}).list_parent_fallback || ((row.extra || {}) as any).is_list_parent"
                size="small"
                type="warning"
                effect="plain"
                style="margin-left: 8px"
              >
                聚合页兜底
              </el-tag>
              <el-tag
                v-else-if="(row.flags || {}).has_list_parent || ((row.extra || {}) as any).has_list_parent"
                size="small"
                type="info"
                effect="plain"
                style="margin-left: 8px"
              >
                含聚合页来源
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="summary" label="智能摘要" min-width="320">
          <template #default="{ row }">
            <div class="summary-text">{{ row.summary || "暂无摘要" }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="event_time_end" label="事件时间" width="180" align="center">
          <template #default="{ row }">
            <span class="text-sm">{{ formatDateTime(row.event_time_end) || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="hot_score" label="热度值" width="120" align="center" sortable>
          <template #default="{ row }">
            <span class="hot-score">
              <el-icon color="#f56c6c"><DataAnalysis /></el-icon>
              {{ Number(row.hot_score || 0).toLocaleString() }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="source_count" label="来源数" width="100" align="center" sortable>
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ row.source_count }} 来源</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="goWindowDetail(row)">
              详情
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

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
            <el-option
              v-for="p in importPackOptions"
              :key="p.id"
              :label="`#${p.id} ${p.name}`"
              :value="p.name"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="描述（可选）">
          <el-input v-model="importPackDesc" placeholder="例如：热点榜单一键导入" />
        </el-form-item>

        <el-alert
          :title="importAlertTitle"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importPackName.trim()" @click="confirmImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="topicDialogVisible" title="按主题智能筛选热点（可人工确认）" width="860px">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="14">
            <el-form-item label="主题（必填）">
              <el-input v-model="topicForm.topic" placeholder="例如：AI、财经、半导体、新能源、教育" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="额外指令（可选）">
              <el-input v-model="topicForm.instruction" placeholder="例如：优先政策解读/投资机会/商业化" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-table :data="topicDecisions" v-loading="topicLoading" height="360" style="width: 100%">
          <el-table-column label="选" width="70" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.checked" />
            </template>
          </el-table-column>
          <el-table-column prop="score" label="评分" width="90" />
          <el-table-column prop="reason" label="原因" width="240" show-overflow-tooltip />
          <el-table-column prop="title" label="热点事件" min-width="260" show-overflow-tooltip />
          <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
        </el-table>
      </el-form>

      <template #footer>
        <el-button @click="topicDialogVisible = false">取消</el-button>
        <el-button :loading="topicLoading" @click="runTopicFilter">重新筛选</el-button>
        <el-button type="primary" :disabled="topicDecisions.length === 0" @click="applyTopicFilter">应用筛选</el-button>
      </template>
    </el-dialog>

    <MaterialBasketDrawer v-model="basketVisible" @written="onBasketWritten" @created="onBasketCreated" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, MagicStick, DataAnalysis, ArrowRight } from "@element-plus/icons-vue";
import type {
  MaterialItemCreate,
  MaterialPack,
  WindowHotspotEvent,
} from "@/types";
import { buildWindowHotspots } from "@/api/windowHotspots";
import { smartFilterWindowHotspotList } from "@/api/windowHotspots";
import { batchCreateMaterialItems, createMaterialPack, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";
import MaterialBasketDrawer from "@/components/MaterialBasketDrawer.vue";

const route = useRoute();
const router = useRouter();

const limit = ref(20);
const windowKey = ref<"today" | "week" | "month" | "range">("today");
const rangeValue = ref<[string, string] | null>(null);
const windowItems = ref<WindowHotspotEvent[]>([]);
const windowLoading = ref(false);

const selectedWindowRows = ref<WindowHotspotEvent[]>([]);

const basket = useMaterialBasketStore();

const basketVisible = ref(false);
const openBasket = () => {
  basketVisible.value = true;
};

const addSelectedWindowToBasket = async () => {
  const rows = selectedWindowRows.value;
  if (!rows.length) {
    ElMessage.warning("请先勾选要加入素材篮的窗口热点事件");
    return;
  }

  addingToBasket.value = true;
  try {
    const toAdd: MaterialItemCreate[] = [];
    rows.forEach((r) => toAdd.push(..._windowEventToMaterialItems(r)));

    if (!toAdd.length) {
      ElMessage.warning("未生成任何可加入的素材条目");
      return;
    }

    basket.addMany(toAdd);
    ElMessage.success(`已加入素材篮：${toAdd.length} 条（素材篮共 ${basket.count} 条）`);
    basketVisible.value = true;
  } catch (err: any) {
    ElMessage.error(err.message || "加入素材篮失败");
  } finally {
    addingToBasket.value = false;
  }
};

const importDialogVisible = ref(false);
const importing = ref(false);
const addingToBasket = ref(false);
const importPackName = ref("");
const importPackDesc = ref("");
const importPackOptions = ref<MaterialPack[]>([]);

type _TopicRow = {
  event_key: string;
  recommended: boolean;
  score: number;
  reason?: string | null;
  checked: boolean;
  title: string;
  summary: string;
};

const topicDialogVisible = ref(false);
const topicLoading = ref(false);
const topicForm = ref({
  topic: "",
  instruction: "",
});
const topicDecisions = ref<_TopicRow[]>([]);
const topicFilterApplied = ref(false);
const topicSelectedKeys = ref<string[]>([]);

const displayItems = computed(() => {
  if (!topicFilterApplied.value) return windowItems.value;
  const allow = new Set(topicSelectedKeys.value);
  return windowItems.value.filter((x) => allow.has(windowRowKey(x)));
});

const importAlertTitle = computed(() => {
  return `将导入 ${selectedWindowRows.value.length} 个窗口热点事件的摘要/要点/引用/来源到素材包中`;
});

const openTopicFilter = async () => {
  if (windowItems.value.length === 0) {
    ElMessage.warning("当前无榜单数据，请先生成或刷新");
    return;
  }
  topicDialogVisible.value = true;
};

const runTopicFilter = async () => {
  const topic = (topicForm.value.topic || "").trim();
  if (!topic) {
    ElMessage.warning("请先输入主题");
    return;
  }

  if (windowKey.value === "range" && (!rangeValue.value || rangeValue.value.length !== 2)) {
    ElMessage.warning("请先选择日期范围");
    return;
  }

  topicLoading.value = true;
  try {
    const rangePayload =
      windowKey.value === "range" && rangeValue.value
        ? {
            start_time: `${rangeValue.value[0]} 00:00:00`,
            end_time: `${rangeValue.value[1]} 23:59:59`,
          }
        : {};

    const resp = await smartFilterWindowHotspotList({
      window: windowKey.value,
      topic,
      instruction: (topicForm.value.instruction || "").trim() || undefined,
      limit: limit.value,
      temperature: 0.2,
      ...rangePayload,
    });

    const map: Record<string, WindowHotspotEvent> = {};
    for (const it of windowItems.value) map[windowRowKey(it)] = it;

    topicDecisions.value = (resp.decisions || []).map((d) => {
      const ev = map[d.event_key];
      return {
        ...d,
        checked: !!d.recommended,
        title: ev?.title || d.event_key,
        summary: (ev?.summary as string) || "",
      };
    });
  } catch (err: any) {
    ElMessage.error(err.message || "智能筛选失败");
  } finally {
    topicLoading.value = false;
  }
};

const applyTopicFilter = () => {
  const keys = topicDecisions.value.filter((x) => x.checked).map((x) => x.event_key);
  topicSelectedKeys.value = keys;
  topicFilterApplied.value = true;
  topicDialogVisible.value = false;
  ElMessage.success(`已应用筛选：${keys.length} 条`);
};

const clearTopicFilter = () => {
  topicSelectedKeys.value = [];
  topicFilterApplied.value = false;
};

const formatDateTime = (s?: string | null) => {
  if (!s) return "";
  return String(s).replace("T", " ").replace("Z", "");
};

const onWindowRowClick = (row: WindowHotspotEvent, column: any) => {
  // 中文说明：避免勾选多选框时触发行点击打开详情
  if (column?.type === "selection") return;
  goWindowDetail(row);
};

const goWindowDetail = (row: WindowHotspotEvent) => {
  const key = windowRowKey(row);
  try {
    sessionStorage.setItem(`window_hotspot_detail:${key}`, JSON.stringify(row));
  } catch {
    // ignore
  }
  router.push({ path: `/window-hotspots/${encodeURIComponent(key)}`, query: route.query });
};

const onWindowSelectionChange = (rows: WindowHotspotEvent[]) => {
  selectedWindowRows.value = rows || [];
};

const windowRowKey = (row: WindowHotspotEvent) => {
  const t = (row?.title || "").trim();
  const te = (row?.event_time_end || "").trim();
  const u = ((row?.sources || [])[0]?.url || "").trim();
  return `${row.window || ""}|${t}|${te}|${u}`;
};

const onRangeChange = async () => {
  if (windowKey.value !== "range") return;
  if (!rangeValue.value || rangeValue.value.length !== 2) return;
  await fetchWindowList();
};

const fetchWindowList = async () => {
  if (windowKey.value === "range" && (!rangeValue.value || rangeValue.value.length !== 2)) {
    ElMessage.warning("请先选择日期范围");
    return;
  }

  windowLoading.value = true;
  try {
    const rangePayload =
      windowKey.value === "range" && rangeValue.value
        ? {
            start_time: `${rangeValue.value[0]} 00:00:00`,
            end_time: `${rangeValue.value[1]} 23:59:59`,
          }
        : {};
    const resp = await buildWindowHotspots({
      window: windowKey.value,
      limit: limit.value,
      use_llm: false,
      ...rangePayload,
    });
    windowItems.value = resp.items || [];
    selectedWindowRows.value = [];
    topicSelectedKeys.value = [];
    topicFilterApplied.value = false;
  } catch (err: any) {
    ElMessage.error(err.message || "获取窗口热点失败");
  } finally {
    windowLoading.value = false;
  }
};

const refreshCurrent = async () => {
  await fetchWindowList();
};

const onLimitChange = async () => {
  await fetchWindowList();
};

const _defaultWindowPackName = () => {
  const labelMap: Record<string, string> = {
    today: "今日",
    week: "本周",
    month: "本月",
    range: "范围",
  };
  const w = windowKey.value;
  return `${labelMap[w] || w} 窗口热点素材`;
};

const openWindowImportDialog = async () => {
  if (!selectedWindowRows.value.length) {
    ElMessage.warning("请先勾选要导入的窗口热点事件");
    return;
  }
  importPackName.value = importPackName.value.trim() || _defaultWindowPackName();
  if (!importPackDesc.value) {
    if (windowKey.value === "range" && rangeValue.value) {
      importPackDesc.value = `窗口热点一键导入：范围 ${rangeValue.value[0]}~${rangeValue.value[1]}`;
    } else {
      importPackDesc.value = `窗口热点一键导入：${windowKey.value}`;
    }
  }

  try {
    const resp = await listMaterialPacks({ limit: 200, offset: 0 });
    importPackOptions.value = resp.items || [];
  } catch {
    importPackOptions.value = [];
  }

  importDialogVisible.value = true;
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

const _windowEventToMaterialItems = (ev: WindowHotspotEvent): MaterialItemCreate[] => {
  const labelMap: Record<string, string> = {
    today: "今日",
    week: "本周",
    month: "本月",
    range: "范围",
  };
  const baseMeta = {
    event_title: ev.title,
    window: ev.window,
    window_key: ev.window,
    window_label: labelMap[String(ev.window || "")] || String(ev.window || ""),
    event_time_end: ev.event_time_end,
    event_time_start: ev.event_time_start,
    flags: ev.flags || undefined,
    _source: "window_hotspot",
  };

  const arr: MaterialItemCreate[] = [];

  const summary = (ev.summary || "").trim();
  if (summary) {
    arr.push({
      item_type: "note",
      text: summary,
      meta: { ...baseMeta, note_type: "summary" },
    });
  }

  (ev.bullets || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "bullet",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      meta: { ...baseMeta, hotspot_item_type: "bullet", position: it.position, score: it.score },
    });
  });

  (ev.quotes || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "quote",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      meta: { ...baseMeta, hotspot_item_type: "quote", position: it.position, score: it.score },
    });
  });

  (ev.sources || []).forEach((s: any) => {
    const url = (s?.url || "").trim();
    if (!url) return;
    const title = (s?.title || "").trim();
    arr.push({
      item_type: "source",
      text: title ? `${title}\n${url}` : url,
      source_url: url,
      source_content_id: s.content_id || undefined,
      meta: {
        ...baseMeta,
        domain: s.domain,
        is_list_parent: s.is_list_parent,
        time_confidence: s.time_confidence,
        source_event_time_end: s.event_time_end,
      },
    });
  });

  return arr;
};

const onBasketWritten = (packId: number) => {
  router.push(`/materials/packs/${packId}`);
};

const onBasketCreated = (packId: number) => {
  router.push(`/materials/packs/${packId}`);
};

const confirmImport = async () => {
  const name = (importPackName.value || "").trim();
  if (!name) {
    ElMessage.warning("请先填写素材包名称");
    return;
  }
  const rows = selectedWindowRows.value;
  if (!rows.length) {
    ElMessage.warning("请先勾选要导入的窗口热点事件");
    return;
  }

  importing.value = true;
  try {
    const pack = await _pickOrCreatePackByName(name);

    const items: MaterialItemCreate[] = [];
    rows.forEach((r) => items.push(..._windowEventToMaterialItems(r)));

    if (!items.length) {
      ElMessage.warning("未导入到任何素材条目");
      return;
    }

    await batchCreateMaterialItems(pack.id, { items });
    importDialogVisible.value = false;
    ElMessage.success(`已导入素材包「${pack.name}」：${items.length} 条`);
  } catch (err: any) {
    ElMessage.error(err.message || "导入素材包失败");
  } finally {
    importing.value = false;
  }
};

const getRankClass = (rank: number) => {
  if (rank === 1) return "rank-1";
  if (rank === 2) return "rank-2";
  if (rank === 3) return "rank-3";
  return "rank-other";
};

onMounted(async () => {
  const qLimit = route.query.limit;
  if (typeof qLimit === "string" && qLimit && !Number.isNaN(Number(qLimit))) limit.value = Number(qLimit);
  const qWin = route.query.window;
  if (typeof qWin === "string" && ["today", "week", "month"].includes(qWin)) {
    windowKey.value = qWin as any;
  } else if (qWin === "realtime") {
    windowKey.value = "today";
  }

  await fetchWindowList();
});

watch(
  () => [windowKey.value, limit.value],
  () => {
    const q = {
      ...route.query,
      window: windowKey.value,
      limit: String(limit.value),
    } as Record<string, any>;
    router.replace({ path: "/daily-hotspots", query: q });
  }
);
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

.main-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.left-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1 1 520px;
}

.right-panel {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1 1 420px;
}

.event-title {
  font-weight: 500;
  color: #111827;
}

.summary-text {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rank-num {
  font-weight: 700;
  font-style: italic;
  font-size: 16px;
}

.rank-1 { color: #f56c6c; font-size: 20px; }
.rank-2 { color: #e6a23c; font-size: 18px; }
.rank-3 { color: #409eff; font-size: 18px; }
.rank-other { color: #909399; }

.hot-score {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-weight: 600;
  color: #303133;
}

.text-sm {
  font-size: 12px;
}
</style>
