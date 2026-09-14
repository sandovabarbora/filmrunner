import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// VITE_BASE is "/filmrunner/" on GitHub Pages (set in pages.yml) and "/" locally.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg", "demo/call-sheet.json"],
      manifest: {
        name: "FilmRunner Call Sheets",
        short_name: "Call Sheet",
        description: "Offline-capable shoot-day call sheet viewer",
        start_url: ".",
        display: "standalone",
        background_color: "#f7f4ee",
        theme_color: "#f7f4ee",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
      workbox: {
        // App shell and the bundled demo are precached; API reads are
        // network-first with a cache fallback (second offline layer under
        // the IndexedDB store in cache.ts).
        globPatterns: ["**/*.{js,css,html,svg,json}"],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/api/v1/public/call-sheets/"),
            handler: "NetworkFirst",
            options: { cacheName: "filmrunner-api-v1", networkTimeoutSeconds: 5 },
          },
        ],
      },
    }),
  ],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: { viewer: resolve(__dirname, "index.html"), editor: resolve(__dirname, "editor.html") },
    },
  },
});
