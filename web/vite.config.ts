import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 4173 },
  preview: { port: 4174 },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          echarts: ["echarts", "echarts-for-react"],
          icons: ["lucide-react"],
        },
      },
    },
  },
});
