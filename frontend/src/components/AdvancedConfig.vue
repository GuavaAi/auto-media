<template>
  <div class="advanced-config">
    <el-form label-width="120px" :inline="false" size="small">
      <el-form-item label="请求头 (Headers)">
        <div class="kv-list">
          <div class="kv-row" v-for="(item, idx) in headers" :key="idx">
            <el-input v-model="item.key" placeholder="Header 名称" />
            <el-input v-model="item.value" placeholder="Header 值" />
            <el-button type="text" @click="removeHeader(idx)">删除</el-button>
          </div>
          <el-button type="primary" link @click="addHeader">+ 添加 Header</el-button>
        </div>
      </el-form-item>

      <template v-if="sourceType === 'url'">
        <el-form-item label="抓取引擎">
          <div class="kv-list">
            <el-select v-model="crawlerEngine" placeholder="选择抓取引擎">
              <el-option label="playwright（JS 渲染）" value="playwright" />
              <el-option label="crawl4ai（本地高级解析）" value="crawl4ai" />
              <el-option label="FireCrawl（云端反爬）" value="firecrawl" />
            </el-select>
            <p class="tip">默认使用 crawl4ai</p>
          </div>
        </el-form-item>
        <el-form-item v-if="crawlerEngine === 'firecrawl'" label="FireCrawl 配置">
          <div class="kv-list">
            <div class="inline-row mb8">
              <el-tag v-if="firecrawlKeyPoolConfigured" type="success">API Key：已配置（来自 API Key 池）</el-tag>
              <el-tag v-else type="warning">API Key：未配置</el-tag>
              <el-button
                v-if="!firecrawlKeyPoolConfigured"
                type="primary"
                link
                :disabled="firecrawlKeyPoolLoading"
                @click="goToApiKeyPool"
              >
                前往配置
              </el-button>
              <el-button link :loading="firecrawlKeyPoolLoading" @click="fetchFirecrawlKeyPoolStatus">
                刷新状态
              </el-button>
            </div>
            <p class="tip">BaseURL：默认官方 https://api.firecrawl.dev/v2（无需填写）</p>
            <p class="tip">说明：FireCrawl 的“关键词搜索”已迁移到 API 数据源模式；此处仅用于 URL 抓取。</p>
          </div>
        </el-form-item>
        <el-form-item v-if="crawlerEngine === 'crawl4ai'" label="crawl4ai 配置">
          <div class="kv-list">
            <el-select v-model="crawl4aiBrowser" placeholder="浏览器内核" class="mb8">
              <el-option label="chromium（默认）" value="chromium" />
              <el-option label="firefox" value="firefox" />
              <el-option label="webkit" value="webkit" />
            </el-select>
            <div class="inline-row mb8">
              <el-input
                v-model.number="crawl4aiWaitMs"
                type="number"
                placeholder="渲染等待毫秒，默认 800"
                style="width: 220px"
              />
              <el-switch v-model="crawl4aiStealth" active-text="Stealth" inactive-text="关闭" />
            </div>
            <el-input
              v-model="crawl4aiJsCode"
              type="textarea"
              :rows="3"
              placeholder="可选 JS 代码，换行分多段执行"
            />
            <el-input
              v-model="crawl4aiPrompt"
              type="textarea"
              :rows="3"
              placeholder="可选提示语：用于指导 crawl4ai 做内容抽取/整理（若当前版本不支持将自动忽略）"
            />
            <p class="tip">本地模式需已安装 crawl4ai/Playwright。</p>
          </div>
        </el-form-item>
        <el-form-item label="返回过滤 (可选)">
          <div class="kv-list">
            <div class="inline-row mb8">
              <el-input
                v-model="parser.cssSelector"
                placeholder="正文 CSS 选择器，如 .content"
              />
              <el-button type="primary" link :disabled="!previewUrl" @click="openElementPicker">
                选择元素
              </el-button>
            </div>
            <ElementPicker v-model:visible="elementPickerVisible" :url="previewUrl" @picked="onElementPicked" />
          </div>
        </el-form-item>
        <el-form-item label="抓取子页面">
          <div class="inline-row">
            <el-switch v-model="autoDiscoverSub" />
            <el-input
              v-model.number="maxSubLinks"
              type="number"
              placeholder="子链接数，默认 10"
              style="width: 160px"
              :disabled="!autoDiscoverSub"
            />
          </div>
        </el-form-item>
        <el-form-item v-if="autoDiscoverSub" label="子页面过滤">
          <div class="kv-list">
            <div class="inline-row mb8">
              <el-input
                v-model="subParser.cssSelector"
                placeholder="子页面正文 CSS 选择器，如 .article"
              />
              <el-button
                type="primary"
                link
                :disabled="!previewUrl"
                :loading="subPageLoading"
                @click="openSubPageElementPicker"
              >
                选择元素
              </el-button>
            </div>
            <ElementPicker
              v-model:visible="subPagePickerVisible"
              :url="subPagePreviewUrl"
              @picked="onSubPageElementPicked"
            />
          </div>
        </el-form-item>
        <el-form-item label="JS 渲染">
          <div class="inline-row">
            <el-switch v-model="usePlaywright" />
            <span class="tip">开启后将使用 Playwright 执行 JS 渲染，适合动态页面</span>
          </div>
        </el-form-item>
        <el-form-item label="正文抽取">
          <div class="inline-row">
            <el-switch v-model="useReadability" />
            <span class="tip">默认开启 Readability 抽取主内容；关闭后将直接按页面文本解析</span>
          </div>
        </el-form-item>
      </template>

      <template v-if="sourceType === 'api'">
        <el-form-item label="Method">
          <el-select v-model="api.method" placeholder="选择请求方法">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
        </el-form-item>

        <el-form-item label="查询参数 (Params)">
          <div class="kv-list">
            <div class="kv-row" v-for="(item, idx) in params" :key="idx">
              <el-input v-model="item.key" placeholder="参数名" />
              <el-input v-model="item.value" placeholder="参数值" />
              <el-button type="text" @click="removeParam(idx)">删除</el-button>
            </div>
            <el-button type="primary" link @click="addParam">+ 添加 Param</el-button>
          </div>
        </el-form-item>

        <el-form-item label="请求体 (Body)">
          <el-input
            v-model="api.body"
            type="textarea"
            :rows="4"
            placeholder='可填写 JSON，请求时将作为 body 发送（GET 不会发送 body）'
          />
        </el-form-item>
      </template>

      <template v-if="sourceType === 'document'">
        <el-form-item label="文档配置">
          <p class="tip">文档类型目前无需高级配置，可在此处预留 headers 或解析提示。</p>
        </el-form-item>
      </template>

      <template v-if="sourceType === 'n8n'">
        <el-form-item label="n8n 触发">
          <p class="tip">可在此补充附加 payload/headers，触发时随请求发送。</p>
        </el-form-item>
      </template>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import { listApiKeys } from "@/api/apiKeys";
