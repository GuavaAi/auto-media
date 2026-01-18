<template>
  <div class="page-container notebooklm-page">
    <div class="notebooklm-layout">
      <ResourceSidebar :onSearch="sidebarSearch" :onUrl="sidebarUrl" :onPaste="sidebarPaste" />

      <WorkspacePanel>
        <template #status>
          <div class="status-bar">
            <el-alert
              title="将数据与灵感，转化为高质量内容。填入主题和大纲，选择模型，一键生成 Markdown/HTML。"
              type="info"
              show-icon
              :closable="false"
              class="page-tip"
            />
            <div class="stat-group">
              <div class="stat-item">
                <span class="label">当前模型</span>
                <span class="value">{{ currentProviderLabel }}</span>
              </div>
              <el-divider direction="vertical" />
              <div class="stat-item">
                <span class="label">推荐字数</span>
                <span class="value">{{ lengthDisplay }}</span>
              </div>
            </div>
          </div>
        </template>

        <template #main>
          <el-row :gutter="24" class="main-row">
            <!-- 左侧表单区 -->
            <el-col :span="15" :lg="16" :xl="17">
              <el-card class="form-card" shadow="never">
                <template #header>
                  <div class="card-header">
                    <span class="title">配置参数</span>
                    <div class="header-actions">
                      <el-button link type="primary" @click="reset">重置配置</el-button>
                    </div>
                  </div>
                </template>
                
                <el-form :model="form" label-position="top" class="generate-form">
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="核心主题 / 标题" required>
                  <el-input 
                    v-model="form.topic" 
                    placeholder="例如：AI 在自媒体写作的应用" 
                    size="large"
                    class="topic-input"
                  >
                    <template #prefix>
                      <el-icon><EditPen /></el-icon>
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="语气风格">
                  <el-select
                    v-model="form.tone"
                    placeholder="例如：专业且亲和"
                    filterable
                    allow-create
                    default-first-option
                    style="width: 100%"
                  >
                    <el-option
                      v-for="t in toneOptions"
                      :key="t"
                      :label="t"
                      :value="t"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="关键词 (逗号分隔)">
                  <el-input v-model="keywordsInput" placeholder="DeepSeek, 自动化, 生产力" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="文章大纲（可选）">
              <el-input
                v-model="outlineInput"
                type="textarea"
                :rows="4"
                placeholder="每行一条，例如：
