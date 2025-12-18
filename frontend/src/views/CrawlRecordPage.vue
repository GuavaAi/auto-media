<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">内容抓取记录</h2>
        <p class="page-desc">
          查看所有数据源的抓取历史。支持按数据源筛选，点击记录可查看原始内容详情。
        </p>
      </div>
      <div class="header-actions">
        <el-button type="primary" plain @click="openQuickFetch">
          快捷抓取
        </el-button>
        <el-button :loading="loading" @click="fetchList">
          <el-icon class="el-icon--left"><Refresh /></el-icon>
          刷新列表
        </el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="left-panel">
            <el-select
              v-model="filters.datasource_id"
              clearable
              filterable
              placeholder="全部数据源"
              style="width: 240px"
              @change="onFilterChange"
            >
              <template #prefix>
                <el-icon><Filter /></el-icon>
              </template>
              <el-option
                v-for="ds in datasources"
                :key="ds.id"
                :label="ds.name"
                :value="ds.id"
              >
                <span style="float: left">{{ ds.name }}</span>
                <span style="float: right; color: #8492a6; font-size: 13px">#{{ ds.id }}</span>
              </el-option>
            </el-select>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="~"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 320px"
              @change="onFilterChange"
            />
          </div>
          <div class="right-panel">
            <span class="total-text">共 {{ total }} 条记录</span>
          </div>
        </div>
      </template>

      <el-table :data="items" stripe size="default" class="data-table" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" align="center" />
        
        <el-table-column prop="datasource_name" label="数据源" min-width="140">
          <template #default="{ row }">
            <div class="ds-info">
              <span class="ds-name">{{ row.datasource_name || `ID:${row.datasource_id}` }}</span>
              <el-tag size="small" type="info" effect="light" class="ds-type">{{ row.source_type }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="来源标题 / URL" min-width="240">
          <template #default="{ row }">
             <div class="source-title" :title="row.title || ''">{{ row.title || '-' }}</div>
             <a v-if="isUrl(row.url)" :href="row.url || ''" target="_blank" class="source-link">
               {{ row.url }}
               <el-icon><TopRight /></el-icon>
             </a>
          </template>
        </el-table-column>

        <el-table-column prop="content_preview" label="内容预览" min-width="300">
          <template #default="{ row }">
            <div class="content-preview">{{ row.content_preview || "无预览内容" }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="fetched_at" label="抓取时间" width="180" align="center">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.fetched_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="goDetail(row.id)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          background
          layout="total, prev, pager, next, jumper"
          :page-size="page.limit"
          :current-page="currentPage"
          :total="total"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="quickFetchVisible" title="快捷抓取（一次性）" width="640px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="URL" required>
          <el-input v-model="quickFetchForm.url" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="CSS Selector（可选：元素选择抽取）">
          <div style="display: flex; gap: 10px; width: 100%">
            <el-input v-model="quickFetchForm.css_selector" placeholder="例如：article 或 #content" />
            <el-button @click="openElementPicker" :disabled="!(quickFetchForm.url || '').trim()">选择元素</el-button>
          </div>
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="抓取引擎">
              <el-select v-model="quickFetchForm.crawler_engine" style="width: 100%">
                <el-option label="playwright" value="playwright" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="超时（秒）">
              <el-input-number v-model="quickFetchForm.timeout" :min="5" :max="180" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="quickFetchVisible = false">取消</el-button>
        <el-button :loading="quickFetchPreviewLoading" @click="onQuickFetchPreview">预览</el-button>
        <el-button type="primary" :loading="quickFetchLoading" @click="onQuickFetch">开始抓取</el-button>
      </template>

      <el-alert
        v-if="quickFetchPreviewText"
        title="预览（抽取+清洗后的文本片段）"
        type="info"
        :closable="false"
        show-icon
        style="margin-top: 12px"
      />
      <el-input
        v-if="quickFetchPreviewText"
        v-model="quickFetchPreviewText"
        type="textarea"
        :rows="8"
        readonly
        style="margin-top: 8px"
      />
    </el-dialog>

    <ElementPicker
      v-model:visible="elementPickerVisible"
      :url="(quickFetchForm.url || '').trim()"
      :engine="quickFetchForm.crawler_engine"
      @picked="onPickedSelector"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, Filter, TopRight } from "@element-plus/icons-vue";
import { listCrawlRecords, quickFetchCrawlRecord, quickFetchCrawlRecordPreview } from "@/api/crawlRecords";
import { listDataSources } from "@/api/datasources";
import type { CrawlRecord, DataSource } from "@/types";
import { formatDate } from "@/utils/date";
import ElementPicker from "@/components/ElementPicker.vue";

const router = useRouter();

const loading = ref(false);
const items = ref<CrawlRecord[]>([]);
const total = ref(0);

const quickFetchVisible = ref(false);
const quickFetchLoading = ref(false);
const quickFetchPreviewLoading = ref(false);
const quickFetchPreviewText = ref("");
const elementPickerVisible = ref(false);
const quickFetchForm = reactive<{ url: string; crawler_engine: string; timeout: number; css_selector: string }>({
  url: "",
  crawler_engine: "playwright",
  timeout: 30,
  css_selector: "",
});

const datasources = ref<DataSource[]>([]);

const filters = reactive<{ datasource_id?: number | null }>({
  datasource_id: null,
});
const dateRange = ref<[string, string] | null>(null);

const page = reactive({
  limit: 10,
  offset: 0,
});

const currentPage = computed(() => Math.floor(page.offset / page.limit) + 1);

const fetchDataSources = async () => {
  try {
    datasources.value = await listDataSources();
  } catch {
    datasources.value = [];
  }
};

const openElementPicker = () => {
  const url = (quickFetchForm.url || "").trim();
  if (!url) {
    ElMessage.warning("请先填写 URL");
    return;
  }
  elementPickerVisible.value = true;
};

const onPickedSelector = async (sel: string) => {
  quickFetchForm.css_selector = (sel || "").trim();
  if (quickFetchForm.css_selector) {
    await onQuickFetchPreview();
  }
};

const openQuickFetch = () => {
  quickFetchForm.url = "";
  quickFetchForm.crawler_engine = "playwright";
  quickFetchForm.timeout = 30;
  quickFetchForm.css_selector = "";
  quickFetchPreviewText.value = "";
  quickFetchVisible.value = true;
};

const onQuickFetchPreview = async () => {
  const url = (quickFetchForm.url || "").trim();
  if (!url) {
    ElMessage.warning("请先填写 URL");
    return;
  }
  quickFetchPreviewLoading.value = true;
  try {
    const resp: any = await quickFetchCrawlRecordPreview({
      url,
      crawler_engine: quickFetchForm.crawler_engine,
      timeout: quickFetchForm.timeout,
      css_selector: quickFetchForm.css_selector || undefined,
    });
    quickFetchPreviewText.value = resp?.text_preview || "";
    if (!quickFetchPreviewText.value) {
      ElMessage.warning("未获取到预览内容，可尝试更换引擎或填写 CSS Selector");
    }
  } catch (err: any) {
    ElMessage.error(err.message || "预览失败");
  } finally {
    quickFetchPreviewLoading.value = false;
  }
};

const onQuickFetch = async () => {
  const url = (quickFetchForm.url || "").trim();
  if (!url) {
    ElMessage.warning("请填写 URL");
    return;
  }
  quickFetchLoading.value = true;
  try {
    const resp: any = await quickFetchCrawlRecord({
      url,
      crawler_engine: quickFetchForm.crawler_engine,
      timeout: quickFetchForm.timeout,
      css_selector: quickFetchForm.css_selector || undefined,
    });
    ElMessage.success(`抓取成功：已生成记录 #${resp.id}`);
    quickFetchVisible.value = false;
    await fetchList();
    // 便捷跳转：抓取成功后自动打开详情
    if (resp?.id) {
      router.push(`/crawl-records/${resp.id}`);
    }
  } catch (err: any) {
    ElMessage.error(err.message || "快捷抓取失败");
  } finally {
    quickFetchLoading.value = false;
  }
};

const fetchList = async () => {
  loading.value = true;
  try {
    const resp = await listCrawlRecords({
      datasource_id: filters.datasource_id || undefined,
      start_date: dateRange.value?.[0] || undefined,
      end_date: dateRange.value?.[1] || undefined,
      limit: page.limit,
      offset: page.offset,
    });
    items.value = resp.items;
    total.value = resp.total;
  } catch (err: any) {
    ElMessage.error(err.message || "获取抓取记录失败");
  } finally {
    loading.value = false;
  }
};

const onPageChange = async (p: number) => {
  page.offset = (p - 1) * page.limit;
  await fetchList();
};

const onFilterChange = async () => {
  page.offset = 0;
  await fetchList();
};

const goDetail = (id: number) => router.push(`/crawl-records/${id}`);

const isUrl = (s?: string | null) => !!s && (s.startsWith("http://") || s.startsWith("https://"));

onMounted(async () => {
  await fetchDataSources();
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
  gap: 12px;
}

.ds-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ds-name {
  font-weight: 500;
  color: #303133;
}

.ds-type {
  width: fit-content;
}

.source-title {
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link {
  font-size: 12px;
  color: #409eff;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  text-decoration: none;
}

.source-link:hover {
  text-decoration: underline;
}

.content-preview {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.time-text {
  color: #909399;
  font-size: 13px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.total-text {
  font-size: 13px;
  color: #909399;
}
</style>
