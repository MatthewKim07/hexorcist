import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";

// The two faces most of the page is set in. Their built names are hashed, so the preload links are added after bundling.
const PRELOAD = /geist-sans-latin-(400|500)-normal-[\w-]+\.woff2$/;

function preloadFonts(): Plugin {
  return {
    name: "preload-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        return Object.keys(ctx.bundle ?? {})
          .filter((file) => PRELOAD.test(file))
          .sort()
          .map((file) => ({ tag: "link", attrs: { rel: "preload", href: `/${file}`, as: "font", type: "font/woff2", crossorigin: "" }, injectTo: "head" as const }));
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), preloadFonts()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: { chunkSizeWarningLimit: 1500 },
});
