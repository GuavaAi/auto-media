import http from "./http";
import type { UserCreate, UserListResponse, UserInfo, UserUpdate } from "@/types";

export const listUsers = () =>
  http.get<UserListResponse>("/users").then((resp) => resp.data);

export const createUser = (payload: UserCreate) =>
  http.post<UserInfo>("/users", payload).then((resp) => resp.data);

export const updateUser = (id: number, payload: UserUpdate) =>
  http.patch<UserInfo>(`/users/${id}`, payload).then((resp) => resp.data);
