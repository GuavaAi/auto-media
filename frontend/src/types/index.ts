export interface DataSource {
  id: number;
  name: string;
  source_type: string;
  config: Record<string, unknown> | null;
  biz_category?: string | null;
  schedule_cron?: string | null;
  enable_schedule: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
}

export interface ArticleUpdate {
  title?: string | null;
  summary?: string | null;
  content_md?: string | null;
  content_html?: string | null;
}

export interface DeleteResponse {
  ok: boolean;
}

export interface ArticleAiEditRequest {
  action: "rewrite" | "continue" | "translate";
  selected_text?: string;
  provider?: string;
  temperature?: number;
  max_tokens?: number;
  length?: number;
  instruction?: string;
  target_language?: string;
}

export interface ArticleAiEditResponse {
  content_md: string;
  content_html: string;
  prompt_text?: string | null;
}

export interface GenerationRequest {
  topic: string;
  outline?: string[];
  keywords?: string[];
  tone?: string;
  length?: number;
  temperature?: number;
  max_tokens?: number;
  call_to_action?: string;
  sources?: number[];
  summary_hint?: string;
  provider?: string;
  template_key?: string;
  template_version?: number;

  // 可选：注入素材包内容（后端会将素材条目拼装进 Prompt）
  material_pack_id?: number;
  material_item_ids?: number[];
}

export interface Article {
  id: number;
  title: string;
  summary?: string | null;
  content_md: string;
  content_html: string;
  source_refs?: number[] | null;
  request_payload?: Record<string, any> | null;
  prompt_text?: string | null;
  material_pack_id?: number | null;
  material_refs?: Record<string, any> | null;
  template_key?: string | null;
  template_version?: number | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  elapsed_ms?: number | null;
  usage?: Record<string, any> | null;
  created_at: string;
}

export interface PromptTemplate {
  id: number;
  name?: string | null;
  key: string;
  version: number;
  content: string;
  created_at: string;
}

export interface PromptTemplateListResponse {
  items: PromptTemplate[];
}

