<template>
  <div class="page-container">
    <div class="header">
      <div class="left">
        <h2 class="title">发布（公众号草稿箱）</h2>
        <div class="desc">先支持微信公众号草稿箱；后续可扩展到更多平台（provider 化）。</div>
      </div>
      <div class="actions">
        <el-button @click="fetchAll" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>发布账号</span>
              <el-button type="primary" @click="openCreateAccount">新增账号</el-button>
            </div>
          </template>

          <el-table :data="accounts" v-loading="loading" style="width: 100%" max-height="520">
            <el-table-column prop="id" label="#" width="80" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="provider" label="平台" width="140" />
            <el-table-column prop="is_active" label="启用" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-alert
            class="mt12"
            title="当前只支持 wechat_official（公众号）。账号配置需填 appid/secret。"
            type="info"
            show-icon
            :closable="false"
          />
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>创建草稿任务</span>
              <div class="right">
                <el-radio-group v-model="submitMode" size="small">
                  <el-radio-button label="sync">同步</el-radio-button>
                  <el-radio-button label="async">异步队列</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>

          <el-form :model="draftForm" label-position="top">
            <el-form-item label="发布账号" required>
              <el-select v-model="draftForm.account_id" filterable placeholder="选择账号" style="width: 100%">
                <el-option
                  v-for="a in accounts"
                  :key="a.id"
                  :label="`#${a.id} ${a.name} (${a.provider})`"
                  :value="a.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="文章 ID" required>
              <el-select
                v-model="draftForm.article_id"
                filterable
                clearable
                placeholder="搜索文章标题/ID"
                style="width: 100%"
                :loading="articlesLoading"
              >
                <el-option
                  v-for="it in articles"
                  :key="it.id"
                  :label="`#${it.id} ${it.title}`"
                  :value="it.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="封面图 URL" required>
              <el-input v-model="draftForm.thumb_image_url" placeholder="https://.../cover.jpg">
                <template #append>
                  <el-upload
                    accept="image/*"
                    :show-file-list="false"
                    :http-request="onUploadCover"
                    :disabled="coverUploading"
                  >
                    <el-button :loading="coverUploading">上传</el-button>
                  </el-upload>
                </template>
              </el-input>
            </el-form-item>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="作者（可选）">
                  <el-input v-model="draftForm.author" placeholder="可不填" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="摘要（可选）">
                  <el-input v-model="draftForm.digest" placeholder="可不填" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="原文链接（可选）">
              <el-input v-model="draftForm.content_source_url" placeholder="https://..." />
            </el-form-item>

            <el-button type="primary" :loading="submitLoading" @click="onSubmit">
              {{ submitMode === 'sync' ? '创建草稿（同步）' : '创建草稿（异步）' }}
            </el-button>
          </el-form>

          <el-divider />

          <div class="task-area">
            <div class="task-header">
              <div class="task-title">任务查询 / 重试</div>
              <div class="task-actions">
                <el-input v-model.number="taskQueryId" type="number" placeholder="输入 task_id" style="width: 180px" />
                <el-button @click="onQueryTask" :loading="taskLoading">查询</el-button>
                <el-button type="warning" @click="onRetryTask" :disabled="!task" :loading="taskLoading">重试</el-button>
              </div>
            </div>

            <el-descriptions v-if="task" class="task-descriptions" :column="2" border>
              <el-descriptions-item label="task_id">{{ task.id }}</el-descriptions-item>
              <el-descriptions-item label="status">{{ task.status }}</el-descriptions-item>
              <el-descriptions-item label="provider">{{ task.provider }}</el-descriptions-item>
              <el-descriptions-item label="action">{{ task.action }}</el-descriptions-item>
              <el-descriptions-item label="attempts">{{ task.attempts }} / {{ task.max_attempts }}</el-descriptions-item>
              <el-descriptions-item label="dlq">{{ task.dlq ? '是' : '否' }}</el-descriptions-item>
              <el-descriptions-item label="celery_task_id">{{ task.celery_task_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="next_retry_at">{{ task.next_retry_at || '-' }}</el-descriptions-item>
              <el-descriptions-item label="remote_id">{{ task.remote_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="error_code">{{ task.error_code || '-' }}</el-descriptions-item>
              <el-descriptions-item label="error_message" :span="2">{{ task.error_message || '-' }}</el-descriptions-item>
            </el-descriptions>

            <el-alert
              v-else
              title="暂无任务信息。你可以先创建草稿任务，或输入 task_id 查询。"
              type="info"
              show-icon
              :closable="false"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="accountDialogVisible" title="新增发布账号（公众号）" width="560px">
      <el-form :model="accountForm" label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="accountForm.name" placeholder="例如：公众号-A" />
        </el-form-item>
        <el-form-item label="平台" required>
          <el-select v-model="accountForm.provider" style="width: 100%">
            <el-option label="微信公众号（wechat_official）" value="wechat_official" />
          </el-select>
        </el-form-item>

        <el-divider />

        <el-form-item label="AppID" required>
          <el-input v-model="accountForm.appid" placeholder="wx..." />
        </el-form-item>
        <el-form-item label="AppSecret" required>
          <el-input v-model="accountForm.secret" placeholder="..." show-password />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="accountDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="accountCreating" @click="onCreateAccount">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { UploadRequestOptions } from "element-plus";
import type { Article, PublishAccount, PublishTask } from "@/types";
import { listArticles } from "@/api/articles";
import { uploadImage } from "@/api/upload";
import {
  createPublishAccount,
  createWechatDraft,
  enqueueWechatDraft,
  getPublishTask,
  listPublishAccounts,
  retryPublishTask,
} from "@/api/publish";

const loading = ref(false);
const submitLoading = ref(false);
const taskLoading = ref(false);
const articlesLoading = ref(false);
const coverUploading = ref(false);

const accounts = ref<PublishAccount[]>([]);
const articles = ref<Article[]>([]);

const submitMode = ref<"sync" | "async">("async");

const draftForm = reactive({
  account_id: null as number | null,
  article_id: null as number | null,
  thumb_image_url: "",
  author: "",
  digest: "",
  content_source_url: "",
});

const taskQueryId = ref<number | null>(null);
const task = ref<PublishTask | null>(null);

const accountDialogVisible = ref(false);
const accountCreating = ref(false);
const accountForm = reactive({
  name: "",
  provider: "wechat_official",
  appid: "",
  secret: "",
});

const fetchAll = async () => {
  loading.value = true;
  try {
    accounts.value = await listPublishAccounts();
    articlesLoading.value = true;
    try {
      articles.value = await listArticles();
    } finally {
      articlesLoading.value = false;
    }
  } catch (err: any) {
    ElMessage.error(err.message || "加载账号失败");
  } finally {
    loading.value = false;
  }
};

const onUploadCover = async (options: UploadRequestOptions) => {
  coverUploading.value = true;
  try {
    const file = options.file as File;
    const res = await uploadImage(file);
    draftForm.thumb_image_url = res.url;
    ElMessage.success("上传成功，已回填封面 URL");
    options.onSuccess && options.onSuccess(res as any);
  } catch (err: any) {
    ElMessage.error(err.message || "上传失败");
    options.onError && options.onError(err);
  } finally {
    coverUploading.value = false;
  }
};

const openCreateAccount = () => {
  accountForm.name = "";
  accountForm.provider = "wechat_official";
  accountForm.appid = "";
  accountForm.secret = "";
  accountDialogVisible.value = true;
};

const onCreateAccount = async () => {
  if (!accountForm.name.trim()) {
    ElMessage.warning("请填写名称");
    return;
  }
  if (!accountForm.appid.trim() || !accountForm.secret.trim()) {
    ElMessage.warning("请填写 appid/secret");
    return;
  }

  accountCreating.value = true;
  try {
    const acc = await createPublishAccount({
      name: accountForm.name.trim(),
      provider: accountForm.provider,
      config: { appid: accountForm.appid.trim(), secret: accountForm.secret.trim() },
    });
    ElMessage.success(`创建成功：#${acc.id}`);
    accountDialogVisible.value = false;
    await fetchAll();
  } catch (err: any) {
    ElMessage.error(err.message || "创建失败");
  } finally {
    accountCreating.value = false;
  }
};

const onSubmit = async () => {
  if (!draftForm.account_id) {
    ElMessage.warning("请选择账号");
    return;
  }
  if (!draftForm.article_id) {
    ElMessage.warning("请填写文章 ID");
    return;
  }
  if (!draftForm.thumb_image_url.trim()) {
    ElMessage.warning("请填写封面图 URL");
    return;
  }

  submitLoading.value = true;
  try {
    const payload = {
      account_id: draftForm.account_id,
      article_id: draftForm.article_id,
      thumb_image_url: draftForm.thumb_image_url.trim(),
      author: draftForm.author || undefined,
      digest: draftForm.digest || undefined,
      content_source_url: draftForm.content_source_url || undefined,
    };

    const res =
      submitMode.value === "sync"
        ? await createWechatDraft(payload)
        : await enqueueWechatDraft(payload);

    task.value = res;
    taskQueryId.value = res.id;
    ElMessage.success(`已创建任务 #${res.id}，状态：${res.status}`);
  } catch (err: any) {
    ElMessage.error(err.message || "提交失败");
  } finally {
    submitLoading.value = false;
  }
};

const onQueryTask = async () => {
  if (!taskQueryId.value) {
    ElMessage.warning("请输入 task_id");
    return;
  }
  taskLoading.value = true;
  try {
    task.value = await getPublishTask(taskQueryId.value);
  } catch (err: any) {
    ElMessage.error(err.message || "查询失败");
  } finally {
    taskLoading.value = false;
  }
};

const onRetryTask = async () => {
  if (!task.value) return;
  taskLoading.value = true;
  try {
    task.value = await retryPublishTask(task.value.id);
    ElMessage.success("已投递重试");
  } catch (err: any) {
    ElMessage.error(err.message || "重试失败");
  } finally {
    taskLoading.value = false;
  }
};

onMounted(async () => {
  await fetchAll();
});
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mt12 {
  margin-top: 12px;
}

.task-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.task-descriptions {
  width: 100%;
}

.task-descriptions :deep(.el-descriptions__table) {
  width: 100%;
  table-layout: fixed;
}

.task-descriptions :deep(.el-descriptions__cell) {
  max-width: 0;
}

.task-descriptions :deep(.el-descriptions__content) {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
