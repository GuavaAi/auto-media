<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <div class="nav-row">
          <el-button link @click="router.back()" class="back-btn">
            <el-icon><ArrowLeft /></el-icon>
            返回抓取列表
          </el-button>
        </div>
        <div class="title-row">
          <h2 class="page-title">{{ record?.title || `记录 #${recordId}` }}</h2>
          <el-tag v-if="record?.source_type" size="small" type="primary" effect="plain">{{ record.source_type }}</el-tag>
        </div>
        <p class="page-desc">
          数据源 ID: {{ record?.datasource_id }} · 抓取时间: {{ formatDate(record?.fetched_at || null) }}
        </p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="copyText(record?.content || '')">
          <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
          复制原文内容
        </el-button>

        <el-button :loading="extracting" @click="onExtractToBasket">
          <el-icon class="el-icon--left"><Plus /></el-icon>
          抽取素材到素材篮
        </el-button>

        <el-button type="success" :loading="extracting || exportToPackLoading" @click="openExportToPack">
          <el-icon class="el-icon--left"><Upload /></el-icon>
          抽取并写入素材包
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <el-skeleton v-if="loading" :rows="8" animated />
      <div v-else-if="record" class="detail-content">
        <el-tabs type="border-card" class="detail-tabs">
          <el-tab-pane label="原文内容">
            <div class="content-wrapper">
              <el-input
                v-model="content"
                type="textarea"
                :rows="20"
                readonly
                resize="none"
                class="content-editor"
              />
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="元数据 & 清洗信息">
            <div class="meta-panel">
              <el-descriptions title="基础信息" :column="2" border>
                <el-descriptions-item label="记录 ID">{{ record.id }}</el-descriptions-item>
                <el-descriptions-item label="来源标识">{{ record.title || "-" }}</el-descriptions-item>
                <el-descriptions-item label="数据源名称">{{ record.datasource_name || "-" }}</el-descriptions-item>
                <el-descriptions-item label="URL / 路径" :span="2">
                  <a v-if="isUrl(record.url)" :href="record.url || ''" target="_blank" class="link">{{ record.url }}</a>
                  <span v-else>{{ record.url || "-" }}</span>
                </el-descriptions-item>
              </el-descriptions>

              <div class="divider"></div>

              <el-descriptions title="处理详情" :column="2" border>
                <el-descriptions-item label="正文抽取器">
                  <el-tag size="small" type="info">{{ extractor || "默认" }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="质量标记">
                  <div v-if="qualityFlags.length" class="tag-row">
                    <el-tag v-for="f in qualityFlags" :key="f" size="small" type="warning">{{ f }}</el-tag>
                  </div>
                  <span v-else class="muted">无标记</span>
                </el-descriptions-item>

                <el-descriptions-item label="清洗关键指标" :span="2">
                  <div v-if="cleanKeyStats.length" class="stat-row">
                    <el-tag v-for="it in cleanKeyStats" :key="it.key" size="small" type="success" effect="plain">
                      {{ it.label }}: {{ it.value }}
                    </el-tag>
                  </div>
                  <span v-else class="muted">无清洗统计</span>
                </el-descriptions-item>
              </el-descriptions>

              <div class="divider"></div>

              <el-collapse v-if="cleanMoreStats.length" class="more-stats">
                <el-collapse-item title="更多清洗指标" name="more">
                  <el-descriptions :column="2" border>
                    <el-descriptions-item v-for="it in cleanMoreStats" :key="it.key" :label="it.label">
                      {{ it.value }}
                    </el-descriptions-item>
                  </el-descriptions>
                </el-collapse-item>
              </el-collapse>

              <div v-if="cleanMoreStats.length" class="divider"></div>

              <div class="json-section">
                <div class="section-title">完整 Extra JSON</div>
                <div class="json-box">
                  <pre>{{ pretty(record.extra) }}</pre>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <el-empty v-else description="未找到记录信息" />
    </el-card>

    <el-dialog v-model="exportToPackVisible" title="抽取素材写入到素材包" width="640px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="目标素材包" required>
          <el-select
            v-model="exportPackName"
            filterable
            clearable
            allow-create
            default-first-option
            placeholder="输入或选择素材包"
            style="width: 100%"
          >
            <el-option
              v-for="p in exportPackOptions"
              :key="p.id"
              :label="`#${p.id} ${p.name}`"
              :value="p.name"
            />
          </el-select>
        </el-form-item>

        <el-alert
          title="将从当前抓取记录中抽取要点（并附带来源条目），写入到素材包。"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="exportToPackVisible = false">取消</el-button>
        <el-button type="primary" :loading="exportToPackLoading" @click="onExtractAndExportToPack">写入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowLeft, DocumentCopy, Plus, Upload } from "@element-plus/icons-vue";
