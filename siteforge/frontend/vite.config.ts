import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: {
    proxy: {
      "/command-api": { target: "http://localhost:8001", changeOrigin: true, rewrite: (path) => path.replace(/^\/command-api/, "/api") },
      "/api": { target: "http://localhost:8000", changeOrigin: false },
      "/health": "http://localhost:8000",
    },
  },
});
