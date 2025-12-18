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
        <el-button type="primary" size="large" :loading="building" @click="build">
          <el-icon class="el-icon--left"><MagicStick /></el-icon>
          生成今日榜单 (Build)
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="left-panel">
            <el-date-picker
              v-model="day"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 180px"
              :clearable="false"
              @change="fetchList"
            />
            <el-divider direction="vertical" />
             <el-radio-group v-model="limit" size="default" @change="fetchList">
              <el-radio-button :value="20">Top 20</el-radio-button>
              <el-radio-button :value="50">Top 50</el-radio-button>
              <el-radio-button :value="100">Top 100</el-radio-button>
            </el-radio-group>
          </div>
          <div class="right-panel">
            <el-button @click="openBasket">素材篮 ({{ basket.count }})</el-button>

            <el-button
              :disabled="items.length === 0"
              @click="openTopicFilter"
            >
              <el-icon class="el-icon--left"><MagicStick /></el-icon>
              主题智能筛选
            </el-button>

            <el-button
              type="warning"
              :disabled="selectedEventIds.length === 0"
              :loading="addingToBasket"
              @click="addSelectedToBasket"
            >
              加入素材篮
              <span v-if="selectedEventIds.length" style="margin-left: 6px">({{ selectedEventIds.length }})</span>
            </el-button>

            <el-button
              type="success"
              :disabled="selectedEventIds.length === 0"
              :loading="importing"
              @click="openImportDialog"
            >
              一键导入素材包
              <span v-if="selectedEventIds.length" style="margin-left: 6px">({{ selectedEventIds.length }})</span>
            </el-button>

            <el-button v-if="topicFilterApplied" @click="clearTopicFilter">
              清除筛选
            </el-button>

            <el-tooltip content="刷新列表" placement="top">
              <el-button circle @click="fetchList" :loading="loading">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <el-empty v-if="!loading && items.length === 0" description="暂无该日榜单数据" :image-size="200">
        <el-button type="primary" plain @click="build" v-if="isToday(day)">立即生成</el-button>
      </el-empty>

      <el-table
        v-else
        :data="displayItems"
        stripe
        size="default"
        class="data-table"
        v-loading="loading"
        highlight-current-row
        @row-click="onRowClick"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="52" align="center" />
        <el-table-column label="排名" width="80" align="center">
          <template #default="{ $index }">
            <span class="rank-num" :class="getRankClass($index + 1)">{{ $index + 1 }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="title" label="热点事件" min-width="200">
          <template #default="{ row }">
             <div class="event-title">{{ row.title }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="summary" label="智能摘要" min-width="350">
          <template #default="{ row }">
            <div class="summary-text">{{ row.summary || "暂无摘要" }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="hot_score" label="热度值" width="120" align="center" sortable>
          <template #default="{ row }">
            <span class="hot-score">
              <el-icon color="#f56c6c"><DataAnalysis /></el-icon>
              {{ row.hot_score.toLocaleString() }}
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
            <el-button type="primary" link @click.stop="goDetail(row.id)">
               详情
               <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

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
        <el-button type="primary" :disabled="topicDecisions.length === 0" @click="applyTopicFilter">
          应用筛选
        </el-button>
      </template>
    </el-dialog>

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
          :title="`将导入 ${selectedEventIds.length} 个热点事件的要点/引用/事实/来源到素材包中`"
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

    <MaterialBasketDrawer v-model="basketVisible" @written="onBasketWritten" @created="onBasketCreated" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, MagicStick, DataAnalysis, ArrowRight } from "@element-plus/icons-vue";
import type { DailyHotspotDetailResponse, DailyHotspotEvent, MaterialItemCreate, MaterialPack } from "@/types";
import { buildDailyHotspots, getDailyHotspotDetail, listDailyHotspots, smartFilterDailyHotspotList } from "@/api/dailyHotspots";
import { batchCreateMaterialItems, createMaterialPack, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";
import MaterialBasketDrawer from "@/components/MaterialBasketDrawer.vue";

const route = useRoute();
const router = useRouter();

const todayDate = new Date();
const pad = (n: number) => String(n).padStart(2, "0");
const todayStr = `${todayDate.getFullYear()}-${pad(todayDate.getMonth() + 1)}-${pad(todayDate.getDate())}`;

const day = ref(todayStr);
const limit = ref(20);
const loading = ref(false);
const building = ref(false);
const items = ref<DailyHotspotEvent[]>([]);

const basket = useMaterialBasketStore();

const basketVisible = ref(false);
const openBasket = () => {
  basketVisible.value = true;
};

const selectedEventIds = ref<number[]>([]);

const importDialogVisible = ref(false);
const importing = ref(false);
const addingToBasket = ref(false);
const importPackName = ref("");
const importPackDesc = ref("");
const importPackOptions = ref<MaterialPack[]>([]);

type _TopicRow = {
  event_id: number;
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
const topicSelectedIds = ref<number[]>([]);

const displayItems = computed(() => {
  if (!topicFilterApplied.value) return items.value;
  const allow = new Set(topicSelectedIds.value);
  return items.value.filter((x) => allow.has(x.id));
});

const fetchList = async () => {
  loading.value = true;
  try {
    const resp = await listDailyHotspots(day.value, limit.value);
    items.value = resp.items || [];
    // 切换日期/重刷时，如果筛选结果不在新列表中，会自动过滤为空；这里不强制清除

    // 将当前 day/limit 持久化到路由，保证从详情页返回后不重置
    const q = { ...route.query, day: day.value, limit: String(limit.value) } as Record<string, any>;
    router.replace({ path: "/daily-hotspots", query: q });
  } catch (err: any) {
    ElMessage.error(err.message || "获取热点榜单失败");
  } finally {
    loading.value = false;
  }
};

const build = async () => {
  building.value = true;
  try {
    const resp = await buildDailyHotspots(day.value, limit.value);
    items.value = resp.items || [];
    ElMessage.success("已生成榜单");
  } catch (err: any) {
    ElMessage.error(err.message || "生成榜单失败");
  } finally {
    building.value = false;
  }
};

const openTopicFilter = async () => {
  if (items.value.length === 0) {
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
  topicLoading.value = true;
  try {
    const resp = await smartFilterDailyHotspotList({
      day: day.value,
      topic,
      instruction: (topicForm.value.instruction || "").trim() || undefined,
      limit: limit.value,
      temperature: 0.2,
    });

    const map: Record<number, DailyHotspotEvent> = {};
    for (const it of items.value) map[it.id] = it;

    topicDecisions.value = (resp.decisions || []).map((d) => {
      const ev = map[d.event_id];
      return {
        ...d,
        checked: !!d.recommended,
        title: ev?.title || `#${d.event_id}`,
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
  const ids = topicDecisions.value.filter((x) => x.checked).map((x) => x.event_id);
  topicSelectedIds.value = ids;
  topicFilterApplied.value = true;
  topicDialogVisible.value = false;
  ElMessage.success(`已应用筛选：${ids.length} 条`);

  // 持久化筛选条件到路由（用于从详情返回后恢复）
  const topic = (topicForm.value.topic || "").trim();
  const q = {
    ...route.query,
    day: day.value,
    limit: String(limit.value),
    topic,
    topic_ids: ids.join(","),
  } as Record<string, any>;
  router.replace({ path: "/daily-hotspots", query: q });
};

const clearTopicFilter = () => {
  topicSelectedIds.value = [];
  topicFilterApplied.value = false;

  // 仅手动清除才移除路由里的筛选参数
  const q = { ...route.query } as Record<string, any>;
  delete q.topic;
  delete q.topic_ids;
  router.replace({ path: "/daily-hotspots", query: q });
};

const goDetail = (id: number) => router.push({ path: `/daily-hotspots/${id}`, query: route.query });

const onRowClick = (row: DailyHotspotEvent, column: any) => {
  // 中文说明：避免勾选多选框时触发行点击跳转
  if (column?.type === "selection") return;
  goDetail(row.id);
};

const onSelectionChange = (rows: DailyHotspotEvent[]) => {
  selectedEventIds.value = (rows || []).map((r) => Number(r.id)).filter((n) => Number.isFinite(n) && n > 0);
};

const _defaultPackName = () => {
  const t = (topicForm.value.topic || "").trim();
  if (t) return t;
  return `${day.value} 热点素材`;
};

const openImportDialog = async () => {
  if (!selectedEventIds.value.length) {
    ElMessage.warning("请先勾选要导入的热点事件");
    return;
  }
  importPackName.value = importPackName.value.trim() || _defaultPackName();
  importPackDesc.value = importPackDesc.value || `热点榜单一键导入：${day.value}`;

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

const _detailToMaterialItems = (detail: DailyHotspotDetailResponse): MaterialItemCreate[] => {
  const eventId = Number(detail.event?.id);
  const eventTitle = detail.event?.title || "";
  const baseMeta = {
    event_id: eventId,
    event_title: eventTitle,
    event_day: detail.event?.day,
    _source: "daily_hotspot",
  };

  const arr: MaterialItemCreate[] = [];
  (detail.bullets || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "bullet",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "bullet" },
    });
  });
  (detail.quotes || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "quote",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "quote" },
    });
  });
  (detail.facts || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "fact",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "fact" },
    });
  });
  (detail.sources || []).forEach((s: any) => {
    const url = (s?.url || "").trim();
    if (!url) return;
    const title = (s?.title || "").trim();
    arr.push({
      item_type: "source",
      text: title ? `${title}\n${url}` : url,
      source_url: url,
      source_content_id: s.content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, weight: s.weight, hotspot_source_id: s.id },
    });
  });

  return arr;
};

