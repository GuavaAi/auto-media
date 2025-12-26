import { defineStore } from "pinia";
import type { AuthLoginRequest, UserInfo } from "@/types";
import { fetchProfile, login as loginApi } from "@/api/auth";
import { clearToken, getToken, setToken } from "@/utils/token";

interface AuthState {
  user: UserInfo | null;
  loadingProfile: boolean;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    loadingProfile: false,
  }),
  getters: {
    isAdmin: (state) => (state.user?.role || "").toLowerCase() === "admin",
    displayName: (state) => state.user?.full_name || state.user?.username || "",
  },
  actions: {
    async login(payload: AuthLoginRequest) {
      const resp = await loginApi(payload);
      setToken(resp.access_token);
      this.user = resp.user;
      return resp.user;
    },
    async loadProfile(force = false) {
      const token = getToken();
      if (!token) {
        this.user = null;
        return null;
      }
      if (this.user && !force) {
        return this.user;
      }
      if (this.loadingProfile) {
        return this.user;
      }
      this.loadingProfile = true;
      try {
        const resp = await fetchProfile();
        this.user = resp.user;
        return this.user;
      } catch (error) {
        clearToken();
        this.user = null;
        throw error;
      } finally {
        this.loadingProfile = false;
      }
    },
    logout() {
      clearToken();
      this.user = null;
    },
  },
});