import { discoverLinks } from "@/api/utils";
import type { ApiKeyOut } from "@/types";
import ElementPicker from "@/components/ElementPicker.vue";

type KV = { key: string; value: string };

const props = defineProps<{
  modelValue: Record<string, unknown> | null;
  sourceType: string;
  previewUrl?: string;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", val: Record<string, unknown>): void;
}>();

const syncingFromModel = ref(false);
const lastEmitted = ref<string>("");

const router = useRouter();

const headers = reactive<KV[]>([]);
const params = reactive<KV[]>([]);
const api = reactive({
  method: "GET",
  body: "",
});
const parser = reactive({
  cssSelector: "",
});
const subParser = reactive({
  cssSelector: "",
});
const autoDiscoverSub = ref<boolean>(true);
const maxSubLinks = ref<number>(10);
const usePlaywright = ref<boolean>(false);
const useReadability = ref<boolean>(true);
const crawlerEngine = ref<string>("crawl4ai");
const crawl4aiBrowser = ref<string>("chromium");
const crawl4aiWaitMs = ref<number | null>(null);
const crawl4aiJsCode = ref<string>("");
const crawl4aiPrompt = ref<string>("");
const crawl4aiStealth = ref<boolean>(true);

const firecrawlKeyPoolLoading = ref(false);
const firecrawlKeyPoolConfigured = ref(false);

