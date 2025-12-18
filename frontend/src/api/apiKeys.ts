import http from "./http";
import type {
  ApiKeyCreate,
  ApiKeyListResponse,
  ApiKeyOut,
  ApiKeyUpdate,
} from "@/types";

export const listApiKeys = (params?: { provider?: string }) =>
  http.get<ApiKeyListResponse>("/api-keys", { params }).then((r) => r.data);

export const createApiKey = (payload: ApiKeyCreate) =>
  http.post<ApiKeyOut>("/api-keys", payload).then((r) => r.data);

export const updateApiKey = (id: number, payload: ApiKeyUpdate) =>
  http.patch<ApiKeyOut>(`/api-keys/${id}`, payload).then((r) => r.data);

export const deleteApiKey = (id: number) =>
  http.delete<{ ok: boolean }>(`/api-keys/${id}`).then((r) => r.data);
