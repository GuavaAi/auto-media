<template>
  <div class="page-container">
    <div class="header-section">
      <div class="header-content">
        <h2 class="page-title">API Key 池</h2>
        <p class="page-desc">统一管理第三方平台的 API Key，支持自动轮询选取（后端使用）。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate">新增 Key</el-button>
        <el-button :loading="loading" @click="fetchList">刷新</el-button>
      </div>
    </div>

    <el-card class="main-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="left-panel">
            <el-select
              v-model="provider"
              placeholder="provider（如 firecrawl）"
              style="width: 240px"
              clearable
              filterable
              allow-create
              default-first-option
              @change="fetchList"
              @clear="fetchList"
            >
              <el-option v-for="p in providerOptions" :key="p" :label="p" :value="p">
                <span style="float: left">{{ p }}</span>
                <span style="float: right; color: #8492a6; font-size: 13px">{{ providerCn(p) }}</span>
              </el-option>
            </el-select>
          </div>
          <div class="right-panel">
            <span class="total-text">共 {{ total }} 条</span>
          </div>
        </div>
      </template>

      <el-table :data="items" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="key_masked" label="Key（脱敏）" min-width="160" />
        <el-table-column label="启用" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="(v: boolean) => onToggleActive(row, v)"
              style="--el-switch-on-color: #13ce66"
            />
          </template>
        </el-table-column>
        <el-table-column prop="use_count" label="使用次数" width="100" align="center" />
        <el-table-column prop="last_used_at" label="最近使用" width="180">
          <template #default="{ row }">
            <span>{{ row.last_used_at ? formatDate(row.last_used_at) : "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span>{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 API Key' : '新增 API Key'" width="520px">
      <el-form :model="form" label-position="top">
        <el-form-item label="Provider" required>
          <el-select v-model="form.provider" placeholder="选择 provider" style="width: 100%" :disabled="!!editingId">
            <el-option v-for="p in providerOptions" :key="p" :label="p" :value="p">
              <span style="float: left">{{ p }}</span>
              <span style="float: right; color: #8492a6; font-size: 13px">{{ providerCn(p) }}</span>
            </el-option>

          </el-select>
          <div v-if="form.provider && providerUrl(form.provider)" style="margin-top: 4px; font-size: 13px; line-height: 1.4; color: #909399;">
            申请地址：
            <a
              :href="providerUrl(form.provider)"
              target="_blank"
              rel="noopener noreferrer"
              style="color: #409eff; text-decoration: none"
            >
              {{ providerUrl(form.provider) }}
            </a>
          </div>
        </el-form-item>
        <el-form-item label="名称/备注">
          <el-input v-model="form.name" placeholder="可选" />
        </el-form-item>
        <el-form-item :label="form.provider === 'oss' ? 'AccessKeySecret' : 'Key'" :required="!editingId">
          <el-input
            v-model="form.key"
            type="textarea"
            :rows="2"
            :placeholder="form.provider === 'oss' ? '填写 AccessKeySecret（建议与 extra 分开管理）' : form.provider === 'aliyun_iqs' ? '填写 API Key 或 AccessKeySecret' : 'fc-...'"
          />
        </el-form-item>

        <el-divider content-position="left">扩展配置（extra）</el-divider>

        <template v-if="form.provider === 'openai'">
          <el-form-item label="OpenAI Base URL（可选）">
            <el-input v-model="formExtra.openai.base_url" placeholder="https://api.openai.com/v1" />
          </el-form-item>
          <el-form-item label="OpenAI Model（必填，优先级高于环境变量）">
            <el-input v-model="formExtra.openai.model" placeholder="gpt-4o-mini" />
          </el-form-item>
        </template>

        <template v-else-if="form.provider === 'deepseek'">
          <el-form-item label="DeepSeek API Base（可选）">
            <el-input v-model="formExtra.deepseek.api_base" placeholder="https://api.deepseek.com" />
          </el-form-item>
          <el-form-item label="DeepSeek Model（可选）">
            <el-input v-model="formExtra.deepseek.model" placeholder="deepseek-chat" />
          </el-form-item>
        </template>

        <template v-else-if="form.provider === 'azure_openai'">
          <el-form-item label="Azure Endpoint（必填）">
            <el-input v-model="formExtra.azure.endpoint" placeholder="https://{resource}.openai.azure.com" />
          </el-form-item>
          <el-form-item label="Deployment（必填）">
            <el-input v-model="formExtra.azure.deployment" placeholder="my-gpt-deployment" />
          </el-form-item>
          <el-form-item label="API Version（必填）">
            <el-input v-model="formExtra.azure.api_version" placeholder="2024-02-15-preview" />
          </el-form-item>
        </template>


        <template v-else-if="form.provider === 'aliyun_iqs'">
          <el-alert
            title="模式说明：1. API Key模式（仅填写上方 Key）；2. AK/SK模式（填写上方 Key 为 Secret，下方填写 AccessKeyId）"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 12px"
          />
          <el-form-item label="AccessKeyId（AK/SK 模式必填）">
            <el-input v-model="formExtra.aliyun_iqs.access_key_id" placeholder="LTAI..." />
          </el-form-item>
        </template>

        <template v-else-if="form.provider === 'oss'">
          <el-alert
            title="说明：key 字段用于存 AccessKeySecret；extra 存 endpoint/bucket/access_key_id/prefix/public_base_url。"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 12px"
          />
          <el-form-item label="OSS Endpoint（必填）">
            <el-input v-model="formExtra.oss.endpoint" placeholder="https://oss-cn-hangzhou.aliyuncs.com" />
          </el-form-item>
          <el-form-item label="Bucket（必填）">
            <el-input v-model="formExtra.oss.bucket" placeholder="your-bucket" />
          </el-form-item>
          <el-form-item label="AccessKeyId（必填）">
            <el-input v-model="formExtra.oss.access_key_id" placeholder="LTAI..." />
          </el-form-item>
          <el-form-item label="Prefix（可选）">
            <el-input v-model="formExtra.oss.prefix" placeholder="uploads/" />
          </el-form-item>
          <el-form-item label="Public Base URL / CDN（可选）">
            <el-input v-model="formExtra.oss.public_base_url" placeholder="https://cdn.example.com" />
          </el-form-item>
        </template>

        <el-form-item v-else label="extra（JSON，可选）">
          <el-input v-model="extraJson" type="textarea" :rows="4" placeholder='例如：{"base_url":"...","model":"..."}' />
        </el-form-item>

        <el-form-item label="启用">
          <el-switch v-model="form.is_active" style="--el-switch-on-color: #13ce66" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createApiKey, deleteApiKey, listApiKeys, updateApiKey } from "@/api/apiKeys";
import type { ApiKeyOut } from "@/types";
import { formatDate } from "@/utils/date";
import { API_KEY_PROVIDER_OPTIONS, getProviderCn, getProviderUrl } from "@/utils/providerNames";

const loading = ref(false);
const saving = ref(false);

const provider = ref("");

const providerOptions = Array.from(API_KEY_PROVIDER_OPTIONS);

const providerCn = (p: string) => getProviderCn(p);
const providerUrl = (p: string) => getProviderUrl(p);

const items = ref<ApiKeyOut[]>([]);
const total = ref(0);

const dialogVisible = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  provider: "firecrawl",
  name: "",
  key: "",
  is_active: true,
  extra: undefined as any,
});