import { extractCrawlRecordMaterials, getCrawlRecord } from "@/api/crawlRecords";
import { batchCreateMaterialItems, createMaterialPack, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";
import type { CrawlRecordDetail, MaterialItemCreate, MaterialPack } from "@/types";
import { formatDate } from "@/utils/date";

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const record = ref<CrawlRecordDetail | null>(null);
const content = ref("");

const basket = useMaterialBasketStore();

const extracting = ref(false);

const exportToPackVisible = ref(false);
const exportToPackLoading = ref(false);
const exportPackName = ref("");
const exportPackOptions = ref<MaterialPack[]>([]);

const recordId = computed(() => Number(route.params.id));

const fetchDetail = async () => {
  const id = recordId.value;
  if (Number.isNaN(id)) {
    ElMessage.error("记录 ID 无效");
    return;
  }
  loading.value = true;
  try {
    record.value = await getCrawlRecord(id);
    content.value = record.value?.content || "";
  } catch (err: any) {
    ElMessage.error(err.message || "获取抓取详情失败");
  } finally {
    loading.value = false;
  }
};

onMounted(fetchDetail);

const _extractItems = async (): Promise<MaterialItemCreate[]> => {
  const id = recordId.value;
  if (Number.isNaN(id) || id <= 0) {
    ElMessage.error("记录 ID 无效");
    return [];
  }

  extracting.value = true;
  try {
    const resp = await extractCrawlRecordMaterials(id, { include_source: true });
    return resp.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "抽取素材失败");
    return [];
  } finally {
    extracting.value = false;
  }
};

const onExtractToBasket = async () => {
  const items = await _extractItems();
  if (!items.length) {
    ElMessage.warning("未抽取到素材");
    return;
  }
  basket.addMany(items);
  ElMessage.success(`已加入素材篮：${items.length} 条`);
};

const loadExportPackOptions = async () => {
  try {
    const resp = await listMaterialPacks({ keyword: undefined, limit: 200, offset: 0 });
    exportPackOptions.value = resp.items || [];
  } catch (err: any) {
    exportPackOptions.value = [];
    ElMessage.error(err.message || "加载素材包列表失败");
  }
};

const _defaultPackName = () => {
  const t = (record.value?.title || "").trim();
  if (t) return t;
  return `抓取记录 #${recordId.value}`;
};

const _pickOrCreatePackByName = async (name: string): Promise<MaterialPack> => {
  const n = (name || "").trim();
  const existed = exportPackOptions.value.find((p) => (p.name || "").trim() === n);
  if (existed) return existed;
  const resp = await listMaterialPacks({ keyword: n, limit: 50, offset: 0 });
  const existed2 = (resp.items || []).find((p) => (p.name || "").trim() === n);
  if (existed2) return existed2;
  return await createMaterialPack({ name: n, description: "抓取记录抽取素材" });
};

const openExportToPack = async () => {
  exportPackName.value = exportPackName.value.trim() || _defaultPackName();
  exportToPackVisible.value = true;
  await loadExportPackOptions();
};

const onExtractAndExportToPack = async () => {
  const name = exportPackName.value.trim();
  if (!name) {
    ElMessage.warning("请输入或选择素材包");
    return;
  }

  exportToPackLoading.value = true;
  try {
    const items = await _extractItems();
    if (!items.length) {
      ElMessage.warning("未抽取到素材");
      return;
    }

    const pack = await _pickOrCreatePackByName(name);
    await batchCreateMaterialItems(pack.id, { items });
    ElMessage.success("已写入到素材包");
    exportToPackVisible.value = false;
    router.push(`/materials/packs/${pack.id}`);
  } catch (err: any) {
    ElMessage.error(err.message || "写入失败");
  } finally {
    exportToPackLoading.value = false;
  }
};

const pretty = (obj: unknown) => {
  if (obj == null) return "{}";
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
};

const getExtraObj = (): Record<string, any> => {
  const extra = record.value?.extra;
  if (!extra || typeof extra !== "object") return {};
  return extra as Record<string, any>;
};

const extractor = computed(() => {
  const extra = getExtraObj();
  return typeof extra.extractor === "string" ? extra.extractor : "";
});

