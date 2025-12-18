import http from "./http";
import type {
  DailyHotspotDetailResponse,
  DailyHotspotListResponse,
  DailyHotspotListSmartFilterRequest,
  DailyHotspotListSmartFilterResponse,
  DailyHotspotSmartFilterRequest,
  DailyHotspotSmartFilterResponse,
} from "@/types";

export const buildDailyHotspots = (day: string, limit: number = 20) =>
  http
    .post<DailyHotspotListResponse>("/daily-hotspots/build", null, {
      params: { day, limit },
    })
    .then((r) => r.data);

export const listDailyHotspots = (day: string, limit: number = 20) =>
  http
    .get<DailyHotspotListResponse>("/daily-hotspots/", {
      params: { day, limit },
    })
    .then((r) => r.data);

export const getDailyHotspotDetail = (eventId: number) =>
  http.get<DailyHotspotDetailResponse>(`/daily-hotspots/${eventId}`).then((r) => r.data);

export const smartFilterDailyHotspot = (eventId: number, payload: DailyHotspotSmartFilterRequest) =>
  http
    .post<DailyHotspotSmartFilterResponse>(`/daily-hotspots/${eventId}/smart-filter`, payload)
    .then((r) => r.data);

export const smartFilterDailyHotspotList = (payload: DailyHotspotListSmartFilterRequest) =>
  http.post<DailyHotspotListSmartFilterResponse>(`/daily-hotspots/smart-filter`, payload).then((r) => r.data);

// One-Click Draft (Quick Generate)
export const quickGenerateFromEvent = (eventId: number) =>
  http.post<any>(`/quick-generate/from-event/${eventId}`).then((r) => r.data);

// Active Inspiration (Topic Search Generate)
export const quickGenerateFromTopic = (topic: string) =>
  http.post<any>(`/quick-generate/from-topic`, { topic }).then((r) => r.data);
