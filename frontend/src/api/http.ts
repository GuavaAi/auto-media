import axios from "axios";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:8010/api",
  timeout: 300000,
});

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error?.response?.data?.detail || error.message || "请求失败";
    return Promise.reject(new Error(msg));
  }
);

export default http;
