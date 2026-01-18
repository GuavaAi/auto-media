<template>
  <div class="page-container">
    <div class="header">
      <div class="left">
        <h2 class="title">素材包</h2>
        <div class="desc">管理可复用的要点/引用/事实/来源素材，用于软文生成时注入 Prompt。</div>
      </div>
      <div class="actions">
        <el-input
          v-model="keyword"
          placeholder="搜索名称/描述"
          clearable
          style="width: 260px"
          @keyup.enter="fetchList"
        />
        <el-button @click="openBasket">素材篮 ({{ basket.count }})</el-button>
        <el-button @click="openUnifiedSearch">统一搜索</el-button>
        <el-button @click="fetchList" :loading="loading">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建素材包</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="packs" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="#" width="80" />
        <el-table-column prop="name" label="名称" min-width="220" />
        <el-table-column label="描述" min-width="260">
          <template #default="{ row }">
            <el-tooltip placement="top" effect="dark" :show-after="300">
              <template #content>
                <div class="pack-desc-tooltip">{{ row.description || '（无）' }}</div>
              </template>
              <div class="pack-desc-clamp">{{ row.description || '（无）' }}</div>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.id)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="limit"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </el-card>
    <el-dialog v-model="createVisible" title="新建素材包" width="520px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="例如：AI 写作素材包" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <MaterialBasketDrawer v-model="basketVisible" @written="onBasketWritten" @created="onBasketCreated" />

    <el-dialog v-model="unifiedSearchVisible" title="统一搜索入库" width="720px">
      <UnifiedSearchForm
        v-model="unifiedSearchForm"
        mode="full"
        :loading="unifiedSearchLoading"
        submit-text="一键入库 + 加入素材篮"
        @submit="onUnifiedSearch"
      />
      <template #footer>
        <el-button @click="unifiedSearchVisible = false">取消</el-button>
        <el-button type="primary" :loading="unifiedSearchLoading" @click="onUnifiedSearch">
          一键入库 + 加入素材篮
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import type { MaterialPack, MaterialPackCreate } from "@/types";
import {
  createMaterialPack,
  deleteMaterialPack,
  aliyunUnifiedSearchIngest,
  firecrawlSearchIngest,
  serpapiSearchIngest,
  listMaterialPacks,
} from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";
import MaterialBasketDrawer from "@/components/MaterialBasketDrawer.vue";
import UnifiedSearchForm, { type UnifiedSearchFormValue } from "@/components/UnifiedSearchForm.vue";

const route = useRoute();
const router = useRouter();

const basket = useMaterialBasketStore();

const loading = ref(false);
const keyword = ref("");

const page = ref(1);
const limit = ref(20);
const total = ref(0);
const offset = computed(() => (page.value - 1) * limit.value);

const packs = ref<MaterialPack[]>([]);

const fetchList = async () => {
  loading.value = true;
  try {
    const resp = await listMaterialPacks({
      keyword: keyword.value || undefined,
      limit: limit.value,
      offset: offset.value,
    });
    packs.value = resp.items || [];
    total.value = resp.total || 0;
  } catch (err: any) {
    ElMessage.error(err.message || "加载素材包失败");
  } finally {
    loading.value = false;
  }
};

const unifiedSearchVisible = ref(false);
const unifiedSearchLoading = ref(false);
const unifiedSearchForm = reactive<UnifiedSearchFormValue>({
  engine: "aliyun",
  query: "",
  limit: 10,
  tbs: "",
  sources: ["web"],
  engineType: "Generic",
  timeRange: "NoLimit",
  category: "",
  serpapiEngine: "google",
});

const openUnifiedSearch = (engine?: UnifiedSearchFormValue["engine"]) => {
  if (engine) {
    unifiedSearchForm.engine = engine;
  }
  unifiedSearchVisible.value = true;
};

