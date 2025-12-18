<template>
  <div class="page-container">
    <div class="header">
      <div class="left">
        <el-button link @click="goBack" class="back-btn">
          <el-icon class="mr-4"><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <div class="title-row">
          <h2 class="title">{{ pack?.name || "素材包" }}</h2>
          <el-tag v-if="pack" type="info" size="small">#{{ pack.id }}</el-tag>
        </div>
        <el-tooltip placement="top" effect="dark" :show-after="300">
          <template #content>
            <div class="pack-desc-tooltip">{{ pack?.description || "（无描述）" }}</div>
          </template>
          <div class="desc pack-desc-clamp">{{ pack?.description || "（无描述）" }}</div>
        </el-tooltip>
      </div>
      <div class="actions">
        <el-input
          v-model="keyword"
          placeholder="在当前素材包内搜索"
          clearable
          style="width: 260px"
          @keyup.enter="onSearch"
        />
        <el-select v-model="typeFilter" placeholder="类型" clearable style="width: 140px">
          <el-option label="要点" value="bullet" />
          <el-option label="引用" value="quote" />
          <el-option label="事实" value="fact" />
          <el-option label="来源" value="source" />
          <el-option label="笔记" value="note" />
        </el-select>
        <el-button @click="refresh" :loading="loading">刷新</el-button>
        <el-button @click="openBatchAdd" type="primary">追加素材</el-button>
        <el-button @click="onDedupe" :loading="dedupeLoading">去重</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="#" width="80" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.item_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="320">
          <template #default="{ row }">
            <el-tooltip placement="top" effect="dark" :show-after="300">
              <template #content>
                <div class="item-text-tooltip">{{ row.text }}</div>
              </template>
              <div class="item-text-clamp">{{ row.text }}</div>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="220">
          <template #default="{ row }">
            <a v-if="row.source_url" :href="row.source_url" target="_blank">{{ row.source_url }}</a>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="batchAddVisible" title="批量追加素材" width="640px">
      <el-form :model="batchAddForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="条目类型" required>
              <el-select v-model="batchAddForm.item_type" style="width: 100%">
                <el-option label="要点" value="bullet" />
                <el-option label="引用" value="quote" />
                <el-option label="事实" value="fact" />
                <el-option label="来源" value="source" />
                <el-option label="笔记" value="note" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="统一来源链接（可选，批量套用）">
              <el-input v-model="batchAddForm.source_url" placeholder="https://..." />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="内容（每行一条）" required>
          <el-input
            v-model="batchAddForm.lines"
            type="textarea"
            :rows="8"
            placeholder="例如：
要点1
要点2"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchAddVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchAddLoading" @click="onBatchAdd">追加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑素材条目" width="560px">
      <el-form :model="editForm" label-position="top">
        <el-form-item label="类型" required>
          <el-select v-model="editForm.item_type" style="width: 100%">
            <el-option label="要点" value="bullet" />
            <el-option label="引用" value="quote" />
            <el-option label="事实" value="fact" />
            <el-option label="来源" value="source" />
            <el-option label="笔记" value="note" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="editForm.text" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="来源链接">
          <el-input v-model="editForm.source_url" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="onEditSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";
import type { MaterialItem, MaterialItemUpdate, MaterialPack } from "@/types";
import {
  batchCreateMaterialItems,
  deleteMaterialItem,
  dedupeMaterialPack,
  getMaterialPackDetail,
  searchMaterialItems,
  updateMaterialItem,
} from "@/api/materials";

const route = useRoute();
const router = useRouter();

const packId = computed(() => Number(route.params.id));

const loading = ref(false);
const pack = ref<MaterialPack | null>(null);
const items = ref<MaterialItem[]>([]);

const keyword = ref("");
const typeFilter = ref<string | undefined>(undefined);

const refresh = async () => {
  loading.value = true;
  try {
    const resp = await getMaterialPackDetail(packId.value);
    pack.value = resp.pack;
    items.value = resp.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "加载素材包失败");
  } finally {
    loading.value = false;
  }
};

const onSearch = async () => {
  loading.value = true;
  try {
    const resp = await searchMaterialItems({
      keyword: keyword.value || undefined,
      pack_id: packId.value,
      item_type: typeFilter.value || undefined,
      limit: 200,
      offset: 0,
    });
    items.value = resp.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "搜索失败");
  } finally {
    loading.value = false;
  }
};

const goBack = () => router.push("/materials/packs");

const dedupeLoading = ref(false);
const onDedupe = async () => {
  dedupeLoading.value = true;
  try {
    const resp = await dedupeMaterialPack(packId.value);
    ElMessage.success(`已去重：移除 ${resp.removed} 条重复素材`);
    await refresh();
  } catch (err: any) {
    ElMessage.error(err.message || "去重失败");
  } finally {
    dedupeLoading.value = false;
  }
};

// 批量追加
const batchAddVisible = ref(false);
const batchAddLoading = ref(false);
const batchAddForm = reactive({
  item_type: "bullet",
  source_url: "",
  lines: "",
});

const openBatchAdd = () => {
  batchAddForm.item_type = "bullet";
  batchAddForm.source_url = "";
  batchAddForm.lines = "";
  batchAddVisible.value = true;
};

const onBatchAdd = async () => {
  const lines = (batchAddForm.lines || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    ElMessage.warning("请填写内容（每行一条）");
    return;
  }

  batchAddLoading.value = true;
  try {
    await batchCreateMaterialItems(packId.value, {
      items: lines.map((t) => ({
        item_type: batchAddForm.item_type,
        text: t,
        source_url: batchAddForm.source_url || undefined,
      })),
    });
    ElMessage.success("追加成功");
    batchAddVisible.value = false;
    await refresh();
  } catch (err: any) {
    ElMessage.error(err.message || "追加失败");
  } finally {
    batchAddLoading.value = false;
  }
};

// 编辑
const editVisible = ref(false);
const editLoading = ref(false);
const editingId = ref<number | null>(null);
const editForm = reactive<MaterialItemUpdate>({
  item_type: "bullet",
  text: "",
  source_url: "",
});

const openEdit = (row: MaterialItem) => {
  editingId.value = row.id;
  editForm.item_type = row.item_type;
  editForm.text = row.text;
  editForm.source_url = row.source_url || "";
  editVisible.value = true;
};

const onEditSave = async () => {
  if (!editingId.value) return;
  if (!editForm.text || !editForm.text.trim()) {
    ElMessage.warning("内容不能为空");
    return;
  }
  editLoading.value = true;
  try {
    await updateMaterialItem(editingId.value, {
      item_type: editForm.item_type,
      text: editForm.text.trim(),
      source_url: editForm.source_url || undefined,
    });
    ElMessage.success("保存成功");
    editVisible.value = false;
    await refresh();
  } catch (err: any) {
    ElMessage.error(err.message || "保存失败");
  } finally {
    editLoading.value = false;
  }
};

const onDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确认删除该素材条目？", "提示", { type: "warning" });
    await deleteMaterialItem(id);
    ElMessage.success("已删除");
    await refresh();
  } catch (err: any) {
    if (err?.message) {
      // 用户取消会抛出错误对象，这里不提示
    }
  }
};

onMounted(async () => {
  await refresh();
});
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.left {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.back-btn {
  padding: 0 8px 0 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.desc {
  color: #6b7280;
  font-size: 13px;
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
  max-width: 520px;
  white-space: pre-wrap;
  word-break: break-word;
}

.item-text-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.35;
}

.item-text-tooltip {
  max-width: 520px;
  white-space: pre-wrap;
  word-break: break-word;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
