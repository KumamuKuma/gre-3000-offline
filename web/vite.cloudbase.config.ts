import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: "cloudbase",
  publicDir: "../public",
  plugins: [react()],
  build: {
    emptyOutDir: true,
    outDir: "../cloudbase-dist",
  },
});
