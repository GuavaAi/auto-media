<template>
  <el-dialog v-model="visibleInner" title="选择页面元素" width="1100px" align-center destroy-on-close>
    <div class="toolbar">
      <el-input v-model="urlInner" placeholder="请输入要预览的 URL" />
      <el-switch v-model="usePlaywright" active-text="JS 渲染" inactive-text="静态" />
      <el-button type="primary" :loading="loading" @click="load">加载预览</el-button>
      <el-button :disabled="!pickedSelector" @click="applyPicked">使用该 Selector</el-button>
    </div>

    <div class="content">
      <div class="left">
        <div class="label">当前选择</div>
        <el-input v-model="pickedSelector" readonly placeholder="点击右侧预览中的元素以生成 selector" />
        <div class="tip">
          说明：在右侧页面中移动鼠标会高亮元素，点击后会生成 CSS Selector。
        </div>
      </div>
      <div class="right">
        <div v-if="!html" class="empty">请先加载预览</div>
        <iframe
          v-else
          ref="iframeRef"
          class="preview"
          :srcdoc="html"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="close">关闭</el-button>
      <el-button type="primary" :disabled="!pickedSelector" @click="applyPicked">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { getPagePreviewHtml } from "@/api/utils";

const props = defineProps<{
  visible: boolean;
  url?: string;
  engine?: string;
}>();

const emit = defineEmits<{
  (e: "update:visible", v: boolean): void;
  (e: "picked", selector: string): void;
}>();

const visibleInner = computed({
  get: () => props.visible,
  set: (v: boolean) => emit("update:visible", v),
});

const iframeRef = ref<HTMLIFrameElement | null>(null);

const urlInner = ref<string>("");
const usePlaywright = ref<boolean>(false);
const loading = ref(false);
const html = ref<string>("");
const pickedSelector = ref<string>("");

const load = async () => {
  const u = (urlInner.value || "").trim();
  if (!u) {
    ElMessage.warning("请填写要预览的 URL");
    return;
  }
  loading.value = true;
  try {
    html.value = await getPagePreviewHtml({ url: u, use_playwright: usePlaywright.value });
    pickedSelector.value = "";
  } catch (err: any) {
    ElMessage.error(err?.message || "加载预览失败");
  } finally {
    loading.value = false;
  }
};

const close = () => {
  emit("update:visible", false);
};

const applyPicked = () => {
  const sel = (pickedSelector.value || "").trim();
  if (!sel) return;
  emit("picked", sel);
  emit("update:visible", false);
};

const onMessage = (event: MessageEvent) => {
  const iframeWin = iframeRef.value?.contentWindow;
  if (!iframeWin || event.source !== iframeWin) return;
  const data = event.data as any;
  if (!data || typeof data !== "object") return;
  if (data.type === "element-picked" && typeof data.selector === "string") {
    pickedSelector.value = data.selector;
  }
  if (data.type === "element-picker-cancel") {
    close();
  }
};

watch(
  () => props.visible,
  (v) => {
    if (v) {
      urlInner.value = (props.url || "").trim();
      html.value = "";
      pickedSelector.value = "";

      // 中文说明：firecrawl/crawl4ai/playwright 默认属于“动态渲染”抓取
      const eng = String(props.engine || "").trim().toLowerCase();
      const dynamicDefault = eng === "playwright" || eng === "firecrawl" || eng === "crawl4ai";
      usePlaywright.value = dynamicDefault;

      if (urlInner.value) {
        load();
      }
    }
  }
);

watch(
  () => props.engine,
  (e) => {
    // 仅在弹窗打开时才联动默认值，避免用户手动切换被打断
    if (!props.visible) return;
    const eng = String(e || "").trim().toLowerCase();
    const dynamicDefault = eng === "playwright" || eng === "firecrawl" || eng === "crawl4ai";
    usePlaywright.value = dynamicDefault;
  }
);

onMounted(() => {
  window.addEventListener("message", onMessage);
});

onBeforeUnmount(() => {
  window.removeEventListener("message", onMessage);
});
</script>

<style scoped>
.toolbar {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.content {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
  height: 600px;
}

.left {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.label {
  font-weight: 600;
}

.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.right {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.preview {
  width: 100%;
  height: 100%;
  border: 0;
}

.empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
}
</style>
