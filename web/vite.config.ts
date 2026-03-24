import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  /** 开发时转发到 FastAPI；默认 8001，可在 web/.env 中设置 VITE_PROXY_TARGET */
  const proxyTarget =
    env.VITE_PROXY_TARGET || "http://127.0.0.1:8001";

  return {
    plugins: [react()],
    resolve: {
      dedupe: ["react", "react-dom"],
    },
    optimizeDeps: {
      include: ["react", "react-dom", "react-router-dom", "echarts"],
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