const elementPickerVisible = ref(false);
const subPagePickerVisible = ref(false);
const subPagePreviewUrl = ref("");
const subPageLoading = ref(false);

const openElementPicker = () => {
  if (!(props.previewUrl || "").trim()) {
    ElMessage.warning("请先填写用于预览的 URL");
    return;
  }
  elementPickerVisible.value = true;
};

const onElementPicked = (selector: string) => {
  parser.cssSelector = (selector || "").trim();
};

// 子页面元素选择器：先用主页面过滤后的内容发现子页面链接，取第一个作为预览 URL
const openSubPageElementPicker = async () => {
  const baseUrl = (props.previewUrl || "").trim();
  if (!baseUrl) {
    ElMessage.warning("请先填写用于预览的 URL");
    return;
  }
  subPageLoading.value = true;
  try {
    // 传入主页面的 cssSelector，仅在过滤后的内容区域内发现链接
    const resp = await discoverLinks({
      url: baseUrl,
      limit: 1,
      use_playwright: usePlaywright.value,
      css_selector: parser.cssSelector || undefined,
    });
    const links = resp?.links || [];
    if (!links.length) {
      ElMessage.warning("未发现子页面链接，请确认页面（过滤区域内）包含同域链接");
      return;
    }
    subPagePreviewUrl.value = links[0];
    subPagePickerVisible.value = true;
  } catch (err: any) {
    ElMessage.error(err?.message || "发现子页面链接失败");
  } finally {
    subPageLoading.value = false;
  }
};

const onSubPageElementPicked = (selector: string) => {
  subParser.cssSelector = (selector || "").trim();
};

const fetchFirecrawlKeyPoolStatus = async () => {
  firecrawlKeyPoolLoading.value = true;
  try {
    const resp = await listApiKeys({ provider: "firecrawl" });
    const items = (resp?.items || []) as ApiKeyOut[];
    firecrawlKeyPoolConfigured.value = items.some((it) => !!it.is_active);
  } catch (err: any) {
    ElMessage.error(err?.message || "检查 FireCrawl API Key 池状态失败");
    firecrawlKeyPoolConfigured.value = false;
  } finally {
    firecrawlKeyPoolLoading.value = false;
  }
};

const goToApiKeyPool = () => {
  router.push({ path: "/api-keys" });
};

const kvToObj = (list: KV[]) =>
  list.reduce<Record<string, string>>((acc, cur) => {
    if (cur.key) acc[cur.key] = cur.value;
    return acc;
  }, {});

const objToKv = (obj: unknown): KV[] => {
  if (!obj || typeof obj !== "object") return [];
  return Object.entries(obj as Record<string, string>).map(([k, v]) => ({
    key: k,
    value: String(v ?? ""),
  }));
};

const addHeader = () => headers.push({ key: "", value: "" });
const removeHeader = (idx: number) => headers.splice(idx, 1);
const addParam = () => params.push({ key: "", value: "" });
const removeParam = (idx: number) => params.splice(idx, 1);

const resetLocalState = () => {
  syncingFromModel.value = true;
  headers.splice(0, headers.length, ...[{ key: "", value: "" }]);
  params.splice(0, params.length);
  api.method = "GET";
  api.body = "";
  parser.cssSelector = "";
  subParser.cssSelector = "";
  autoDiscoverSub.value = true;
  maxSubLinks.value = 10;
  usePlaywright.value = false;
  useReadability.value = true;
  crawlerEngine.value = "crawl4ai";
  crawl4aiBrowser.value = "chromium";
  crawl4aiWaitMs.value = null;
  crawl4aiJsCode.value = "";
  crawl4aiPrompt.value = "";
  crawl4aiStealth.value = true;
  lastEmitted.value = "{}";
  nextTick(() => {
    syncingFromModel.value = false;
  });
};

