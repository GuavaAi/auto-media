import axios from "axios";

import { clearToken, getToken } from "@/utils/token";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:8010/api",
  timeout: 300000,
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      clearToken();
      // 中文说明：此处不要直接 import router，否则容易形成循环依赖（router -> store -> api -> http -> router）
      // 直接使用 location 进行跳转，确保 401 能稳定回到登录页
      const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(current)}`;
      }
    }
    const msg = error?.response?.data?.detail || error.message || "请求失败";
    return Promise.reject(new Error(msg));
  }
);

export default http;