const addSelectedToBasket = async () => {
  const ids = selectedEventIds.value;
  if (!ids.length) {
    ElMessage.warning("请先勾选要加入素材篮的热点事件");
    return;
  }

  addingToBasket.value = true;
  try {
    // 中文说明：并发拉取热点详情并转成素材条目（后续如数据量变大可加并发限制）
    const details = await Promise.all(ids.map((id) => getDailyHotspotDetail(id)));
    const toAdd: MaterialItemCreate[] = [];
    details.forEach((d) => toAdd.push(..._detailToMaterialItems(d)));

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
  const ids = selectedEventIds.value;
  if (!ids.length) {
    ElMessage.warning("请先勾选要导入的热点事件");
    return;
  }

  importing.value = true;
  try {
    const pack = await _pickOrCreatePackByName(name);

    // 中文说明：并发拉取热点详情并转成素材条目（可能较多，后续可加并发限制）
    const details = await Promise.all(ids.map((id) => getDailyHotspotDetail(id)));
    const items: MaterialItemCreate[] = [];
    details.forEach((d) => items.push(..._detailToMaterialItems(d)));

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

const isToday = (d: string) => d === todayStr;

const getRankClass = (rank: number) => {
  if (rank === 1) return "rank-1";
  if (rank === 2) return "rank-2";
  if (rank === 3) return "rank-3";
  return "rank-other";
};

onMounted(async () => {
  // 从路由恢复 day/limit/筛选（从详情返回时不会丢）
  const qDay = route.query.day;
  if (typeof qDay === "string" && qDay) day.value = qDay;
  const qLimit = route.query.limit;
  if (typeof qLimit === "string" && qLimit && !Number.isNaN(Number(qLimit))) limit.value = Number(qLimit);

  const qTopic = route.query.topic;
  const qIds = route.query.topic_ids;
  if (typeof qTopic === "string" && qTopic && typeof qIds === "string" && qIds.trim()) {
    topicForm.value.topic = qTopic;
    const ids = qIds
      .split(",")
      .map((x) => Number(x))
      .filter((x) => Number.isFinite(x) && x > 0);
    if (ids.length) {
      topicSelectedIds.value = ids;
      topicFilterApplied.value = true;
    }
  }

  await fetchList();
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
}

.left-panel {
  display: flex;
  align-items: center;
  gap: 16px;
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
</style>