const emitValue = () => {
  if (syncingFromModel.value) return;
  const result: Record<string, unknown> = {};
  const headerObj = kvToObj(headers);
  if (Object.keys(headerObj).length) {
    result.headers = headerObj;
  }

  if (props.sourceType === "api") {
    const paramObj = kvToObj(params);
    if (Object.keys(paramObj).length) {
      result.params = paramObj;
    }
    result.method = api.method || "GET";
    if (api.body) {
      try {
        result.body = JSON.parse(api.body);
      } catch {
        result.body = api.body;
      }
    }
  }

  if (props.sourceType === "url") {
    if (crawlerEngine.value) {
      result.crawler_engine = crawlerEngine.value;
    }
    const parserCfg: Record<string, unknown> = {};
    if (parser.cssSelector) parserCfg.css_selector = parser.cssSelector;
    if (Object.keys(parserCfg).length) {
      result.parser = parserCfg;
    }
    result.auto_discover_sub = autoDiscoverSub.value;
    result.max_sub_links = maxSubLinks.value ?? 10;
    result.use_playwright = usePlaywright.value;
    if (crawlerEngine.value === "crawl4ai") {
      const opts: Record<string, unknown> = {};
      if (crawl4aiBrowser.value) opts.browser = crawl4aiBrowser.value;
      if (typeof crawl4aiWaitMs.value === "number" && !Number.isNaN(crawl4aiWaitMs.value)) {
        opts.wait_ms = crawl4aiWaitMs.value;
      }
      const jsList = crawl4aiJsCode.value
        ? crawl4aiJsCode.value
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean)
        : [];
      if (jsList.length) opts.js_code = jsList;
      if (crawl4aiPrompt.value && String(crawl4aiPrompt.value).trim()) {
        opts.prompt = String(crawl4aiPrompt.value).trim();
      }
      opts.stealth = crawl4aiStealth.value;
      if (Object.keys(opts).length) result.crawl4ai_options = opts;
    }

    result.extractor = {
      use_readability: useReadability.value,
    };

    const subParserCfg: Record<string, unknown> = {};
    if (subParser.cssSelector) subParserCfg.css_selector = subParser.cssSelector;
    if (Object.keys(subParserCfg).length) {
      result.sub_parser = subParserCfg;
    }
  }

  if (props.sourceType === "n8n") {
    if (Object.keys(headerObj).length) {
      result.headers = headerObj;
    }
  }

  if (props.sourceType === "document") {
    if (Object.keys(headerObj).length) {
      result.headers = headerObj;
    }
  }

  const serialized = JSON.stringify(result);
  if (serialized === lastEmitted.value) return;
  lastEmitted.value = serialized;
  emit("update:modelValue", result);
};