1. 现状与痛点
2. 模型能力分析
3. 落地实战建议"
              />
            </el-form-item>

            <el-divider content-position="left">参考素材</el-divider>
            <el-form-item label="素材包（可选，用于注入要点/引用/事实/来源）">
              <div class="material-pack-row">
                <el-select
                  class="material-pack-select"
                  v-model="form.material_pack_id"
                  placeholder="不使用素材包"
                  clearable
                  filterable
                >
                  <el-option label="不使用" :value="undefined" />
                  <el-option
                    v-for="p in materialPacks"
                    :key="p.id"
                    :label="`#${p.id} ${p.name}`"
                    :value="p.id"
                  />
                </el-select>

                <el-button type="primary" plain @click="openSmartPickDialog" class="smart-pick-btn">
                  <el-icon class="el-icon--left"><MagicStick /></el-icon>
                  智能选取素材
                </el-button>
              </div>
            </el-form-item>

            <el-form-item v-if="form.material_pack_id" label="素材条目（可选：仅使用部分条目）">
              <div class="material-picker">
                <div class="material-picker-top">
                  <el-radio-group v-model="materialMode" size="small">
                    <el-radio-button label="all">使用全部</el-radio-button>
                    <el-radio-button label="custom">自选条目</el-radio-button>
                  </el-radio-group>
                  <el-tag v-if="materialDetailLoading" type="info" size="small">加载中...</el-tag>
                  <el-tag v-else type="info" size="small">共 {{ materialPackDetailItems.length }} 条</el-tag>
                </div>

                <div v-if="materialMode === 'custom'" class="material-picker-body">
                  <el-input
                    v-model="materialKeyword"
                    placeholder="搜索条目内容"
                    clearable
                    style="margin-bottom: 10px"
                  />

                  <el-scrollbar max-height="240px" class="material-scroll">
                    <el-checkbox-group v-model="selectedMaterialItemIds">
                      <div
                        v-for="it in filteredMaterialItems"
                        :key="it.id"
                        class="material-item-row"
                      >
                        <el-checkbox :label="it.id">
                          <span class="mi-meta">
                            <el-tag size="small">{{ it.item_type }}</el-tag>
                            <span class="mi-id">#{{ it.id }}</span>
                          </span>
                          <span class="mi-text">{{ it.text }}</span>
                        </el-checkbox>
                      </div>
                    </el-checkbox-group>
                  </el-scrollbar>

                  <div class="material-picker-actions">
                    <el-button link type="primary" @click="selectAllMaterialItems">全选</el-button>
                    <el-button link @click="clearMaterialItemSelection">清空</el-button>
                    <span class="mi-count">已选 {{ selectedMaterialItemIds.length }} / {{ materialPackDetailItems.length }}</span>
                  </div>
                </div>
              </div>
            </el-form-item>

            <!-- 高级设置（默认折叠） -->
            <div class="advanced-panel">
              <div class="advanced-header" @click="advancedOpen = !advancedOpen">
                <span class="advanced-title">高级设置</span>
                <span class="advanced-chevron" :class="{ open: advancedOpen }">›</span>
              </div>

              <div v-show="advancedOpen" class="advanced-body">
                <div class="advanced-grid grid-2">
                  <el-form-item label="Prompt 模板">
                    <el-select
                      v-model="form.template_key"
                      placeholder="默认模板"
                      clearable
                      filterable
                      style="width: 100%"
                      @change="onTemplateKeyChange"
                    >
                      <el-option label="默认模板" value="" />
                      <el-option
                        v-for="it in templateOptions"
                        :key="it.key"
                        :label="it.label"
                        :value="it.key"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item v-if="form.template_key" label="模板版本">
                    <el-radio-group v-model="form.template_version">
                      <el-radio :value="undefined" border>最新</el-radio>
                      <el-radio v-for="v in templateVersions" :key="v" :value="v" border>v{{ v }}</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <div v-else />
                </div>

                <div class="advanced-grid grid-3">
                  <el-form-item label="模型供应商">
                    <ModelProviderSelect v-model="form.provider" placeholder="默认 deepseek" style="width: 100%" />
                  </el-form-item>

                  <el-form-item label="期望字数">
                    <el-input-number v-model="form.length" :min="300" :max="5000" :step="100" style="width: 100%" />
                  </el-form-item>

                  <el-form-item label="随机性 (Temperature)">
                    <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.1" :format-tooltip="(val: number) => val" />
                  </el-form-item>
                </div>

                <div class="advanced-grid grid-2">
                  <el-form-item label="行动号召 (CTA)">
                    <el-input v-model="form.call_to_action" placeholder="例如：关注获取更多实战案例" />
                  </el-form-item>

                  <el-form-item label="补充视角/提示">
                    <el-input v-model="form.summary_hint" placeholder="例如：强调效率提升与风险规避" />
                  </el-form-item>
                </div>
              </div>
            </div>

            <div class="form-footer">
              <el-button type="primary" size="large" :loading="loading" @click="onGenerate" class="submit-btn">
                开始生成内容
                <el-icon class="el-icon--right"><VideoPlay /></el-icon>
              </el-button>
            </div>
          </el-form>
              </el-card>
            </el-col>

      <!-- 右侧结果/提示区 -->
      <el-col :span="9" :lg="8" :xl="7">
         <!-- 结果卡片 -->
        <el-card v-if="result" class="result-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="title">生成结果</span>
              <div class="header-actions">
                <el-tooltip v-if="result && result.id" content="查看详情" placement="top">
                   <el-button circle size="small" @click="goArticleDetail">
                      <el-icon><View /></el-icon>
                   </el-button>
                </el-tooltip>
                <el-tooltip content="复制 Markdown" placement="top">
                   <el-button circle size="small" @click="copyText(result.content_md)">
                      <el-icon><DocumentCopy /></el-icon>
                   </el-button>
                </el-tooltip>
                <el-tooltip content="复制 HTML" placement="top">
                   <el-button circle size="small" type="primary" plain @click="copyHtml(result.content_html)">
                      <el-icon><CopyDocument /></el-icon>
                   </el-button>
                </el-tooltip>
              </div>
            </div>
          </template>
          
          <div class="result-meta">
             <div class="meta-item">
               <span class="label">标题</span>
               <p>{{ result.title }}</p>
             </div>
             <div class="meta-item">
               <span class="label">摘要</span>
               <p class="summary-text">{{ result.summary }}</p>
             </div>
             <div class="meta-tags">
                <el-tag v-if="result.elapsed_ms" size="small" type="info">{{ result.elapsed_ms }}ms</el-tag>
                <el-tag v-if="result.template_key" size="small" type="success">{{ result.template_key }}</el-tag>
             </div>
          </div>

          <el-divider />

          <el-tabs type="border-card" class="result-tabs">
            <el-tab-pane label="预览">
               <div class="preview-content" v-html="result.content_html" />
            </el-tab-pane>
            <el-tab-pane label="Markdown">
               <pre class="code-block">{{ result.content_md }}</pre>
            </el-tab-pane>
            <el-tab-pane label="Prompt">
               <pre class="code-block">{{ result.prompt_text }}</pre>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <!-- 提示卡片 -->
        <el-card class="tips-card" shadow="never" :class="{ 'mt-4': !!result }">
          <template #header>
            <div class="card-header">
              <span class="title">写作助手</span>
              <el-icon class="header-icon"><Reading /></el-icon>
            </div>
          </template>
          <div class="tips-grid">
            <div class="tip-item">
              <div class="tip-icon-wrapper">🎯</div>
              <div class="tip-content">
                <div class="tip-title">主题明确</div>
                <div class="tip-desc">越具体的主题，生成的深度越好。</div>
              </div>
            </div>
            <div class="tip-item">
              <div class="tip-icon-wrapper">📝</div>
              <div class="tip-content">
                <div class="tip-title">大纲引导</div>
                <div class="tip-desc">3-5 个要点能有效控制文章结构。</div>
              </div>
            </div>
            <div class="tip-item">
              <div class="tip-icon-wrapper">🌡️</div>
              <div class="tip-content">
                <div class="tip-title">温度调节</div>
                <div class="tip-desc">0.7 适合大多数创作，1.0 更具创意。</div>
              </div>
            </div>
            <div class="tip-item">
              <div class="tip-icon-wrapper">🔗</div>
              <div class="tip-content">
                <div class="tip-title">数据引用</div>
                <div class="tip-desc">填写数据源 ID 可引用抓取的素材。</div>
              </div>
            </div>
          </div>
        </el-card>
            </el-col>
          </el-row>

    <el-dialog
      v-model="smartPickVisible"
      title="智能选取素材（热点榜单）"
      width="980px"
      destroy-on-close
    >
      <el-alert
        title="输入核心主题，智能筛选当天热点事件；选择后可将热点要点/引用/事实快速导入素材，并写入同名素材包。"
        type="info"
        show-icon
        :closable="false"
        class="smart-tip"
      />

      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="核心主题" required>
              <el-input v-model="smartTopic" placeholder="例如：AI 在自媒体写作的应用" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="日期">
              <el-date-picker
                v-model="smartDay"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="候选范围">
              <el-input-number v-model="smartLimit" :min="10" :max="200" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="补充指令（可选）">
              <el-input v-model="smartInstruction" placeholder="例如：偏向可写成公众号深度解读的事件" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型供应商">
              <ModelProviderSelect
                v-model="smartProvider"
                style="width: 100%"
                :include-empty-option="true"
                empty-label="跟随生成页"
                empty-value=""
              />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="smart-actions">
          <el-button type="primary" :loading="smartLoading" @click="runSmartPick">智能筛选</el-button>
          <el-button
            type="success"
            :disabled="!selectedSmartEventIds.length"
            :loading="basketLoading || writePackLoading"
            @click="oneClickImportAndWrite"
          >
            一键导入素材包并选中
          </el-button>
        </div>
      </el-form>

      <el-divider content-position="left">智能筛选结果</el-divider>

      <el-table
        ref="smartTableRef"
        :data="smartDecisionRows"
        stripe
        size="small"
        v-loading="smartLoading"
        :max-height="360"
        class="smart-table"
        @selection-change="onSmartEventSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="event_id" label="事件ID" width="90" />
        <el-table-column prop="title" label="标题" min-width="260" />
        <el-table-column prop="hot_score" label="热度" width="90" />
        <el-table-column prop="source_count" label="来源数" width="90" />
        <el-table-column label="推荐" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.recommended" size="small" type="success">推荐</el-tag>
            <el-tag v-else size="small" type="info">-</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="分数" width="90" />
        <el-table-column prop="reason" label="原因" min-width="240" />
      </el-table>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="smartPickVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

        </template>
      </WorkspacePanel>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { 
  EditPen, 
  VideoPlay, 
  DocumentCopy, 
  CopyDocument, 
  View,
  Reading,
  MagicStick,
} from "@element-plus/icons-vue";
import { generateArticle, listPromptTemplates } from "@/api/articles";
import {
  listMaterialPacks,
  createMaterialPack,
  batchCreateMaterialItems,
  getMaterialPackDetail,
  firecrawlSearchIngest,
  aliyunUnifiedSearchIngest,
  serpapiSearchIngest,
} from "@/api/materials";
import { getDailyHotspotDetail, listDailyHotspots, smartFilterDailyHotspotList } from "@/api/dailyHotspots";
import { extractCrawlRecordMaterials, quickFetchCrawlRecord } from "@/api/crawlRecords";
import ModelProviderSelect from "@/components/ModelProviderSelect.vue";
import ResourceSidebar from "@/views/generate/layout/ResourceSidebar.vue";
import WorkspacePanel from "@/views/generate/layout/WorkspacePanel.vue";
import type {
  Article,
  DailyHotspotDetailResponse,
  DailyHotspotEvent,
  DailyHotspotListSmartFilterDecision,
  DailyHotspotListSmartFilterResponse,
  GenerationRequest,
  MaterialItem,
  MaterialItemCreate,
  MaterialPack,
  PromptTemplate,
} from "@/types";
import { getProviderCn } from "@/utils/providerNames";
import { useMaterialBasketStore } from "@/stores/materialBasket";

