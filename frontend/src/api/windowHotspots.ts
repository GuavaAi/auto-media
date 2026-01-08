import http from "./http";

import type {
  WindowHotspotBuildRequest,
  WindowHotspotListResponse,
  WindowHotspotListSmartFilterRequest,
  WindowHotspotListSmartFilterResponse,
} from "@/types";

export const buildWindowHotspots = (payload: WindowHotspotBuildRequest) =>
  http.post<WindowHotspotListResponse>("/window-hotspots/build", payload).then((r) => r.data);

export const smartFilterWindowHotspotList = (payload: WindowHotspotListSmartFilterRequest) =>
  http.post<WindowHotspotListSmartFilterResponse>("/window-hotspots/smart-filter", payload).then((r) => r.data);