const initFromModel = (val: Record<string, unknown> | null) => {
  syncingFromModel.value = true;
  if (!val || Object.keys(val).length === 0) {
    // 父组件可能在切换 tab/sourceType 时回传空对象 {}。
    // 此时若本地已存在可编辑行（例如刚点了“添加 Header”但 key 还没填），不应重置，否则会表现为“没反应”。
    lastEmitted.value = "{}";
    if (headers.length === 0) {
      resetLocalState();
      return;
    }
    nextTick(() => {
      syncingFromModel.value = false;
    });
    return;
  }
  lastEmitted.value = JSON.stringify(val);
  headers.splice(0, headers.length, ...objToKv(val?.headers));
  if (headers.length === 0) {
    addHeader();
  }
  params.splice(0, params.length, ...objToKv(val?.params));
  api.method = (val?.method as string) || "GET";
  api.body =
    typeof val?.body === "string"
      ? (val?.body as string)
      : val?.body
        ? JSON.stringify(val.body, null, 2)
        : "";
  const parserCfg = (val?.parser || {}) as Record<string, unknown>;
  parser.cssSelector = (parserCfg.css_selector as string) || "";
  const incomingEngine = String((val?.crawler_engine as string) || "").trim();
  crawlerEngine.value = !incomingEngine || incomingEngine === "requests" ? "crawl4ai" : incomingEngine;
  const c4opts = (val?.crawl4ai_options || {}) as Record<string, unknown>;
  crawl4aiBrowser.value = (c4opts.browser as string) || "chromium";
  const waitMsRaw = c4opts.wait_ms;
  const parsedWait =
    typeof waitMsRaw === "number" && !Number.isNaN(waitMsRaw)
      ? waitMsRaw
      : Number(waitMsRaw);
  crawl4aiWaitMs.value = parsedWait && parsedWait > 0 ? parsedWait : null;
  const jsCodeList = Array.isArray(c4opts.js_code)
    ? (c4opts.js_code as string[])
    : typeof c4opts.js_code === "string"
      ? [c4opts.js_code as string]
      : [];
  crawl4aiJsCode.value = jsCodeList.join("\n");
  crawl4aiPrompt.value =
    (c4opts.prompt as string) || (c4opts.llm_prompt as string) || (c4opts.extraction_prompt as string) || "";
  crawl4aiStealth.value =
    typeof c4opts.stealth === "boolean" ? (c4opts.stealth as boolean) : true;

  const subParserCfg = (val?.sub_parser || {}) as Record<string, unknown>;
  subParser.cssSelector = (subParserCfg.css_selector as string) || "";
  autoDiscoverSub.value =
    typeof (val as Record<string, unknown>)?.auto_discover_sub === "boolean"
      ? ((val as Record<string, unknown>).auto_discover_sub as boolean)
      : true;
  const maxSub = (val as Record<string, unknown>)?.max_sub_links;
  const parsedMax =
    typeof maxSub === "number" && !Number.isNaN(maxSub) ? maxSub : Number(maxSub);
  maxSubLinks.value = parsedMax && parsedMax > 0 ? parsedMax : 10;
  usePlaywright.value =
    typeof (val as Record<string, unknown>)?.use_playwright === "boolean"
      ? ((val as Record<string, unknown>).use_playwright as boolean)
      : false;

  const extractorCfg = (val?.extractor || {}) as Record<string, unknown>;
  useReadability.value =
    typeof extractorCfg.use_readability === "boolean"
      ? (extractorCfg.use_readability as boolean)
      : true;

  nextTick(() => {
    syncingFromModel.value = false;
  });
};

watch(
  () => props.modelValue,
  (val: Record<string, unknown> | null) => initFromModel(val || {}),
  { immediate: true }
);

watch(
  () => crawlerEngine.value,
  (v) => {
    if (v === "firecrawl") {
      fetchFirecrawlKeyPoolStatus();
    }
  },
  { immediate: true }
);

onMounted(() => {
  if (crawlerEngine.value === "firecrawl") {
    fetchFirecrawlKeyPoolStatus();
  }
});

// 初始至少有一行 Header 便于输入
if (headers.length === 0) {
  addHeader();
}

watch(
  () => [
    headers,
    params,
    api.method,
    api.body,
    parser.cssSelector,
    subParser.cssSelector,
    autoDiscoverSub.value,
    maxSubLinks.value,
    usePlaywright.value,
    useReadability.value,
    crawlerEngine.value,
    crawl4aiBrowser.value,
    crawl4aiWaitMs.value,
    crawl4aiJsCode.value,
    crawl4aiPrompt.value,
    crawl4aiStealth.value,
    props.sourceType,
  ],
  () => emitValue(),
  { deep: true }
);
</script>

<style scoped>
.advanced-config {
  width: 100%;
}
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.kv-row {
  display: grid;
  grid-template-columns: 1fr 1fr 80px;
  gap: 8px;
}
.mb8 {
  margin-bottom: 8px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