const router = useRouter();
const route = useRoute();

const loading = ref(false);
const result = ref<Article | null>(null);

const toneOptions = [
  "专业且亲和",
  "专业严谨",
  "简洁干货",
  "通俗科普",
  "观点鲜明",
  "幽默风趣",
  "犀利吐槽",
  "故事化叙述",
  "温暖治愈",
  "公众号深度解读",
  "小红书种草",
];

const templates = ref<PromptTemplate[]>([]);
const materialPacks = ref<MaterialPack[]>([]);

const materialPackDetailItems = ref<MaterialItem[]>([]);
const materialDetailLoading = ref(false);
const materialMode = ref<"all" | "custom">("all");
const materialKeyword = ref("");
const selectedMaterialItemIds = ref<number[]>([]);

const advancedOpen = ref(false);

const smartPickVisible = ref(false);
const smartLoading = ref(false);
const basketLoading = ref(false);
const writePackLoading = ref(false);

const smartTopic = ref("");
const smartDay = ref("");
const smartInstruction = ref("");
const smartProvider = ref("");
const smartLimit = ref(50);

const smartDecisions = ref<DailyHotspotListSmartFilterDecision[]>([]);
const smartDecisionRows = ref<
  Array<
    DailyHotspotListSmartFilterDecision & {
      title?: string;
      hot_score?: number;
      source_count?: number;
    }
  >
