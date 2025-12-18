import http from "./http";
import type { CrawlRecordDetail, CrawlRecordListResponse, MaterialItemCreate } from "@/types";

export interface CrawlRecordListParams {
  datasource_id?: number;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export const listCrawlRecords = (params: CrawlRecordListParams) =>
  http.get<CrawlRecordListResponse>("/crawl-records", { params }).then((r) => r.data);

export const getCrawlRecord = (id: number) =>
  http.get<CrawlRecordDetail>(`/crawl-records/${id}`).then((r) => r.data);

export interface CrawlRecordQuickFetchRequest {
  url: string;
  crawler_engine?: string;
  timeout?: number;
  use_playwright?: boolean;
  css_selector?: string;
}

export const quickFetchCrawlRecord = (payload: CrawlRecordQuickFetchRequest) =>
  http.post(`/crawl-records/quick-fetch`, payload).then((r) => r.data);

export const quickFetchCrawlRecordPreview = (payload: CrawlRecordQuickFetchRequest) =>
  http.post(`/crawl-records/quick-fetch/preview`, payload).then((r) => r.data);

export interface CrawlRecordExtractMaterialsRequest {
  top_k?: number;
  include_source?: boolean;
}

export interface CrawlRecordExtractMaterialsResponse {
  items: MaterialItemCreate[];
}

export const extractCrawlRecordMaterials = (id: number, payload?: CrawlRecordExtractMaterialsRequest) =>
  http
    .post<CrawlRecordExtractMaterialsResponse>(`/crawl-records/${id}/materials:extract`, payload || {})
    .then((r) => r.data);
