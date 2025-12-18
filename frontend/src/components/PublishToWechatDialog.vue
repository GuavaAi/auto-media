<template>
  <el-dialog
    :model-value="modelValue"
    title="一键发布到公众号（草稿箱）"
    width="640px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @open="onOpen"
  >
    <el-alert
      v-if="!wechatAccounts.length"
      type="warning"
      :closable="false"
      show-icon
      title="暂无可用的公众号发布账号，请先到【发布】页面创建并启用账号。"
      class="mb12"
    />

    <el-form label-position="top">
      <el-form-item label="发布账号" required>
        <el-select
          v-model="form.account_id"
          filterable
          placeholder="选择发布账号"
          style="width: 100%"
          :disabled="accountsLoading || !wechatAccounts.length"
        >
          <el-option
            v-for="a in wechatAccounts"
            :key="a.id"
            :label="`#${a.id} ${a.name}${a.is_active ? '' : '（未启用）'}`"
            :value="a.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="封面图 URL" required>
        <el-input v-model="form.thumb_image_url" placeholder="https://.../cover.jpg" :disabled="!wechatAccounts.length">
          <template #append>
            <el-upload
              accept="image/*"
              :show-file-list="false"
              :http-request="onUploadCover"
              :disabled="coverUploading || !wechatAccounts.length"
            >
              <el-button :loading="coverUploading">上传</el-button>
            </el-upload>
          </template>
        </el-input>
      </el-form-item>

      <el-form-item label="摘要（可选）">
        <el-input v-model="form.digest" type="textarea" :rows="2" placeholder="默认使用文章摘要" />
      </el-form-item>

      <el-form-item label="作者（可选）">
        <el-input v-model="form.author" placeholder="可不填" />
      </el-form-item>

      <el-form-item label="原文链接（可选）">
        <el-input v-model="form.content_source_url" placeholder="https://..." />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :loading="publishing"
        :disabled="!wechatAccounts.length"
        @click="onPublish"
      >
        发布到草稿箱
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { UploadRequestOptions } from "element-plus";
import type { PublishAccount, PublishTask } from "@/types";
import { listPublishAccounts, enqueueWechatDraft } from "@/api/publish";
import { uploadImage } from "@/api/upload";

const props = defineProps<{
  modelValue: boolean;
  articleId: number | null;
  defaultDigest?: string;
  defaultAuthor?: string;
  defaultContentSourceUrl?: string;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "success", task: PublishTask): void;
}>();

const accounts = ref<PublishAccount[]>([]);
const accountsLoading = ref(false);
const coverUploading = ref(false);
const publishing = ref(false);

const form = reactive({
  account_id: null as number | null,
  thumb_image_url: "",
  digest: "",
  author: "",
  content_source_url: "",
});

const wechatAccounts = computed(() => accounts.value.filter((a) => a.provider === "wechat_official"));

const fetchAccounts = async () => {
  accountsLoading.value = true;
  try {
    accounts.value = await listPublishAccounts();
  } catch (err: any) {
    ElMessage.error(err.message || "加载发布账号失败");
  } finally {
    accountsLoading.value = false;
  }
};

const resetForm = () => {
  // 关键逻辑：每次打开弹窗都重置表单，避免沿用上一次发布的封面/账号
  form.account_id = null;
  form.thumb_image_url = "";
  form.digest = props.defaultDigest || "";
  form.author = props.defaultAuthor || "";
  form.content_source_url = props.defaultContentSourceUrl || "";

  const active = wechatAccounts.value.find((a) => a.is_active);
  const first = wechatAccounts.value[0];
  form.account_id = (active || first)?.id ?? null;
};

const onOpen = async () => {
  if (!accounts.value.length) {
    await fetchAccounts();
  }
  resetForm();
};

const onUploadCover = async (options: UploadRequestOptions) => {
  coverUploading.value = true;
  try {
    const file = options.file as File;
    const res = await uploadImage(file);
    form.thumb_image_url = res.url;
    ElMessage.success("上传成功，已回填封面 URL");
    options.onSuccess && options.onSuccess(res as any);
  } catch (err: any) {
    ElMessage.error(err.message || "上传失败");
    options.onError && options.onError(err);
  } finally {
    coverUploading.value = false;
  }
};

const onPublish = async () => {
  if (!props.articleId) {
    ElMessage.warning("文章尚未加载完成");
    return;
  }
  if (!form.account_id) {
    ElMessage.warning("请选择发布账号");
    return;
  }
  if (!form.thumb_image_url.trim()) {
    ElMessage.warning("请填写封面图 URL");
    return;
  }

  publishing.value = true;
  try {
    const task = await enqueueWechatDraft({
      account_id: form.account_id,
      article_id: props.articleId,
      thumb_image_url: form.thumb_image_url.trim(),
      author: form.author || undefined,
      digest: form.digest || undefined,
      content_source_url: form.content_source_url || undefined,
    });

    ElMessage.success(`已创建发布任务 #${task.id}，可到【发布】页面查询进度`);
    emit("success", task);
    emit("update:modelValue", false);
  } catch (err: any) {
    ElMessage.error(err.message || "创建发布任务失败");
  } finally {
    publishing.value = false;
  }
};
</script>

<style scoped>
.mb12 {
  margin-bottom: 12px;
}
</style>
