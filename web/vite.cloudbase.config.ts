import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const cloudbaseOrigin = "https://kuma-d9gnt6m3d6b8050f8-1472025206.ap-shanghai.app.tcloudbase.com";

export default defineConfig(({ mode }) => {
  const githubPages = mode === "github-pages";
  const apiOrigin = githubPages ? process.env.GRE_GITHUB_PAGES_API_ORIGIN : cloudbaseOrigin;
  const api = apiOrigin ? new URL(apiOrigin) : null;
  if (!api || api.protocol !== "https:" || ![api.origin, `${api.origin}/`].includes(apiOrigin ?? "")) {
    throw new Error("Set GRE_GITHUB_PAGES_API_ORIGIN to the HTTPS origin of the sync worker.");
  }
  return {
    root: "cloudbase",
    base: githubPages ? "/gre-3000-offline/" : "/",
    publicDir: "../public",
    plugins: [react()],
    define: {
      "import.meta.env.GRE_SYNC_API_ORIGIN": JSON.stringify(api.origin),
      "import.meta.env.GRE_ACCOUNT_SYNC": JSON.stringify(githubPages ? "on" : "off"),
    },
    build: {
      emptyOutDir: true,
      outDir: githubPages ? "../github-pages-dist" : "../cloudbase-dist",
    },
  };
});
