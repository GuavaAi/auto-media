<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">软文管理</h2>
        <p class="page-desc">查看已生成的软文列表，支持快速检索与查看详情。</p>
      </div>
      <div class="header-actions">
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
            <el-input
              v-model="filters.keyword"
              clearable
              placeholder="按标题关键词搜索"
              style="width: 320px"
              @keyup.enter="onFilterChange"
              @clear="onFilterChange"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="right-panel">
            <span class="total-text">共 {{ filteredItems.length }} 篇</span>
          </div>
        </div>
      </template>

      <el-table :data="pagedItems" stripe size="default" class="data-table" v-loading="loading">
        <el-table-column prop="id" label="ID" width="90" align="center" />

        <el-table-column prop="title" label="标题" min-width="260">
          <template #default="{ row }">
            <div class="title-cell" :title="row.title">{{ row.title }}</div>
            <div class="subline">
              <el-tag v-if="row.material_pack_id" size="small" type="success" effect="light">
                素材包 #{{ row.material_pack_id }}
              </el-tag>
              <el-tag v-if="row.material_refs?.item_ids?.length" size="small" type="info" effect="light">
                引用素材 {{ row.material_refs.item_ids.length }} 条
              </el-tag>
              <el-tag v-if="row.source_refs?.length" size="small" type="warning" effect="light">
                引用数据源 {{ row.source_refs.length }} 个
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="summary" label="摘要" min-width="260">
          <template #default="{ row }">
            <div class="summary-cell" :title="row.summary || ''">{{ row.summary || "-" }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="生成时间" width="180" align="center">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="goDetail(row.id)">查看</el-button>
            <el-button type="success" link @click="goEdit(row.id)">编辑</el-button>
            <el-button type="danger" link @click="onDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20, 50]"
          :page-size="pageSize"
          :current-page="currentPage"
          :total="filteredItems.length"
          @size-change="onPageSizeChange"
          @current-change="onPageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh, Search } from "@element-plus/icons-vue";
import { deleteArticle, listArticles } from "@/api/articles";
import type { Article } from "@/types";
import { formatDate } from "@/utils/date";

const router = useRouter();

const loading = ref(false);
const items = ref<Article[]>([]);

const filters = reactive({
  keyword: "",
});

const currentPage = ref(1);
const pageSize = ref(10);

const filteredItems = computed(() => {
  const kw = (filters.keyword || "").trim().toLowerCase();
  if (!kw) return items.value;
  return items.value.filter((it) => (it.title || "").toLowerCase().includes(kw));
});

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredItems.value.slice(start, start + pageSize.value);
});

const fetchList = async () => {
  loading.value = true;
  try {
    items.value = await listArticles();
  } catch (err: any) {
    ElMessage.error(err.message || "获取文章列表失败");
  } finally {
    loading.value = false;
  }
};

const onFilterChange = () => {
  currentPage.value = 1;
};

const onPageChange = (p: number) => {
  currentPage.value = p;
};

const onPageSizeChange = (s: number) => {
  pageSize.value = s;
  currentPage.value = 1;
};

const goDetail = (id: number) => {
  router.push(`/articles/${id}`);
};

const goEdit = (id: number) => {
  router.push(`/articles/${id}/edit`);
};

const onDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确认删除该文章？删除后不可恢复。", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }

  try {
    const resp = await deleteArticle(id);
    if (!resp?.ok) {
      ElMessage.error("删除失败");
      return;
    }
    ElMessage.success("已删除");
    await fetchList();
  } catch (err: any) {
    ElMessage.error(err.message || "删除失败");
  }
};

onMounted(fetchList);
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

.header-content {
  flex: 1;
  min-width: 0;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}

.page-desc {
  margin: 6px 0 0 0;
  color: #6b7280;
  font-size: 13px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.total-text {
  color: #6b7280;
  font-size: 13px;
}

.title-cell {
  font-weight: 600;
  padding-top: 16px;
}

.summary-cell {
  color: #374151;
  line-height: 1.4;
  max-width: 100%;
  white-space: normal;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
}

.time-text {
  color: #6b7280;
}
</style>
