<template>
  <div class="unified-search" :class="`mode-${mode}`">
    <div class="config-row">
      <span v-if="mode === 'compact'" class="config-label">引擎</span>
      <el-segmented v-model="form.engine" :options="engineOptions" size="small" class="engine-picker" />
    </div>

    <div class="search-input-row">
      <el-input
        v-model="form.query"
        placeholder="搜索内容..."
        clearable
        class="main-search-input"
        @keyup.enter="submit"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-input-number
        v-if="limitVisible"
        v-model="form.limit"
        :min="1"
        :max="50"
        controls-position="right"
        class="limit-input"
      />
      <el-button type="primary" :loading="loading" class="search-go-btn" @click="submit">
        {{ submitText }}
      </el-button>
    </div>

    <div v-if="mode === 'full'" class="engine-advanced">
      <template v-if="form.engine === 'firecrawl'">
        <div class="field-row">
          <span class="field-label">时间范围</span>
          <el-select v-model="form.tbs" placeholder="不限" class="field-input">
            <el-option label="不限" value="" />
            <el-option label="1 小时内" value="qdr:h" />
            <el-option label="1 天内" value="qdr:d" />
            <el-option label="1 周内" value="qdr:w" />
            <el-option label="1 月内" value="qdr:m" />
            <el-option label="1 年内" value="qdr:y" />
          </el-select>
        </div>
        <div class="field-row">
          <span class="field-label">Sources</span>
          <el-select v-model="form.sources" multiple placeholder="默认 web" class="field-input">
            <el-option label="web" value="web" />
            <el-option label="news" value="news" />
          </el-select>
        </div>
      </template>

      <template v-else-if="form.engine === 'aliyun'">
        <div class="field-row">
          <span class="field-label">搜索引擎</span>
          <el-select v-model="form.engineType" class="field-input">
            <el-option label="Generic（标准）" value="Generic" />
            <el-option label="GenericAdvanced（增强）" value="GenericAdvanced" />
          </el-select>
        </div>
        <div class="field-row">
          <span class="field-label">时间范围</span>
          <el-select v-model="form.timeRange" class="field-input">
            <el-option label="不限" value="NoLimit" />
            <el-option label="1 天内" value="OneDay" />
            <el-option label="1 周内" value="OneWeek" />
            <el-option label="1 月内" value="OneMonth" />
            <el-option label="1 年内" value="OneYear" />
          </el-select>
        </div>
        <div class="field-row">
          <span class="field-label">分类</span>
          <el-select v-model="form.category" clearable filterable placeholder="不限" class="field-input">
            <el-option label="finance 金融" value="finance" />
            <el-option label="law 法律" value="law" />
            <el-option label="medical 医疗" value="medical" />
            <el-option label="internet 互联网（精选）" value="internet" />
            <el-option label="tax 税务" value="tax" />
            <el-option label="news_province 新闻省级" value="news_province" />
            <el-option label="news_center 新闻中央" value="news_center" />
          </el-select>
        </div>
      </template>

      <template v-else>
        <div class="field-row">
          <span class="field-label">搜索引擎</span>
          <el-select v-model="form.serpapiEngine" placeholder="google" class="field-input">
            <el-option label="google" value="google" />
            <el-option label="bing" value="bing" />
            <el-option label="baidu" value="baidu" />
          </el-select>
        </div>
      </template>

      <el-alert
        v-if="showHint"
        :title="engineHint"
        type="info"
        show-icon
        :closable="false"
        class="engine-hint"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import { Search } from "@element-plus/icons-vue";

export type UnifiedSearchEngine = "firecrawl" | "aliyun" | "serpapi";

export interface UnifiedSearchFormValue {
  engine: UnifiedSearchEngine;
  query: string;
  limit: number;
  tbs?: string;
  sources?: string[];
  engineType?: string;
  timeRange?: string;
  category?: string;
  serpapiEngine?: string;
}

const props = withDefaults(
  defineProps<{
    modelValue?: Partial<UnifiedSearchFormValue>;
    mode?: "compact" | "full";
    loading?: boolean;
    submitText?: string;
    showHint?: boolean;
  }>(),
  {
    mode: "full",
    loading: false,
    submitText: "搜索",
    showHint: true,
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", val: UnifiedSearchFormValue): void;
  (e: "submit", val: UnifiedSearchFormValue): void;
}>();

const engineOptions = [
  { label: "阿里云", value: "aliyun" },
  { label: "SerpAPI", value: "serpapi" },
  { label: "Firecrawl", value: "firecrawl" },
];

const form = reactive<UnifiedSearchFormValue>({
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

watch(
  () => props.modelValue,
  (val) => {
    if (!val) return;
    Object.assign(form, val);
  },
  { immediate: true, deep: true }
);

watch(
  form,
  () => {
    emit("update:modelValue", { ...form });
  },
  { deep: true }
);

const limitVisible = computed(() => props.mode === "full" && (form.engine === "firecrawl" || form.engine === "serpapi"));

const engineHint = computed(() => {
  if (form.engine === "firecrawl") {
    return "Firecrawl 搜索 → 自动抓取 → 落库抓取记录 → 同步加入素材篮。";
  }
  if (form.engine === "aliyun") {
    return "阿里统一搜索 → 返回结果（可含正文）→ 落库抓取记录 → 同步加入素材篮。";
  }
  return "SerpAPI 搜索 → 返回结果 → 落库抓取记录 → 同步加入素材篮。";
});

const submit = () => {
  emit("submit", { ...form });
};
</script>

<style scoped>
.unified-search {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-label {
  font-size: 12px;
  color: #909399;
  width: 32px;
  flex-shrink: 0;
}

.engine-picker {
  flex: none;
}

.search-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.main-search-input {
  flex: 1;
}

.main-search-input :deep(.el-input__wrapper) {
  border-radius: 6px;
  padding-left: 8px;
}

.search-go-btn {
  padding: 8px 12px;
}

.limit-input {
  width: 96px;
}

.engine-advanced {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  align-items: center;
}

.field-label {
  font-size: 12px;
  color: #64748b;
}

.field-input {
  width: 100%;
}

.engine-hint {
  margin-top: 4px;
}
</style>
