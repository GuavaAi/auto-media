import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

// Vite 基础配置，支持 @ 别名
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
