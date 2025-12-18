<template>
  <el-drawer v-model="visible" :title="drawerTitle" size="660px">
    <div class="basket-actions">
      <el-button :disabled="basket.count === 0" @click="openExportToPack">写入到已有素材包</el-button>
      <el-button type="primary" :disabled="basket.count === 0" @click="openCreateFromBasket">
        从素材篮创建素材包
      </el-button>
      <el-button :disabled="basket.count === 0" @click="basket.clear()">清空</el-button>
    </div>

    <el-table :data="basket.items" style="width: 100%" max-height="620">
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.item_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="内容" min-width="320">
        <template #default="{ row }">
          <el-tooltip placement="top" effect="dark" :show-after="300">
            <template #content>
              <div class="basket-text-tooltip">{{ row.text }}</div>
            </template>
            <div class="basket-text-clamp">{{ row.text }}</div>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="danger" @click="basket.removeByKey(row._key)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createFromBasketVisible" title="从素材篮创建素材包" width="520px">
      <el-form :model="createFromBasketForm" label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="createFromBasketForm.name" placeholder="例如：热点合集素材包" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createFromBasketForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-alert
          :title="`将写入 ${basket.count} 条素材（本地已去重）。`"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="createFromBasketVisible = false">取消</el-button>
        <el-button type="primary" :loading="createFromBasketLoading" @click="onCreateFromBasket">
          创建并写入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportToPackVisible" title="将素材篮写入到已有素材包" width="560px">
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

        <el-form-item label="写入后清空素材篮">
          <el-switch v-model="exportClearBasket" style="--el-switch-on-color: #13ce66" />
        </el-form-item>

        <el-alert
          :title="`将写入 ${basket.count} 条素材（素材篮本地已去重；后端仍会生成 text_hash）。`"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="exportToPackVisible = false">取消</el-button>
        <el-button type="primary" :loading="exportToPackLoading" @click="onExportToPack">
          写入
        </el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { MaterialPack, MaterialPackCreate } from "@/types";
import { batchCreateMaterialItems, createMaterialPack, listMaterialPacks } from "@/api/materials";
import { useMaterialBasketStore } from "@/stores/materialBasket";

const props = defineProps<{
  modelValue: boolean;
  title?: string;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "written", packId: number): void;
  (e: "created", packId: number): void;
}>();

const basket = useMaterialBasketStore();

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit("update:modelValue", v),
});

const drawerTitle = computed(() => props.title || `素材篮（${basket.count}）`);

const exportToPackVisible = ref(false);
const exportToPackLoading = ref(false);
const exportToPackId = ref<number | null>(null);
const exportClearBasket = ref(true);
const exportPackOptions = ref<MaterialPack[]>([]);

const loadExportPackOptions = async () => {
  try {
    const resp = await listMaterialPacks({
      keyword: undefined,
      limit: 200,
      offset: 0,
    });
    exportPackOptions.value = resp.items || [];
  } catch (err: any) {
    ElMessage.error(err.message || "加载素材包列表失败");
  }
};

const openExportToPack = async () => {
  exportToPackId.value = null;
  exportClearBasket.value = true;
  exportToPackVisible.value = true;
  await loadExportPackOptions();
};

const onExportToPack = async () => {
  if (basket.count === 0) {
    ElMessage.warning("素材篮为空");
    return;
  }
  if (!exportToPackId.value) {
    ElMessage.warning("请选择目标素材包");
    return;
  }

  exportToPackLoading.value = true;
  try {
    await batchCreateMaterialItems(exportToPackId.value, {
      items: basket.items.map((x) => ({
        item_type: x.item_type,
        text: x.text,
        source_url: x.source_url,
        source_content_id: x.source_content_id,
        source_event_id: x.source_event_id,
        meta: x.meta,
      })),
    });

    if (exportClearBasket.value) {
      basket.clear();
    }

    ElMessage.success("已写入到素材包");
    exportToPackVisible.value = false;
    visible.value = false;
    emit("written", exportToPackId.value);
  } catch (err: any) {
    ElMessage.error(err.message || "写入失败");
  } finally {
    exportToPackLoading.value = false;
  }
};

const createFromBasketVisible = ref(false);
const createFromBasketLoading = ref(false);
const createFromBasketForm = reactive<MaterialPackCreate>({
  name: "",
  description: "",
});

const openCreateFromBasket = () => {
  createFromBasketForm.name = "";
  createFromBasketForm.description = "";
  createFromBasketVisible.value = true;
};

const onCreateFromBasket = async () => {
  if (!createFromBasketForm.name.trim()) {
    ElMessage.warning("请填写素材包名称");
    return;
  }
  if (basket.count === 0) {
    ElMessage.warning("素材篮为空");
    return;
  }

  createFromBasketLoading.value = true;
  try {
    const pack = await createMaterialPack({
      name: createFromBasketForm.name.trim(),
      description: createFromBasketForm.description || undefined,
    });

    await batchCreateMaterialItems(pack.id, {
      items: basket.items.map((x) => ({
        item_type: x.item_type,
        text: x.text,
        source_url: x.source_url,
        source_content_id: x.source_content_id,
        source_event_id: x.source_event_id,
        meta: x.meta,
      })),
    });

    basket.clear();
    ElMessage.success("已创建素材包并写入素材");
    createFromBasketVisible.value = false;
    visible.value = false;
    emit("created", pack.id);
  } catch (err: any) {
    ElMessage.error(err.message || "创建失败");
  } finally {
    createFromBasketLoading.value = false;
  }
};
</script>

<style scoped>
.basket-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
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
</style>