const formExtra = reactive({
  openai: {
    base_url: "",
    model: "",
  },
  deepseek: {
    api_base: "",
    model: "",
  },
  azure: {
    endpoint: "",
    deployment: "",
    api_version: "",
  },
  oss: {
    endpoint: "",
    bucket: "",
    access_key_id: "",
    prefix: "",
    public_base_url: "",
  },
  aliyun_iqs: {
    access_key_id: "",
  },
});

const extraJson = ref("");

const resetExtra = () => {
  form.extra = undefined;
  formExtra.openai.base_url = "";
  formExtra.openai.model = "";
  formExtra.deepseek.api_base = "";
  formExtra.deepseek.model = "";
  formExtra.azure.endpoint = "";
  formExtra.azure.deployment = "";
  formExtra.azure.api_version = "";
  formExtra.oss.endpoint = "";
  formExtra.oss.bucket = "";
  formExtra.oss.access_key_id = "";
  formExtra.oss.prefix = "";
  formExtra.oss.public_base_url = "";
  formExtra.aliyun_iqs.access_key_id = "";
  extraJson.value = "";
};

const hydrateExtra = (row?: ApiKeyOut | null) => {
  resetExtra();
  const ex: any = row?.extra || null;
  if (!ex || typeof ex !== "object") return;

  if (row?.provider === "openai") {
    formExtra.openai.base_url = String(ex.base_url || "");
    formExtra.openai.model = String(ex.model || "");
    return;
  }
  if (row?.provider === "deepseek") {
    formExtra.deepseek.api_base = String(ex.api_base || "");
    formExtra.deepseek.model = String(ex.model || "");
    return;
  }
  if (row?.provider === "azure_openai") {
    formExtra.azure.endpoint = String(ex.endpoint || "");
    formExtra.azure.deployment = String(ex.deployment || "");
    formExtra.azure.api_version = String(ex.api_version || "");
    return;
  }

  if (row?.provider === "oss") {
    formExtra.oss.endpoint = String(ex.endpoint || ex.oss_endpoint || "");
    formExtra.oss.bucket = String(ex.bucket || ex.oss_bucket || "");
    formExtra.oss.access_key_id = String(ex.access_key_id || ex.accessKeyId || ex.accessKeyID || "");
    formExtra.oss.prefix = String(ex.prefix || ex.oss_prefix || "");
    formExtra.oss.public_base_url = String(ex.public_base_url || ex.publicBaseUrl || ex.public_base || ex.cdn || "");
    return;
  }

  if (row?.provider === "aliyun_iqs") {
    formExtra.aliyun_iqs.access_key_id = String(ex.access_key_id || ex.accessKeyId || "");
    return;
  }

  try {
    extraJson.value = JSON.stringify(ex, null, 2);
  } catch {
    extraJson.value = "";
  }
};