>([]);
const smartTableRef = ref<any>(null);
const smartRecommendedEventIds = ref<number[]>([]);
const selectedSmartEventIds = ref<number[]>([]);

const basketItems = ref<MaterialItemCreate[]>([]);

const basket = useMaterialBasketStore();

const _norm = (s: string) => (s || "").trim().replace(/\s+/g, " ");

const _dedupeMaterialCreates = (items: MaterialItemCreate[]) => {
  const existed = new Set<string>();
  const out: MaterialItemCreate[] = [];
  for (const it of items || []) {
    const t = _norm(it.item_type || "").toLowerCase();
    const text = _norm(it.text || "");
    const key = `${t}|${text}`;
    if (!key || key.endsWith("|")) continue;
    if (existed.has(key)) continue;
    existed.add(key);
    out.push(it);
  }
  return out;
};

const sidebarSearch = async (payload: { engine: "firecrawl" | "aliyun" | "serpapi"; query: string; limit: number }) => {
  if (payload.engine === "firecrawl") {
    const resp = await firecrawlSearchIngest({ query: payload.query, limit: payload.limit });
    return resp.items || [];
  }
  if (payload.engine === "aliyun") {
    const resp = await aliyunUnifiedSearchIngest({ query: payload.query, include_main_text: true });
    return resp.items || [];
  }
  const resp = await serpapiSearchIngest({ query: payload.query, limit: payload.limit });
  return resp.items || [];
};

const sidebarUrl = async (payload: { url: string }) => {
  const url = (payload.url || "").trim();
  if (!(url.startsWith("http://") || url.startsWith("https://"))) {
    throw new Error("URL 必须以 http:// 或 https:// 开头");
  }
  const rec: any = await quickFetchCrawlRecord({ url, crawler_engine: "playwright" });
  const recId = Number(rec?.id);
  if (!recId) {
    throw new Error("快捷抓取失败：未返回 record_id");
  }
  const resp = await extractCrawlRecordMaterials(recId, { top_k: 10, include_source: true });
  return resp.items || [];
};

const sidebarPaste = async (payload: { text: string }) => {
  const t = (payload.text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!t) return [];
  return [
    {
      item_type: "note",
      text: t,
      meta: { from: "paste" },
    },
  ] as MaterialItemCreate[];
};