const onUnifiedSearch = async () => {
  const query = unifiedSearchForm.query.trim();
  if (!query) {
    ElMessage.warning("请填写搜索 query");
    return;
  }
  unifiedSearchLoading.value = true;
  try {
    // 中文说明：统一入口根据引擎切换不同入库 API。
    if (unifiedSearchForm.engine === "firecrawl") {
      const resp = await firecrawlSearchIngest({
        query,
        limit: unifiedSearchForm.limit || 10,
        tbs: unifiedSearchForm.tbs || undefined,
        sources: unifiedSearchForm.sources || undefined,
      });
      basket.addMany(resp.items || []);
      ElMessage.success(`已入库 ${resp.ingested} 条，加入素材篮 ${resp.items?.length || 0} 条（素材篮共 ${basket.count} 条）`);
    } else if (unifiedSearchForm.engine === "aliyun") {
      const resp = await aliyunUnifiedSearchIngest({
        query,
        engine_type: unifiedSearchForm.engineType || "Generic",
        time_range: unifiedSearchForm.timeRange || "NoLimit",
        category: unifiedSearchForm.category || undefined,
        include_main_text: true,
      });
      basket.addMany(resp.items || []);
      ElMessage.success(`已入库 ${resp.ingested} 条，加入素材篮 ${resp.items?.length || 0} 条（素材篮共 ${basket.count} 条）`);
    } else {
      const resp = await serpapiSearchIngest({
        query,
        limit: unifiedSearchForm.limit || 10,
        engine: unifiedSearchForm.serpapiEngine || "google",
      });
      basket.addMany(resp.items || []);
      ElMessage.success(`已入库 ${resp.ingested} 条，加入素材篮 ${resp.items?.length || 0} 条（素材篮共 ${basket.count} 条）`);
    }
    basketVisible.value = true;
    unifiedSearchVisible.value = false;
  } catch (err: any) {
    const fallback = unifiedSearchForm.engine === "firecrawl"
      ? "Firecrawl 搜索入库失败"
      : unifiedSearchForm.engine === "aliyun"
        ? "阿里统一搜索入库失败"
        : "SerpAPI 搜索入库失败";
    ElMessage.error(err.message || fallback);
  } finally {
    unifiedSearchLoading.value = false;
  }
};

const onPageChange = async (p: number) => {
  page.value = p;
  await fetchList();
};

const goDetail = (id: number) => {
  router.push(`/materials/packs/${id}`);
};

const onDelete = async (row: MaterialPack) => {
  try {
    await ElMessageBox.confirm(
      `确定删除素材包「${row.name}」吗？\n\n注意：该素材包下的所有素材条目将一并删除，且不可恢复。`,
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

  try {
    await deleteMaterialPack(row.id);
    ElMessage.success("删除成功");
    await fetchList();
  } catch (err: any) {
    ElMessage.error(err.message || "删除失败");
  }
};

const createVisible = ref(false);
const createLoading = ref(false);
const createForm = reactive<MaterialPackCreate>({
  name: "",
  description: "",
});

const openCreate = () => {
  createForm.name = "";
  createForm.description = "";
  createVisible.value = true;
};

const basketVisible = ref(false);
const openBasket = () => {
  basketVisible.value = true;
};

const onBasketWritten = async (packId: number) => {
  await fetchList();
  goDetail(packId);
};

const onBasketCreated = async (packId: number) => {
  await fetchList();
  goDetail(packId);
};


const onCreate = async () => {
  if (!createForm.name.trim()) {
    ElMessage.warning("请填写素材包名称");
    return;
  }
  createLoading.value = true;
  try {
    const pack = await createMaterialPack({
      name: createForm.name.trim(),
      description: createForm.description || undefined,
    });
    ElMessage.success("创建成功");
    createVisible.value = false;
    await fetchList();
    goDetail(pack.id);
  } catch (err: any) {
    ElMessage.error(err.message || "创建失败");
  } finally {
    createLoading.value = false;
  }
};

onMounted(() => {
  fetchList();
});

watch(
  () => route.query.tool,
  (v) => {
    if (!v) return;
    const tool = String(v || "").toLowerCase();
    if (tool === "aliyun") {
      openUnifiedSearch("aliyun");
    } else if (tool === "firecrawl") {
      openUnifiedSearch("firecrawl");
    } else if (tool === "serpapi") {
      openUnifiedSearch("serpapi");
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.desc {
  color: #6b7280;
  font-size: 13px;
  margin-top: 6px;
}

.actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.basket-text-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.35;
}

.basket-text-tooltip {
  max-width: 420px;
  white-space: pre-wrap;
  word-break: break-word;
}

.pack-desc-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.35;
}

.pack-desc-tooltip {
  max-width: 420px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
