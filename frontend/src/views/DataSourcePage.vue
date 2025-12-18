<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">数据源管理</h2>
        <p class="page-desc">
          管理你的内容抓取入口。支持 URL、API、文档上传及 n8n Webhook 集成，保持内容库的新鲜度。
        </p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="openCreate">
          <el-icon class="el-icon--left"><Plus /></el-icon>
          新建数据源
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="left-panel">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索数据源名称..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-divider direction="vertical" />
            <el-radio-group v-model="filterType" size="small">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="url">URL</el-radio-button>
              <el-radio-button label="api">API</el-radio-button>
              <el-radio-button label="n8n">n8n</el-radio-button>
            </el-radio-group>
          </div>
          <div class="right-panel">
             <el-tooltip content="刷新列表" placement="top">
                <el-button circle @click="fetchList" :loading="loading">
                  <el-icon><Refresh /></el-icon>
                </el-button>
             </el-tooltip>
          </div>
        </div>
      </template>

      <el-table :data="filteredList" stripe size="default" class="data-table" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="name" label="名称" min-width="150">
          <template #default="{ row }">
            <span class="name-text">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getSourceTypeTag(row.source_type)" size="small" effect="light">
              {{ row.source_type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="biz_category" label="分类" width="100" align="center">
          <template #default="{ row }">
             <el-tag v-if="row.biz_category" size="small" type="info">{{ row.biz_category }}</el-tag>
             <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="enable_schedule" label="自动抓取" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.enable_schedule"
              size="small"
              disabled
              style="--el-switch-on-color: #13ce66"
            />
          </template>
        </el-table-column>
        <el-table-column label="调度信息" width="220">
          <template #default="{ row }">
            <div class="schedule-info">
              <div v-if="row.schedule_cron" class="cron-tag">
                <el-icon><Timer /></el-icon>
                <span>{{ row.schedule_cron }}</span>
              </div>
              <div class="time-info">
                <span v-if="row.last_run_at" class="last-run">上次: {{ formatDate(row.last_run_at) }}</span>
                <span v-if="row.next_run_at" class="next-run">下次: {{ formatDate(row.next_run_at) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="立即触发抓取" placement="top">
                <el-button
                  circle
                  size="small"
                  type="success"
                  plain
                  :loading="!!triggerLoading[row.id]"
                  @click="onTrigger(row.id)"
                >
                  <el-icon><VideoPlay /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                 <el-button circle size="small" type="primary" plain @click="onEdit(row)">
                   <el-icon><Edit /></el-icon>
                 </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                 <el-button circle size="small" type="danger" plain @click="onDelete(row)">
                   <el-icon><Delete /></el-icon>
                 </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑/新增弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑数据源' : '新建数据源'"
      width="720px"
      align-center
      destroy-on-close
      @closed="reset"
    >
      <el-form :model="form" label-position="top" class="dialog-form">
        <el-row :gutter="24">
          <el-col :span="16">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" placeholder="例如：行业科技资讯源" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
             <el-form-item label="业务分类">
              <el-select v-model="form.biz_category" placeholder="选择分类" clearable>
                <el-option label="人工智能" value="人工智能" />
                <el-option label="科技" value="科技" />
                <el-option label="财经" value="财经" />
                <el-option label="生活" value="生活" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="数据源类型" required>
          <el-radio-group v-model="form.source_type" size="large">
            <el-radio-button label="url">网页 URL</el-radio-button>
            <el-radio-button label="api">API 接口</el-radio-button>
            <el-radio-button label="document">文档 (OSS)</el-radio-button>
            <el-radio-button label="n8n">n8n Webhook</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 动态配置区域 -->
        <div class="config-area">
          <el-form-item v-if="form.source_type === 'url'" label="URL 列表" required>
            <el-input
              v-model="urlInput"
              type="textarea"
              :rows="4"
              placeholder="请输入目标网页地址，多个地址请换行或用逗号分隔"
            />
          </el-form-item>

          <template v-if="form.source_type === 'api'">
            <el-form-item label="API 模式" required>
              <el-select v-model="apiMode" placeholder="选择模式" style="width: 100%">
                <el-option label="自定义 HTTP" value="http" />
                <el-option label="Firecrawl 搜索（关键词）" value="firecrawl_search" />
                <el-option label="阿里统一搜索（关键词）" value="aliyun_unified_search" />
              </el-select>
            </el-form-item>

            <el-form-item v-if="apiMode === 'http'" label="API 地址" required>
              <el-input v-model="apiUrlInput" placeholder="https://api.example.com/v1/posts" />
            </el-form-item>

            <template v-if="apiMode === 'firecrawl_search'">
              <el-form-item label="Search Query" required>
                <el-input v-model="firecrawlQuery" type="textarea" :rows="2" placeholder="例如：AI 监管政策 最新" />
              </el-form-item>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="返回条数">
                    <el-input v-model.number="firecrawlLimit" type="number" placeholder="默认 10" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="时间范围">
                    <el-select v-model="firecrawlTbs" placeholder="不限" style="width: 100%">
                      <el-option label="不限" value="" />
                      <el-option label="1 小时内" value="qdr:h" />
                      <el-option label="1 天内" value="qdr:d" />
                      <el-option label="1 周内" value="qdr:w" />
                      <el-option label="1 月内" value="qdr:m" />
                      <el-option label="1 年内" value="qdr:y" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="Sources">
                <el-select v-model="firecrawlSources" multiple placeholder="默认 web" style="width: 100%">
                  <el-option label="web" value="web" />
                  <el-option label="news" value="news" />
                </el-select>
              </el-form-item>
              <el-alert title="该数据源为关键词搜索模式，不依赖 URL 列表。" type="info" show-icon :closable="false" />
            </template>

            <template v-if="apiMode === 'aliyun_unified_search'">
              <el-form-item label="Search Query" required>
                <el-input v-model="aliyunQuery" type="textarea" :rows="2" placeholder="例如：AI 监管政策 最新" />
              </el-form-item>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="搜索引擎">
                    <el-select v-model="aliyunEngineType" style="width: 100%">
                      <el-option label="Generic（标准）" value="Generic" />
                      <el-option label="GenericAdvanced（增强）" value="GenericAdvanced" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="时间范围">
                    <el-select v-model="aliyunTimeRange" style="width: 100%">
                      <el-option label="不限" value="NoLimit" />
                      <el-option label="1 天内" value="OneDay" />
                      <el-option label="1 周内" value="OneWeek" />
                      <el-option label="1 月内" value="OneMonth" />
                      <el-option label="1 年内" value="OneYear" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="分类（可选）">
                <el-select v-model="aliyunCategory" clearable filterable placeholder="不限" style="width: 100%">
                  <el-option label="finance 金融" value="finance" />
                  <el-option label="law 法律" value="law" />
                  <el-option label="medical 医疗" value="medical" />
                  <el-option label="internet 互联网（精选）" value="internet" />
                  <el-option label="tax 税务" value="tax" />
                  <el-option label="news_province 新闻省级" value="news_province" />
                  <el-option label="news_center 新闻中央" value="news_center" />
                </el-select>
              </el-form-item>
              <el-alert title="该数据源为关键词搜索模式，不依赖 URL 列表。" type="info" show-icon :closable="false" />
            </template>
          </template>

          <el-form-item v-if="form.source_type === 'n8n'" label="Webhook 地址" required>
            <el-input v-model="n8nWebhook" placeholder="https://n8n.example.com/webhook/..." />
          </el-form-item>

          <el-form-item v-if="form.source_type === 'document'" label="OSS 文档 URL" required>
            <el-input
              v-model="docOssUrl"
              placeholder="上传后填入 OSS 访问地址"
            >
              <template #append>
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="onSelectFile"
                >
                  <el-button>选择文件</el-button>
                </el-upload>
              </template>
            </el-input>
            <div v-if="fileList.length" class="upload-tip">
               已选择: {{ fileList[0].name }} (模拟上传，请手动填入 OSS 地址)
            </div>
          </el-form-item>
        </div>

        <el-form-item v-if="shouldShowAdvancedConfig" label="高级配置">
           <AdvancedConfig v-model="advancedConfig" :source-type="form.source_type" :preview-url="previewUrl" />
        </el-form-item>

        <el-divider />

        <div class="schedule-config">
          <el-form-item label="启用定时抓取">
             <el-switch v-model="form.enable_schedule" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          
          <el-form-item v-if="form.enable_schedule" label="Cron 表达式" class="cron-item">
            <CronBuilder v-model="form.schedule_cron" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="save">保存配置</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile, UploadUserFile } from "element-plus";
import { 
  Plus, 
  Search, 
  Refresh, 
  VideoPlay, 
  Edit, 
  Delete,
  Timer
} from "@element-plus/icons-vue";
import {
  createDataSource,
  deleteDataSource,
  listDataSources,
  triggerDataSource,
  updateDataSource,
} from "@/api/datasources";
import type { DataSource } from "@/types";
import CronBuilder from "@/components/CronBuilder.vue";
import AdvancedConfig from "@/components/AdvancedConfig.vue";
import { formatDate } from "@/utils/date";

const list = ref<DataSource[]>([]);
const loading = ref(false);
const triggerLoading = reactive<Record<number, boolean>>({});
const dialogVisible = ref(false);
const urlInput = ref("");
const apiUrlInput = ref("");
const apiMode = ref<string>("http");
const firecrawlQuery = ref<string>("");
const firecrawlLimit = ref<number | null>(null);
const firecrawlTbs = ref<string>("");
const firecrawlSources = ref<string[]>(["web"]);
const aliyunQuery = ref<string>("");
const aliyunEngineType = ref<string>("Generic");
const aliyunTimeRange = ref<string>("NoLimit");
const aliyunCategory = ref<string>("");
const n8nWebhook = ref("");
const docOssUrl = ref("");
const fileList = ref<UploadUserFile[]>([]);
const editingId = ref<number | null>(null);
const advancedConfig = ref<Record<string, unknown>>({});

const previewUrl = computed(() => {
  if (form.source_type !== "url") return "";
  const urls = urlInput.value
    .split(/[\n,]/)
    .map((u) => u.trim())
    .filter(Boolean);
  return urls[0] || "";
});

const shouldShowAdvancedConfig = computed(() => {
  if (form.source_type === "document") return false;
  if (form.source_type !== "api") return true;
  return apiMode.value === "http";
});

// 筛选与搜索
const searchKeyword = ref("");
const filterType = ref("");

const filteredList = computed(() => {
  let res = list.value;
  if (filterType.value) {
    res = res.filter(item => item.source_type === filterType.value);
  }
  if (searchKeyword.value) {
    const k = searchKeyword.value.toLowerCase();
    res = res.filter(item => item.name.toLowerCase().includes(k) || String(item.id).includes(k));
  }
  return res;
});

const form = reactive({
  name: "",
  source_type: "url",
  config: {} as Record<string, unknown> | null,
  biz_category: "",
  schedule_cron: "",
  enable_schedule: false,
});

const fetchList = async () => {
  loading.value = true;
  try {
    list.value = await listDataSources();
  } catch (err: any) {
    ElMessage.error(err.message || "获取数据源失败");
  } finally {
    loading.value = false;
  }
};

onMounted(fetchList);

const reset = () => {
  editingId.value = null;
  form.name = "";
  form.source_type = "url";
  form.config = {};
  form.biz_category = "";
  form.schedule_cron = "";
  form.enable_schedule = false;
  urlInput.value = "";
  apiUrlInput.value = "";
  apiMode.value = "http";
  firecrawlQuery.value = "";
  firecrawlLimit.value = null;
  firecrawlTbs.value = "";
  firecrawlSources.value = ["web"];
  aliyunQuery.value = "";
  aliyunEngineType.value = "Generic";
  aliyunTimeRange.value = "NoLimit";
  aliyunCategory.value = "";
  n8nWebhook.value = "";
  docOssUrl.value = "";
  fileList.value = [];
  advancedConfig.value = {};
};

const getSourceTypeTag = (type: string) => {
  const map: Record<string, string> = {
    url: "primary",
    api: "warning",
    n8n: "danger",
    document: "success"
  };
  return map[type] || "info";
};

const buildConfig = (): Record<string, unknown> | null => {
  if (!form.name) {
    ElMessage.warning("请填写名称");
    return null;
  }
  const cfg: Record<string, unknown> = {};
  if (form.source_type === "url") {
    const urls = urlInput.value
      .split(/[\n,]/) // 支持换行或逗号
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      ElMessage.warning("请填写至少一个 URL");
      return null;
    }
    if (urls.length) {
      cfg.urls = urls;
    }
  } else if (form.source_type === "api") {
    cfg.api_mode = apiMode.value || "http";
    if (apiMode.value === "http") {
      if (!apiUrlInput.value.trim()) {
        ElMessage.warning("请填写 API 地址");
        return null;
      }
      cfg.api_url = apiUrlInput.value.trim();
    } else if (apiMode.value === "firecrawl_search") {
      if (!firecrawlQuery.value.trim()) {
        ElMessage.warning("请填写搜索 query");
        return null;
      }
      cfg.query = firecrawlQuery.value.trim();
      if (typeof firecrawlLimit.value === "number" && !Number.isNaN(firecrawlLimit.value)) {
        cfg.limit = firecrawlLimit.value;
      }
      if (firecrawlTbs.value) cfg.tbs = firecrawlTbs.value;
      if (Array.isArray(firecrawlSources.value) && firecrawlSources.value.length) {
        cfg.sources = firecrawlSources.value;
      }
      cfg.scrape_formats = ["html"];
    } else if (apiMode.value === "aliyun_unified_search") {
      if (!aliyunQuery.value.trim()) {
        ElMessage.warning("请填写搜索 query");
        return null;
      }
      cfg.query = aliyunQuery.value.trim();
      cfg.engine_type = aliyunEngineType.value || "Generic";
      cfg.time_range = aliyunTimeRange.value || "NoLimit";
      if (aliyunCategory.value) cfg.category = aliyunCategory.value;
      cfg.include_main_text = true;
    }
  } else if (form.source_type === "n8n") {
    if (!n8nWebhook.value.trim()) {
      ElMessage.warning("请填写 n8n Webhook 地址");
      return null;
    }
    cfg.webhook = n8nWebhook.value.trim();
  } else if (form.source_type === "document") {
    if (!docOssUrl.value.trim()) {
      ElMessage.warning("请填写 OSS 文档 URL");
      return null;
    }
    cfg.doc_url = docOssUrl.value.trim();
  }

  if (shouldShowAdvancedConfig.value && advancedConfig.value && typeof advancedConfig.value === "object") {
    // 中文说明：过滤内部字段，避免把运行态信息写回配置
    Object.keys(advancedConfig.value as any).forEach((k) => {
      if (k.startsWith("_")) return;
      (cfg as any)[k] = (advancedConfig.value as any)[k];
    });
  }
  form.config = cfg;
  return cfg;
};

const save = async () => {
  const cfg = buildConfig();
  if (!cfg) return;
  loading.value = true;
  try {
    const payload = {
      name: form.name,
      source_type: form.source_type,
      config: form.config,
      biz_category: form.biz_category || null,
      schedule_cron: form.schedule_cron || null,
      enable_schedule: form.enable_schedule,
    };
    if (editingId.value) {
      await updateDataSource(editingId.value, payload);
      ElMessage.success("更新成功");
    } else {
      await createDataSource(payload);
      ElMessage.success("创建成功");
    }
    await fetchList();
    dialogVisible.value = false;
  } catch (err: any) {
    ElMessage.error(err.message || "保存失败");
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  reset();
  dialogVisible.value = true;
};

const extractExtraConfig = (cfg: Record<string, unknown> | null) => {
  if (!cfg) return {};
  const extra = { ...cfg };
  delete extra.urls;
  delete extra.api_url;
  delete extra.webhook;
  delete extra.doc_url;
  delete (extra as any).api_mode;
  // 中文说明：API 搜索模式字段不属于 AdvancedConfig（否则会被 AdvancedConfig 覆盖导致丢失）
  delete (extra as any).query;
  delete (extra as any).limit;
  delete (extra as any).tbs;
  delete (extra as any).sources;
  delete (extra as any).scrape_formats;
  delete (extra as any).engine_type;
  delete (extra as any).time_range;
  delete (extra as any).category;
  delete (extra as any).location;
  delete (extra as any).include_main_text;
  delete (extra as any).advanced_params;
  // 中文说明：过滤内部字段，避免把运行态信息写回配置
  Object.keys(extra).forEach((k) => {
    if (k.startsWith("_")) delete (extra as any)[k];
  });
  return extra;
};

const onEdit = (row: DataSource) => {
  reset();
  editingId.value = row.id;
  form.name = row.name;
  form.source_type = row.source_type;
  form.biz_category = row.biz_category || "";
  form.schedule_cron = row.schedule_cron || "";
  form.enable_schedule = row.enable_schedule;
  
  const cfg = (row.config as Record<string, unknown>) || null;
  if (row.source_type === "url" && cfg && Array.isArray(cfg.urls)) {
    urlInput.value = (cfg.urls as string[]).join("\n");
  } else if (row.source_type === "api" && cfg && typeof cfg.api_url === "string") {
    apiUrlInput.value = String(cfg.api_url);
    apiMode.value = String((cfg as any).api_mode || "http");
  } else if (row.source_type === "n8n" && cfg && typeof cfg.webhook === "string") {
    n8nWebhook.value = String(cfg.webhook);
  } else if (row.source_type === "document" && cfg && typeof cfg.doc_url === "string") {
    docOssUrl.value = String(cfg.doc_url);
    fileList.value = [{ name: docOssUrl.value } as UploadUserFile];
  }

  if (row.source_type === "api" && cfg) {
    apiMode.value = String((cfg as any).api_mode || "http");
    if (apiMode.value === "firecrawl_search") {
      firecrawlQuery.value = String((cfg as any).query || "");
      const lim = (cfg as any).limit;
      const parsed = typeof lim === "number" && !Number.isNaN(lim) ? lim : Number(lim);
      firecrawlLimit.value = parsed && parsed > 0 ? parsed : null;
      firecrawlTbs.value = String((cfg as any).tbs || "");
      firecrawlSources.value = Array.isArray((cfg as any).sources) && (cfg as any).sources.length ? (cfg as any).sources : ["web"];
    }
    if (apiMode.value === "aliyun_unified_search") {
      aliyunQuery.value = String((cfg as any).query || "");
      aliyunEngineType.value = String((cfg as any).engine_type || "Generic");
      aliyunTimeRange.value = String((cfg as any).time_range || "NoLimit");
      aliyunCategory.value = String((cfg as any).category || "");
    }
  }
  
  // 中文说明：API 搜索模式不需要高级配置；仅自定义 HTTP 需要。
  if (row.source_type === "api") {
    const mode = String((cfg as any)?.api_mode || "http");
    advancedConfig.value = mode === "http" ? extractExtraConfig(cfg) : {};
  } else {
    advancedConfig.value = extractExtraConfig(cfg);
  }
  dialogVisible.value = true;
};

const onDelete = async (row: DataSource) => {
  try {
    await ElMessageBox.confirm(`确定删除数据源「${row.name}」吗？`, "提示", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteDataSource(row.id);
    ElMessage.success("删除成功");
    await fetchList();
  } catch (err) {
    if (err !== "cancel") ElMessage.error("删除失败");
  }
};

const onTrigger = async (id: number) => {
  if (triggerLoading[id]) return;
  triggerLoading[id] = true;
  try {
    const ds = await triggerDataSource(id);
    const report = (ds?.config && typeof ds.config === "object") ? (ds.config as any)._last_trigger : null;
    const stats = report?.stats || null;
    const ingested = typeof report?.ingested === "number" ? report.ingested : null;
    const dedup = typeof stats?.dedup_skipped === "number" ? stats.dedup_skipped : 0;

    if (ingested === 0 && dedup > 0) {
      try {
        await ElMessageBox.confirm(
          `本次无新增内容（去重跳过 ${dedup} 条）。是否强制重抓（force=true）？`,
          "提示",
          {
            confirmButtonText: "强制重抓",
            cancelButtonText: "取消",
            type: "warning",
          }
        );
        await triggerDataSource(id, true);
        ElMessage.success("已强制重抓");
      } catch {
        ElMessage.info("已触发（无新增，已去重跳过）");
      }
    } else {
      ElMessage.success("已触发采集");
    }
    await fetchList();
  } catch (err: any) {
    ElMessage.error(err.message || "触发失败");
  } finally {
    triggerLoading[id] = false;
  }
};

const onSelectFile = (file: UploadFile, files: UploadFile[]) => {
  fileList.value = files as UploadUserFile[];
  if (!docOssUrl.value) {
    docOssUrl.value = file.name || "";
  }
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
  align-items: center;
  margin-bottom: 8px;
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

.name-text {
  font-weight: 500;
  color: #303133;
}

.text-gray {
  color: #909399;
}

.schedule-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.cron-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  color: #606266;
  width: fit-content;
}

.time-info {
  display: flex;
  flex-direction: column;
  color: #909399;
  font-size: 11px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.config-area {
  background: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  border: 1px dashed #e2e8f0;
  margin-bottom: 20px;
}

.upload-tip {
  font-size: 12px;
  color: #e6a23c;
  margin-top: 4px;
}

.schedule-config {
  background: #f0f9eb;
  padding: 16px;
  border-radius: 8px;
  margin-top: 20px;
}

.cron-item {
  margin-bottom: 0 !important;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