export interface MaterialPack {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface MaterialPackCreate {
  name: string;
  description?: string | null;
}

export interface MaterialItem {
  id: number;
  pack_id: number;
  item_type: string;
  text: string;
  text_hash: string;
  source_url?: string | null;
  source_content_id?: number | null;
  source_event_id?: number | null;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

export interface MaterialItemCreate {
  item_type: string;
  text: string;
  source_url?: string | null;
  source_content_id?: number | null;
  source_event_id?: number | null;
  meta?: Record<string, unknown> | null;
}

export interface FirecrawlSearchIngestRequest {
  query: string;
  limit?: number;
  tbs?: string;
  sources?: string[];
  api_key?: string;
  api_base?: string;
}

export interface FirecrawlSearchIngestResponse {
  ingested: number;
  skipped: number;
  items: MaterialItemCreate[];
}

export interface AliyunUnifiedSearchIngestRequest {
  query: string;
  engine_type?: string;
  time_range?: string;
  category?: string | null;
  location?: string | null;
  include_main_text?: boolean;
  advanced_params?: Record<string, string> | null;
}

export interface AliyunUnifiedSearchIngestResponse {
  ingested: number;
  skipped: number;
  items: MaterialItemCreate[];
}

export interface ApiKeyCreate {
  provider: string;
  name?: string | null;
  key: string;
  is_active: boolean;
  extra?: Record<string, any> | null;
}

export interface ApiKeyUpdate {
  name?: string | null;
  key?: string | null;
  is_active?: boolean;
  extra?: Record<string, any> | null;
}

export interface ApiKeyOut {
  id: number;
  provider: string;
  name?: string | null;
  is_active: boolean;
  last_used_at?: string | null;
  use_count: number;
  created_at: string;
  updated_at: string;
  key_masked: string;
  extra?: Record<string, any> | null;
}

export interface ApiKeyListResponse {
  total: number;
  items: ApiKeyOut[];
}

export interface MaterialItemUpdate {
  item_type?: string;
  text?: string;
  source_url?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface MaterialPackListResponse {
  total: number;
  limit: number;
  offset: number;
  items: MaterialPack[];
}

export interface MaterialPackDetailResponse {
  pack: MaterialPack;
  items: MaterialItem[];
}

export interface MaterialItemBatchCreateRequest {
  items: MaterialItemCreate[];
}

export interface MaterialItemSearchResponse {
  total: number;
  limit: number;
  offset: number;
  items: MaterialItem[];
}

export interface DedupeResponse {
  removed: number;
}

export interface CrawlRecord {
  id: number;
  datasource_id: number;
  datasource_name?: string | null;
  source_type: string;
  title?: string | null;
  url?: string | null;
  content_preview?: string | null;
  extra?: Record<string, unknown> | null;
  fetched_at: string;
}

export interface CrawlRecordDetail extends CrawlRecord {
  content: string;
}

export interface CrawlRecordListResponse {
  total: number;
  limit: number;
  offset: number;
  items: CrawlRecord[];
}

export interface DailyHotspotEvent {
  id: number;
  day: string;
  title: string;
  summary?: string | null;
  hot_score: number;
  keywords?: string[] | null;
  source_count: number;
  created_at: string;
}

export interface DailyHotspotItem {
  id: number;
  type: string;
  text: string;
  source_url?: string | null;
  source_content_id?: number | null;
  position: number;
  score: number;
  extra?: Record<string, unknown> | null;
}

export interface DailyHotspotSource {
  id: number;
  content_id?: number | null;
  url?: string | null;
  title?: string | null;
  weight: number;
}

export interface DailyHotspotListResponse {
  day: string;
  items: DailyHotspotEvent[];
}

export interface DailyHotspotDetailResponse {
  event: DailyHotspotEvent;
  bullets: DailyHotspotItem[];
  quotes: DailyHotspotItem[];
  facts: DailyHotspotItem[];
  sources: DailyHotspotSource[];
}

export interface DailyHotspotSmartFilterRequest {
  provider?: string;
  instruction?: string;
  include_types?: string[];
  max_items?: number;
  temperature?: number;
}

export interface DailyHotspotSmartFilterDecision {
  id: number;
  type: string;
  recommended: boolean;
  score: number;
  reason?: string | null;
}

export interface DailyHotspotSmartFilterResponse {
  event_id: number;
  recommended_item_ids: number[];
  decisions: DailyHotspotSmartFilterDecision[];
}

export interface DailyHotspotListSmartFilterRequest {
  day: string;
  topic: string;
  provider?: string;
  instruction?: string;
  limit?: number;
  temperature?: number;
}

export interface DailyHotspotListSmartFilterDecision {
  event_id: number;
  recommended: boolean;
  score: number;
  reason?: string | null;
}

export interface DailyHotspotListSmartFilterResponse {
  day: string;
  topic: string;
  recommended_event_ids: number[];
  decisions: DailyHotspotListSmartFilterDecision[];
}

export interface PublishAccount {
  id: number;
  name: string;
  provider: string;
  is_active: boolean;
  config?: Record<string, any> | null;
  created_at: string;
}

export interface PublishAccountCreate {
  name: string;
  provider: string;
  config: Record<string, any>;
}

export interface PublishTaskCreateDraftRequest {
  account_id: number;
  article_id: number;
  thumb_image_url: string;
  author?: string;
  digest?: string;
  content_source_url?: string;
}

export interface PublishTask {
  id: number;
  provider: string;
  action: string;
  account_id: number;
  article_id?: number | null;
  status: string;
  attempts: number;
  max_attempts: number;
  celery_task_id?: string | null;
  next_retry_at?: string | null;
  dlq: boolean;
  request?: Record<string, any> | null;
  response?: Record<string, any> | null;
  remote_id?: string | null;
  remote_url?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserInfo {
  id: number;
  username: string;
  full_name?: string | null;
  email?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  total: number;
  items: UserInfo[];
}

export interface UserCreate {
  username: string;
  password: string;
  full_name?: string | null;
  email?: string | null;
  role?: string;
  is_active?: boolean;
}

export interface UserUpdate {
  full_name?: string | null;
  email?: string | null;
  role?: string;
  is_active?: boolean;
  password?: string | null;
}

export interface AuthLoginRequest {
  username: string;
  password: string;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
  menus?: string[];
}

export interface AuthProfileResponse {
  user: UserInfo;
  menus?: string[];
}

export interface RoleOut {
  id: number;
  key: string;
  name: string;
  menus: string[];
  created_at: string;
  updated_at: string;
}

export interface RoleListResponse {
  total: number;
  items: RoleOut[];
}

export interface RoleCreate {
  key: string;
  name: string;
  menus: string[];
}

export interface RoleUpdate {
  name?: string;
  menus?: string[];
}
