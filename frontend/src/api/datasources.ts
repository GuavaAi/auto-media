import http from "./http";
import type { DataSource } from "@/types";

export interface CreateDataSourcePayload {
  name: string;
  source_type: string;
  config?: Record<string, unknown> | null;
  biz_category?: string | null;
  schedule_cron?: string | null;
  enable_schedule?: boolean;
}

export interface UpdateDataSourcePayload extends Partial<CreateDataSourcePayload> {}

export const listDataSources = () =>
  http.get<DataSource[]>("/datasources").then((r) => r.data);

export const createDataSource = (payload: CreateDataSourcePayload) =>
  http.post<DataSource>("/datasources", payload).then((r) => r.data);

export const updateDataSource = (id: number, payload: UpdateDataSourcePayload) =>
  http.put<DataSource>(`/datasources/${id}`, payload).then((r) => r.data);

export const deleteDataSource = (id: number) =>
  http.delete(`/datasources/${id}`).then((r) => r.data);

export const triggerDataSource = (id: number, force: boolean = false) =>
  http.post<DataSource>(`/datasources/${id}/trigger`, null, { params: { force } }).then((r) => r.data);
