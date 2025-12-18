export const PROVIDER_CN_MAP: Record<string, string> = {
  firecrawl: "Firecrawl",
  crawl4ai: "Crawl4AI",
  aliyun_iqs: "阿里统一搜索",
  oss: "对象存储（OSS）",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  azure_openai: "Azure OpenAI",
  ali: "通义千问",
  dashscope: "通义千问",
  tongyi: "通义千问",
  qwen: "通义千问",
  moonshot: "Moonshot",
  kimi: "Kimi",
  baidu: "文心一言",
  wenxin: "文心一言",
};

export const getProviderCn = (p: string) => {
  const key = (p || "").trim().toLowerCase();
  return PROVIDER_CN_MAP[key] || "";
};

export const PROVIDER_URL_MAP: Record<string, string> = {
  firecrawl: "https://www.firecrawl.dev/",
  crawl4ai: "https://github.com/unclecode/crawl4ai",
  aliyun_iqs: "https://ipaas.console.aliyun.com/",
  oss: "https://oss.console.aliyun.com/",
  openai: "https://platform.openai.com/api-keys",
  deepseek: "https://platform.deepseek.com/api_keys",
  azure_openai: "https://portal.azure.com/",
  ali: "https://dashscope.console.aliyun.com/apiKey",
  dashscope: "https://dashscope.console.aliyun.com/apiKey",
  tongyi: "https://dashscope.console.aliyun.com/apiKey",
  qwen: "https://dashscope.console.aliyun.com/apiKey",
  moonshot: "https://platform.moonshot.cn/console/api-keys",
  kimi: "https://platform.moonshot.cn/console/api-keys",
  baidu: "https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application",
  wenxin: "https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application",
};

export const getProviderUrl = (p: string) => {
  const key = (p || "").trim().toLowerCase();
  return PROVIDER_URL_MAP[key] || "";
};

export const MODEL_PROVIDER_OPTIONS = [
  "deepseek",
  "openai",
  "ali",
  "moonshot",
  "kimi",
  "azure_openai",
  "baidu",
] as const;

export const API_KEY_PROVIDER_OPTIONS = [
  "firecrawl",
  "crawl4ai",
  "aliyun_iqs",
  "oss",
  "openai",
  "deepseek",
  "azure_openai",
  "ali",
  "moonshot",
  "kimi",
  "baidu",
] as const;
