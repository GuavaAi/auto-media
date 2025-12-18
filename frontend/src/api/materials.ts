import http from "./http";
import type {
  AliyunUnifiedSearchIngestRequest,
  AliyunUnifiedSearchIngestResponse,
  DedupeResponse,
  FirecrawlSearchIngestRequest,
  FirecrawlSearchIngestResponse,
  MaterialItem,
  MaterialItemBatchCreateRequest,
  MaterialItemSearchResponse,
  MaterialItemUpdate,
  MaterialPack,
  MaterialPackCreate,
  MaterialPackDetailResponse,
  MaterialPackListResponse,
} from "@/types";

export const createMaterialPack = (payload: MaterialPackCreate) =>
  http.post<MaterialPack>("/materials/packs", payload).then((r) => r.data);

export const listMaterialPacks = (params?: {
  keyword?: string;
  limit?: number;
  offset?: number;
}) =>
  http
    .get<MaterialPackListResponse>("/materials/packs", { params })
    .then((r) => r.data);

export const getMaterialPackDetail = (packId: number) =>
  http
    .get<MaterialPackDetailResponse>(`/materials/packs/${packId}`)
    .then((r) => r.data);

export const deleteMaterialPack = (packId: number) =>
  http.delete<{ ok: boolean }>(`/materials/packs/${packId}`).then((r) => r.data);

export const batchCreateMaterialItems = (packId: number, payload: MaterialItemBatchCreateRequest) =>
  http
    .post<MaterialItem[]>(`/materials/packs/${packId}/items:batchCreate`, payload)
    .then((r) => r.data);

export const updateMaterialItem = (itemId: number, payload: MaterialItemUpdate) =>
  http.patch<MaterialItem>(`/materials/items/${itemId}`, payload).then((r) => r.data);

export const deleteMaterialItem = (itemId: number) =>
  http.delete<{ ok: boolean }>(`/materials/items/${itemId}`).then((r) => r.data);

export const searchMaterialItems = (params?: {
  keyword?: string;
  pack_id?: number;
  item_type?: string;
  limit?: number;
  offset?: number;
}) =>
  http
    .get<MaterialItemSearchResponse>("/materials/items/search", { params })
    .then((r) => r.data);

export const dedupeMaterialPack = (packId: number) =>
  http.post<DedupeResponse>(`/materials/packs/${packId}/dedupe`).then((r) => r.data);

export const firecrawlSearchIngest = (payload: FirecrawlSearchIngestRequest) =>
  http
    .post<FirecrawlSearchIngestResponse>("/materials/firecrawl-search:ingest", payload)
    .then((r) => r.data);

export const aliyunUnifiedSearchIngest = (payload: AliyunUnifiedSearchIngestRequest) =>
  http
    .post<AliyunUnifiedSearchIngestResponse>("/materials/aliyun-unified-search:ingest", payload)
    .then((r) => r.data);