const fetchList = async () => {
  loading.value = true;
  try {
    const resp = await listApiKeys({
      provider: provider.value ? provider.value.trim() : undefined,
    });
    items.value = resp.items || [];
    total.value = resp.total || 0;
  } catch (err: any) {
    ElMessage.error(err.message || "加载 API Key 列表失败");
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  editingId.value = null;
  form.provider = provider.value || "firecrawl";
  form.name = "";
  form.key = "";
  form.is_active = true;
  resetExtra();
  dialogVisible.value = true;
};

const openEdit = (row: ApiKeyOut) => {
  editingId.value = row.id;
  form.provider = row.provider;
  form.name = row.name || "";
  form.key = "";
  form.is_active = !!row.is_active;
  hydrateExtra(row);
  dialogVisible.value = true;
};

const buildExtraPayload = () => {
  if (form.provider === "openai") {
    const obj: any = {};
    if ((formExtra.openai.base_url || "").trim()) obj.base_url = formExtra.openai.base_url.trim();
    const model = (formExtra.openai.model || "").trim();
    if (!model) {
      throw new Error("OpenAI 需要填写 model（可在 extra 中配置，或使用环境变量 MODEL_OPENAI_MODEL）");
    }
    obj.model = model;
    return Object.keys(obj).length ? obj : null;
  }
  if (form.provider === "deepseek") {
    const obj: any = {};
    if ((formExtra.deepseek.api_base || "").trim()) obj.api_base = formExtra.deepseek.api_base.trim();
    if ((formExtra.deepseek.model || "").trim()) obj.model = formExtra.deepseek.model.trim();
    return Object.keys(obj).length ? obj : null;
  }
  if (form.provider === "azure_openai") {
    const endpoint = (formExtra.azure.endpoint || "").trim();
    const deployment = (formExtra.azure.deployment || "").trim();
    const api_version = (formExtra.azure.api_version || "").trim();
    if (!endpoint || !deployment || !api_version) {
      throw new Error("Azure OpenAI 需要填写 endpoint / deployment / api_version");
    }
    return { endpoint, deployment, api_version };

  }

  if (form.provider === "aliyun_iqs") {
    const access_key_id = (formExtra.aliyun_iqs.access_key_id || "").trim();
    if (access_key_id) {
       // AK/SK mode: copy key (secret) to extra
       return { 
         access_key_id,
         access_key_secret: (form.key || "").trim() 
       };
    }
    // API Key mode: no extra needed (key is in main field)
    return null;
  }

  if (form.provider === "oss") {
    const endpoint = (formExtra.oss.endpoint || "").trim();
    const bucket = (formExtra.oss.bucket || "").trim();
    const access_key_id = (formExtra.oss.access_key_id || "").trim();
    if (!endpoint || !bucket || !access_key_id) {
      throw new Error("OSS 需要填写 endpoint / bucket / access_key_id；AccessKeySecret 请填写在 key 字段");
    }
    const obj: any = { endpoint, bucket, access_key_id };
    if ((formExtra.oss.prefix || "").trim()) obj.prefix = (formExtra.oss.prefix || "").trim();
    if ((formExtra.oss.public_base_url || "").trim()) obj.public_base_url = (formExtra.oss.public_base_url || "").trim();
    return obj;
  }

  const s = (extraJson.value || "").trim();
  if (!s) return null;
  try {
    const obj = JSON.parse(s);
    return obj && typeof obj === "object" ? obj : null;
  } catch {
    throw new Error("extra JSON 格式不正确");
  }
};

const onSave = async () => {
  const prov = (form.provider || "").trim();
  if (!prov) {
    ElMessage.warning("请填写 provider");
    return;
  }
  if (!editingId.value && !(form.key || "").trim()) {
    ElMessage.warning("请填写 key");
    return;
  }

  saving.value = true;
  try {
    const extra = buildExtraPayload();
    if (editingId.value) {
      const payload: any = {
        name: form.name || null,
        is_active: form.is_active,
      };
      if ((form.key || "").trim()) payload.key = (form.key || "").trim();
      payload.extra = extra;
      await updateApiKey(editingId.value, payload);
      ElMessage.success("更新成功");
    } else {
      await createApiKey({
        provider: prov,
        name: form.name || null,
        key: (form.key || "").trim(),
        is_active: form.is_active,
        extra,
      });
      ElMessage.success("创建成功");
    }
    dialogVisible.value = false;
    await fetchList();
  } catch (err: any) {
    ElMessage.error(err.message || "保存失败");
  } finally {
    saving.value = false;
  }
};

const onDelete = async (row: ApiKeyOut) => {
  try {
    await ElMessageBox.confirm(
      `确定删除该 Key 吗？\n${row.provider}${row.name ? ` / ${row.name}` : ""}`,
      "提示",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
    await deleteApiKey(row.id);
    ElMessage.success("删除成功");
    await fetchList();
  } catch (err: any) {
    if (err !== "cancel") {
      ElMessage.error(err.message || "删除失败");
    }
  }
};

const onToggleActive = async (row: ApiKeyOut, v: boolean) => {
  try {
    await updateApiKey(row.id, { is_active: v });
  } catch (err: any) {
    ElMessage.error(err.message || "更新失败");
    row.is_active = !v;
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

.total-text {
  color: #6b7280;
}
</style>