const _formatLocalYmdCompact = (d: Date) => {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}${mm}${dd}`;
};

const _rand4 = () => String(Math.floor(Math.random() * 10000)).padStart(4, "0");

const _findOrCreateTempPack = async (topic: string | undefined): Promise<MaterialPack> => {
  const ymd = _formatLocalYmdCompact(new Date());
  const tp = (topic || "").trim();
  const prefix = tp ? `【临时】${tp}-${ymd}-` : `【临时】${ymd}-`;

  const resp = await listMaterialPacks({ keyword: prefix, limit: 50, offset: 0 });
  const existed = (resp.items || []).find((p) => (p.name || "").trim().startsWith(prefix));
  if (existed) return existed;

  const name = `${prefix}${_rand4()}`;
  return await createMaterialPack({ name, description: `临时素材包（自动生成）${ymd}` });
};

const _selectedPackItemsToCreates = async (): Promise<MaterialItemCreate[]> => {
  const pid = form.material_pack_id;
  if (!pid) return [];

  // 中文说明：把用户已选素材包（及其自选条目）“合并追加”写入临时包，确保素材篮 + 素材包都能注入生成。
  let items: MaterialItem[] = materialPackDetailItems.value;
  if (!items.length || (items[0] && items[0].pack_id !== pid)) {
    try {
      const resp = await getMaterialPackDetail(pid);
      items = resp.items || [];
    } catch {
      items = [];
    }
  }

  let picked = items;
  if (materialMode.value === "custom") {
    const idSet = new Set(selectedMaterialItemIds.value || []);
    picked = items.filter((x) => idSet.has(x.id));
  }

  return picked.map((x) => ({
    item_type: x.item_type,
    text: x.text,
    source_url: x.source_url,
    source_content_id: x.source_content_id,
    source_event_id: x.source_event_id,
    meta: x.meta,
  }));
};

const lastWriteFingerprint = ref<string | null>(null);
const lastWritePackId = ref<number | null>(null);

const _buildWriteFingerprint = (items: MaterialItemCreate[]) => {
  return (items || [])
    .map((x) => `${_norm(x.item_type || "").toLowerCase()}|${_norm(x.text || "")}`)
    .join("\n");
};

const prepareTempPackForGeneration = async (payload: GenerationRequest) => {
  if (basket.selectedCount === 0) return;

  const pack = await _findOrCreateTempPack(form.topic);
  const fromBasket = basket.selectedItems.map((x) => ({
    item_type: x.item_type,
    text: x.text,
    source_url: x.source_url,
    source_content_id: x.source_content_id,
    source_event_id: x.source_event_id,
    meta: x.meta,
  }));
  const fromSelectedPack = await _selectedPackItemsToCreates();
  const merged = _dedupeMaterialCreates([...(fromSelectedPack || []), ...(fromBasket || [])]);

  const fp = _buildWriteFingerprint(merged);
  if (lastWritePackId.value === pack.id && lastWriteFingerprint.value === fp) {
    payload.material_pack_id = pack.id;
    payload.material_item_ids = undefined;
    return;
  }

  await batchCreateMaterialItems(pack.id, { items: merged });
  await loadMaterialPacks();

  lastWritePackId.value = pack.id;
  lastWriteFingerprint.value = fp;

  payload.material_pack_id = pack.id;
  payload.material_item_ids = undefined;

  form.material_pack_id = pack.id;
  form.material_item_ids = undefined;
  materialMode.value = "all";
  selectedMaterialItemIds.value = [];
};

const filteredMaterialItems = computed(() => {
  const kw = (materialKeyword.value || "").trim();
  if (!kw) return materialPackDetailItems.value;
  return materialPackDetailItems.value.filter((it) => (it.text || "").includes(kw));
});
const BUILTIN_TEMPLATE_LABELS = new Map<string, string>([
  ["copywriting.basic.v1", "通用软文｜痛点-方案-证据-步骤-CTA"],
  ["copywriting.story.v1", "故事型软文｜场景故事+反转+干货"],
  ["copywriting.product.v1", "工具/产品软文｜对比测评+上手教程"],
  ["copywriting.hotspot.v1", "热点借势软文｜事件解读+观点+建议"],
]);

const getTemplateDisplayName = (key: string) => {
  const latest = templates.value
    .filter((t) => t.key === key)
    .slice()
    .sort((a, b) => b.version - a.version)[0];
  return (latest?.name || BUILTIN_TEMPLATE_LABELS.get(key) || "未命名模板").trim();
};

const templateOptions = computed(() => {
  const keys = Array.from(new Set<string>(templates.value.map((t) => t.key)))
    .filter((k) => k && k !== "default_article")
    .sort();
  return keys
    .map((key) => ({ key, label: getTemplateDisplayName(key) }))
    .sort((a, b) => (a.label || "").localeCompare(b.label || "") || a.key.localeCompare(b.key));
});
const templateVersions = computed(() => {
  const key = form.template_key;
  if (!key) return [] as number[];
  const versions = templates.value
    .filter((t) => t.key === key)
    .map((t) => t.version);
  return Array.from(new Set(versions)).sort((a, b) => b - a);
});

// 表单模型
const form = reactive<GenerationRequest>({
  topic: "",
  tone: "专业且亲和",
  length: 1000,
  temperature: 0.7,
  provider: "deepseek",
  template_key: "",
  template_version: undefined,
  material_pack_id: undefined,
  material_item_ids: undefined,
});

const lastAutoTopic = ref<string | null>(null);

const _syncTopicFromQuery = (raw: unknown) => {
  const q = typeof raw === "string" ? raw.trim() : "";
  if (!q) {
    if (lastAutoTopic.value && form.topic === lastAutoTopic.value) {
      form.topic = "";
    }
    lastAutoTopic.value = null;
    return;
  }

  if (!form.topic || form.topic === lastAutoTopic.value) {
    form.topic = q;
    lastAutoTopic.value = q;
  }
};

watch(
  () => route.query.topic,
  (val) => {
    _syncTopicFromQuery(val);
  },
  { immediate: true }
);

const currentProviderLabel = computed(() => {
  const key = (form.provider || "").trim();
  return getProviderCn(key) || key || "-";
});

const lengthDisplay = computed(() => {
  const n = Number(form.length);
  if (Number.isNaN(n) || n <= 0) return "-";
  return `${n}+`;
});

const keywordsInput = ref("");
const outlineInput = ref("");
const sourcesInput = ref("");

// 重置表单
const reset = () => {
  form.topic = "";
  form.tone = "专业且亲和";
  form.length = 800;
  form.temperature = 0.7;
  form.max_tokens = undefined;
  form.call_to_action = "";
  form.summary_hint = "";
  form.provider = "deepseek";
  form.template_key = "";
  form.template_version = undefined;
  form.keywords = undefined;
  form.outline = undefined;
  form.sources = undefined;
  form.material_pack_id = undefined;
  form.material_item_ids = undefined;
  keywordsInput.value = "";
  outlineInput.value = "";
  sourcesInput.value = "";
  result.value = null;

  materialPackDetailItems.value = [];
  materialMode.value = "all";
  materialKeyword.value = "";
  selectedMaterialItemIds.value = [];
};

const _formatLocalYmd = (d: Date) => {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
};

const openSmartPickDialog = () => {
  smartTopic.value = (form.topic || "").trim();
  smartDay.value = smartDay.value || _formatLocalYmd(new Date());
  smartInstruction.value = "";
  smartProvider.value = "";
  smartLimit.value = 50;
  smartDecisions.value = [];
  smartDecisionRows.value = [];
  smartRecommendedEventIds.value = [];
  selectedSmartEventIds.value = [];
  basketItems.value = [];
  smartPickVisible.value = true;
};

const runSmartPick = async () => {
  const topic = (smartTopic.value || "").trim();
  if (!topic) {
    ElMessage.warning("请先填写核心主题");
    return;
  }
  const day = (smartDay.value || "").trim();
  if (!day) {
    ElMessage.warning("请先选择日期");
    return;
  }

  smartLoading.value = true;
  try {
    const payload: any = {
      day,
      topic,
      limit: smartLimit.value,
    };
    const inst = (smartInstruction.value || "").trim();
    if (inst) payload.instruction = inst;
    const p = (smartProvider.value || "").trim();
    if (p) payload.provider = p;
    else if (form.provider) payload.provider = form.provider;

    const resp: DailyHotspotListSmartFilterResponse = await smartFilterDailyHotspotList(payload);
    smartDecisions.value = resp.decisions || [];
    smartRecommendedEventIds.value = resp.recommended_event_ids || [];

    // 补齐展示信息：合并榜单返回的 title/hot/source_count
    let metaItems: DailyHotspotEvent[] = [];
    try {
      const listResp = await listDailyHotspots(day, Math.max(20, smartLimit.value));
      metaItems = listResp.items || [];
    } catch {
      metaItems = [];
    }
    const metaMap = new Map<number, DailyHotspotEvent>();
    metaItems.forEach((e) => metaMap.set(Number(e.id), e));

    smartDecisionRows.value = (smartDecisions.value || []).map((d) => {
      const m = metaMap.get(Number(d.event_id));
      return {
        ...d,
        title: m?.title,
        hot_score: m?.hot_score,
        source_count: m?.source_count,
      };
    });

    // 中文说明：将“推荐/匹配”的事件排到前面，便于快速勾选
    smartDecisionRows.value.sort((a: any, b: any) => {
      const ar = a?.recommended ? 1 : 0;
      const br = b?.recommended ? 1 : 0;
      if (ar !== br) return br - ar;
      const as = Number(a?.score ?? 0);
      const bs = Number(b?.score ?? 0);
      if (as !== bs) return bs - as;
      const ah = Number(a?.hot_score ?? 0);
      const bh = Number(b?.hot_score ?? 0);
      if (ah !== bh) return bh - ah;
      return Number(a?.event_id ?? 0) - Number(b?.event_id ?? 0);
    });

    selectedSmartEventIds.value = [...smartRecommendedEventIds.value];

    // 中文说明：默认勾选“推荐”的事件，减少用户操作成本
    await nextTick();
    try {
      smartTableRef.value?.clearSelection?.();
      const recSet = new Set(smartRecommendedEventIds.value || []);
      smartDecisionRows.value.forEach((row: any) => {
        if (recSet.has(Number(row.event_id))) {
          smartTableRef.value?.toggleRowSelection?.(row, true);
        }
      });
    } catch {
      // ignore
    }
  } catch (err: any) {
    ElMessage.error(err.message || "智能筛选失败");
  } finally {
    smartLoading.value = false;
  }
};

const oneClickImportAndWrite = async () => {
  if (!selectedSmartEventIds.value.length) {
    ElMessage.warning("请先勾选热点事件");
    return;
  }
  await buildBasketFromSelected();
  if (!basketItems.value.length) return;
  await writeBasketToTopicPack();
};

const onSmartEventSelectionChange = (rows: Array<{ event_id: number }>) => {
  selectedSmartEventIds.value = (rows || []).map((x) => Number(x.event_id)).filter((n) => !Number.isNaN(n));
};

const _detailToMaterialItems = (detail: DailyHotspotDetailResponse): MaterialItemCreate[] => {
  const eventId = Number(detail.event?.id);
  const eventTitle = detail.event?.title || "";
  const baseMeta = {
    event_id: eventId,
    event_title: eventTitle,
    event_day: detail.event?.day,
    _source: "daily_hotspot",
  };

  const arr: MaterialItemCreate[] = [];
  (detail.bullets || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "bullet",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "bullet" },
    });
  });
  (detail.quotes || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "quote",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "quote" },
    });
  });
  (detail.facts || []).forEach((it: any) => {
    if (!it?.text) return;
    arr.push({
      item_type: "fact",
      text: String(it.text),
      source_url: it.source_url || undefined,
      source_content_id: it.source_content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, hotspot_item_id: it.id, hotspot_item_type: "fact" },
    });
  });
  (detail.sources || []).forEach((s: any) => {
    const url = (s?.url || "").trim();
    if (!url) return;
    const title = (s?.title || "").trim();
    arr.push({
      item_type: "source",
      text: title ? `${title}\n${url}` : url,
      source_url: url,
      source_content_id: s.content_id || undefined,
      source_event_id: eventId,
      meta: { ...baseMeta, weight: s.weight, hotspot_source_id: s.id },
    });
  });

  return arr;
};

const buildBasketFromSelected = async () => {
  const ids = selectedSmartEventIds.value;
  if (!ids.length) {
    ElMessage.warning("请先勾选热点事件");
    return;
  }
  basketLoading.value = true;
  try {
    const all: MaterialItemCreate[] = [];
    for (const eid of ids) {
      const detail = await getDailyHotspotDetail(eid);
      all.push(..._detailToMaterialItems(detail));
    }
    basketItems.value = all;
    ElMessage.success(`已导入素材：${all.length} 条`);
  } catch (err: any) {
    ElMessage.error(err.message || "导入素材失败");
  } finally {
    basketLoading.value = false;
  }
};

const _pickOrCreateTopicPack = async (topic: string): Promise<MaterialPack> => {
  const name = topic.trim();
  const resp = await listMaterialPacks({ keyword: name, limit: 50, offset: 0 });
  const existed = (resp.items || []).find((p) => (p.name || "").trim() === name);
  if (existed) return existed;
  return await createMaterialPack({ name, description: `智能选取素材：${smartDay.value || ""}` });
};

const writeBasketToTopicPack = async () => {
  const topic = (smartTopic.value || form.topic || "").trim();
  if (!topic) {
    ElMessage.warning("请先填写核心主题");
    return;
  }
  if (!basketItems.value.length) {
    ElMessage.warning("未导入到任何素材，请先一键导入");
    return;
  }

  const selected = basketItems.value;

  writePackLoading.value = true;
  try {
    const pack = await _pickOrCreateTopicPack(topic);
    await batchCreateMaterialItems(pack.id, { items: selected });
    await loadMaterialPacks();
    form.material_pack_id = pack.id;
    smartPickVisible.value = false;
    ElMessage.success(`已写入素材包「${pack.name}」：${selected.length} 条`);
  } catch (err: any) {
    ElMessage.error(err.message || "写入素材包失败");
  } finally {
    writePackLoading.value = false;
  }
};

const loadMaterialPacks = async () => {
  try {
    const resp = await listMaterialPacks({ limit: 200, offset: 0 });
    materialPacks.value = resp.items || [];
  } catch (err: any) {
    // 不阻塞生成主流程
  }
};

const onTemplateKeyChange = () => {
  form.template_version = undefined;
};

const loadTemplates = async () => {
  try {
    templates.value = await listPromptTemplates();
  } catch (err: any) {
    ElMessage.error(err.message || "加载模板失败");
  }
};

const selectAllMaterialItems = () => {
  selectedMaterialItemIds.value = materialPackDetailItems.value.map((x) => x.id);
};

const clearMaterialItemSelection = () => {
  selectedMaterialItemIds.value = [];
};

watch(
  () => form.material_pack_id,
  async (pid) => {
    // 切换素材包时：默认使用全量
    form.material_item_ids = undefined;
    materialMode.value = "all";
    materialKeyword.value = "";
    selectedMaterialItemIds.value = [];
    materialPackDetailItems.value = [];

    if (!pid) return;

    materialDetailLoading.value = true;
    try {
      const resp = await getMaterialPackDetail(pid);
      materialPackDetailItems.value = resp.items || [];
    } catch (err: any) {
      // 不阻塞生成主流程
    } finally {
      materialDetailLoading.value = false;
    }
  }
);

watch(
  materialMode,
  (m) => {
    if (m === "all") {
      form.material_item_ids = undefined;
      selectedMaterialItemIds.value = [];
      return;
    }
    // 切到自选：默认全选，用户再手动删减
    if (selectedMaterialItemIds.value.length === 0) {
      selectAllMaterialItems();
    }
    form.material_item_ids = [...selectedMaterialItemIds.value];
  },
  { immediate: true }
);

watch(
  selectedMaterialItemIds,
  (ids) => {
    if (materialMode.value !== "custom") return;
    form.material_item_ids = ids.length ? [...ids] : [];
  },
  { deep: true }
);

onMounted(() => {
  loadTemplates();
  loadMaterialPacks();
});

// 处理生成
const onGenerate = async () => {
  if (!form.topic) {
    ElMessage.warning("请填写主题/标题");
    return;
  }

  if (form.material_pack_id && materialMode.value === "custom" && selectedMaterialItemIds.value.length === 0) {
    ElMessage.warning("你选择了素材包“自选条目”，但未勾选任何条目");
    return;
  }
  form.keywords = keywordsInput.value
    ? keywordsInput.value.split(",").map((k) => k.trim()).filter(Boolean)
    : undefined;
  form.outline = outlineInput.value
    ? outlineInput.value.split("\n").map((k) => k.trim()).filter(Boolean)
    : undefined;
  form.sources = sourcesInput.value
    ? sourcesInput.value
        .split(",")
        .map((id) => Number(id.trim()))
        .filter((n) => !Number.isNaN(n))
        .filter(Boolean) // 修正: 过滤掉 0 或转换失败的
    : undefined;
  loading.value = true;
  try {
    const payload: GenerationRequest = { ...form };
    if (!payload.template_key) {
      payload.template_key = undefined;
      payload.template_version = undefined;
    }

    await prepareTempPackForGeneration(payload);

    const data = await generateArticle(payload);
    result.value = data;
    ElMessage.success("生成成功");
  } catch (err: any) {
    ElMessage.error(err.message || "生成失败");
  } finally {
    loading.value = false;
  }
};

// 复制 Markdown/HTML
const copyText = async (text: string) => {
  if (!text) return;
  await navigator.clipboard.writeText(text);
  ElMessage.success("已复制");
};
const copyHtml = async (html: string) => {
  if (!html) return;
  const listener = (e: ClipboardEvent) => {
    e.preventDefault();
    if (e.clipboardData) {
      e.clipboardData.setData("text/html", html);
      e.clipboardData.setData("text/plain", html);
    }
  };
  document.addEventListener("copy", listener);
  document.execCommand("copy");
  document.removeEventListener("copy", listener);
  ElMessage.success("已复制 HTML");
};

const goArticleDetail = () => {
  const id = result.value?.id;
  if (!id) return;
  router.push(`/articles/${id}`);
};
</script>

<style scoped>
.page-container {
  min-height: 100vh;
  background: #f8fafc;
  overflow-x: hidden;
  overflow-y: auto;
}

.notebooklm-layout {
  display: flex;
  align-items: flex-start;
  background: #f8fafc;
  min-height: 100vh;
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-tip {
  flex: 1;
  border: none !important;
  background-color: #f1f5f9 !important;
  padding: 8px 16px;
}

.page-tip :deep(.el-alert__title) {
  font-size: 13px;
  color: #64748b;
}

.stat-group {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-item .label {
  font-size: 10px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-item .value {
  font-weight: 700;
  font-size: 14px;
  color: #1e293b;
}

.form-card, .result-card {
  margin-bottom: 20px;
  background: #fff;
  border: 1px solid #eef2f6;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.smart-tip {
  margin-bottom: 20px;
  border: none !important;
  background-color: #f0f9ff !important;
}

.smart-tip :deep(.el-alert__title) {
  color: #0369a1;
  font-size: 13px;
}

.smart-table {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #f1f5f9;
}

.smart-table :deep(.el-table__header) th {
  background-color: #f8fafc;
  color: #64748b;
  font-weight: 600;
}

.smart-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.dialog-footer {
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
}

.form-card :deep(.el-card__header), 
.result-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header .title {
  font-weight: 600;
  font-size: 15px;
  color: #1e293b;
}

.topic-input :deep(.el-input__wrapper) {
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  padding: 4px 12px;
}

.advanced-panel {
  margin-top: 20px;
}

.advanced-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background-color: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
  transition: all 0.2s;
}

.advanced-header:hover {
  background-color: #f1f5f9;
}

.advanced-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
}

.advanced-chevron {
  color: #94a3b8;
  font-size: 18px;
  transition: transform 0.2s;
}

.advanced-chevron.open {
  transform: rotate(90deg);
}

.advanced-body {
  padding: 16px 4px 0;
}

.advanced-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}

.advanced-grid.grid-2 {
  grid-template-columns: repeat(2, 1fr);
}

.advanced-grid.grid-3 {
  grid-template-columns: repeat(3, 1fr);
}

.preview-content {
  padding: 16px;
  background: #fff;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  max-height: 500px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.code-block {
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  overflow-x: auto;
  white-space: pre-wrap;
  margin: 0;
  max-height: 400px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.result-meta {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meta-item .label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
  display: block;
}

.meta-item p {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
}

.summary-text {
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta-tags {
  display: flex;
  gap: 8px;
}

.result-tabs {
  margin-top: 16px;
}

.result-tabs :deep(.el-tabs__content) {
  padding: 12px 0 0;
}

.form-footer {
  margin-top: 24px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.material-pack-row {
  display: flex;
  gap: 12px;
  width: 100%;
}

.material-pack-select {
  flex: 1;
}

.material-picker {
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  padding: 12px;
  background: #fcfdfe;
}

.material-picker-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.material-item-row {
  padding: 8px 4px;
  border-bottom: 1px solid #f1f5f9;
}

.mi-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}

.mi-id {
  color: #94a3b8;
  font-size: 11px;
}

.mi-text {
  font-size: 13px;
  color: #475569;
}

.material-picker-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  font-size: 12px;
}

.mi-count {
  color: #94a3b8;
}

/* 写作助手卡片样式优化 */
.tips-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.tips-card :deep(.el-card__header) {
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.tips-card .card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tips-card .header-icon {
  color: #3b82f6;
  font-size: 18px;
}

.tips-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.tip-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 8px;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.tip-item:hover {
  background: #fff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}

.tip-icon-wrapper {
  width: 36px;
  height: 36px;
  background: #fff;
  border: 1px solid #eef2f6;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: all 0.2s ease;
}

.tip-item:hover .tip-icon-wrapper {
  border-color: #3b82f6;
  background: #eff6ff;
}

.tip-content {
  flex: 1;
}

.tip-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 2px;
}

.tip-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
}

.mt-4 {
  margin-top: 16px;
}
</style>
