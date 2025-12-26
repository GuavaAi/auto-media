import http from "./http";
import type { AuthLoginRequest, AuthLoginResponse, AuthProfileResponse } from "@/types";

export const login = (payload: AuthLoginRequest) =>
  http.post<AuthLoginResponse>("/auth/login", payload).then((r) => r.data);

export const fetchProfile = () =>
  http.get<AuthProfileResponse>("/auth/profile").then((r) => r.data);
