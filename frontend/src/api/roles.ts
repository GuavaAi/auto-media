import http from "@/api/http";
import type { RoleCreate, RoleListResponse, RoleOut, RoleUpdate } from "@/types";

export async function fetchRoles(): Promise<RoleListResponse> {
  const { data } = await http.get("/roles/");
  return data;
}

export async function createRole(payload: RoleCreate): Promise<RoleOut> {
  const { data } = await http.post("/roles/", payload);
  return data;
}

export async function updateRole(roleId: number, payload: RoleUpdate): Promise<RoleOut> {
  const { data } = await http.patch(`/roles/${roleId}`, payload);
  return data;
}

export async function deleteRole(roleId: number): Promise<{ ok: boolean }> {
  const { data } = await http.delete(`/roles/${roleId}`);
  return data;
}
