import { copyFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/** GitHub Pages: 404.html = index.html, para as rotas do React funcionarem em qualquer URL. */
function spaFallback(): Plugin {
  return {
    name: "spa-fallback-404",
    apply: "build",
    closeBundle() {
      const dist = resolve(__dirname, "dist");
      if (existsSync(resolve(dist, "index.html"))) copyFileSync(resolve(dist, "index.html"), resolve(dist, "404.html"));
    },
  };
}

export default defineConfig({
  // No GitHub Pages o site fica em /<nome-do-repositório>/ — o workflow define VITE_BASE.
  base: process.env.VITE_BASE || "/",
  plugins: [react(), tailwindcss(), spaFallback()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
    fs: { allow: [".."] }, // permite ler ../campanha.json
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    globals: true,
  },
});
