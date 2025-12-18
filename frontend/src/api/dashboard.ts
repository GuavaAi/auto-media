import http from "./http";

export interface DashboardStats {
  total_articles: number;
  today_articles: number;
  total_crawl: number;
  today_crawl: number;
  total_datasources: number;
}

export interface RecentArticle {
  id: number;
  title: string;
  summary?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  elapsed_ms?: number | null;
  created_at: string;
}

export interface RecentCrawlRecord {
  id: number;
  datasource_id: number;
  datasource_name?: string | null;
  title?: string | null;
  url?: string | null;
  fetched_at: string;
  extra?: Record<string, unknown> | null;
}

export interface DashboardRecentResponse {
  recent_articles: RecentArticle[];
  recent_crawl_records: RecentCrawlRecord[];
}

export const getDashboardStats = () => {
  return http.get<DashboardStats>("/dashboard/stats").then((r) => r.data);
};

export const getDashboardRecent = (limit = 5) => {
  return http
    .get<DashboardRecentResponse>("/dashboard/recent", { params: { limit } })
    .then((r) => r.data);
};
