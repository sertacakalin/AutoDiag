import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite yapılandırması. CSS Modules yerleşik olarak desteklenir.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
});