const qualityFlags = computed(() => {
  const extra = getExtraObj();
  return Array.isArray(extra.quality_flags)
    ? extra.quality_flags.map((x: any) => String(x))
    : [];
});

const cleanStats = computed(() => {
  const extra = getExtraObj();
  const s = extra.clean_stats;
  return s && typeof s === "object" ? (s as Record<string, any>) : null;
});

const cleanKeyStats = computed(() => {
  const s = cleanStats.value;
  if (!s) return [] as Array<{ key: string; label: string; value: string }>;

  const getNum = (k: string) => {
    const v = s[k];
    return typeof v === "number" ? v : null;
  };

  const rawLen = getNum("raw_len");
  const cleanLen = getNum("clean_len");
  const removedByKeyword = getNum("removed_by_keyword") || 0;
  const removedShortNoise = getNum("removed_short_noise") || 0;
  const removedDupParagraph = getNum("removed_dup_paragraph") || 0;
  const removedTotal = removedByKeyword + removedShortNoise + removedDupParagraph;

  const items: Array<{ key: string; label: string; value: string }> = [];
  if (rawLen != null) items.push({ key: "raw_len", label: "原始长度", value: String(rawLen) });
  if (cleanLen != null) items.push({ key: "clean_len", label: "清洗后长度", value: String(cleanLen) });
  items.push({ key: "removed_total", label: "移除段/行", value: String(removedTotal) });
  if (typeof s.paragraph_count === "number") {
    items.push({ key: "paragraph_count", label: "段落数", value: String(s.paragraph_count) });
  }
  if (typeof s.line_count === "number") {
    items.push({ key: "line_count", label: "行数", value: String(s.line_count) });
  }
  return items.slice(0, 5);
});

const cleanMoreStats = computed(() => {
  const s = cleanStats.value;
  if (!s) return [] as Array<{ key: string; label: string; value: string }>;

  const items: Array<{ key: string; label: string; value: string }> = [];
  Object.keys(s)
    .sort()
    .forEach((k) => {
      if (k === "raw_len" || k === "clean_len" || k === "paragraph_count" || k === "line_count") return;
      if (k === "removed_by_keyword" || k === "removed_short_noise" || k === "removed_dup_paragraph") return;
      const v = (s as any)[k];
      if (v == null) return;
      items.push({ key: k, label: k, value: typeof v === "object" ? pretty(v) : String(v) });
    });

  const removedByKeyword = typeof s.removed_by_keyword === "number" ? s.removed_by_keyword : null;
  const removedShortNoise = typeof s.removed_short_noise === "number" ? s.removed_short_noise : null;
  const removedDupParagraph = typeof s.removed_dup_paragraph === "number" ? s.removed_dup_paragraph : null;
  if (removedByKeyword != null) items.unshift({ key: "removed_by_keyword", label: "按关键词移除", value: String(removedByKeyword) });
  if (removedShortNoise != null) items.unshift({ key: "removed_short_noise", label: "短噪声移除", value: String(removedShortNoise) });
  if (removedDupParagraph != null) items.unshift({ key: "removed_dup_paragraph", label: "重复段落移除", value: String(removedDupParagraph) });

  if (typeof s.min_line_len === "number") items.push({ key: "min_line_len", label: "min_line_len", value: String(s.min_line_len) });
  if (typeof s.min_text_len === "number") items.push({ key: "min_text_len", label: "min_text_len", value: String(s.min_text_len) });
  return items;
});

const isUrl = (s?: string | null) => !!s && (s.startsWith("http://") || s.startsWith("https://"));

const copyText = async (text: string) => {
  if (!text) {
    ElMessage.warning("内容为空");
    return;
  }
  await navigator.clipboard.writeText(text);
  ElMessage.success("已复制内容");
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

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}

.page-desc {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.main-card {
  border-radius: 8px;
  min-height: 500px;
}

.detail-tabs {
  min-height: 500px;
  box-shadow: none;
  border: 1px solid #dcdfe6;
}

.content-wrapper {
  padding: 0;
}

.content-editor :deep(.el-textarea__inner) {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  background-color: #f9fafb;
  padding: 16px;
  border: none;
}

.meta-panel {
  padding: 16px;
}

.divider {
  height: 24px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.link {
  color: #409eff;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.muted {
  color: #909399;
}

.json-section {
  margin-top: 16px;
}

.section-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
  color: #303133;
}

.json-box {
  background: #1e293b;
  border-radius: 6px;
  padding: 16px;
  overflow: auto;
  max-height: 400px;
}

.json-box pre {
  margin: 0;
  color: #e2e8f0;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}
</style>
