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
      includeAssets: ["icon.svg", "icon.png", "apple-touch-icon.png", "demo/call-sheet.json"],
      manifest: {
        name: "FilmRunner",
        short_name: "FilmRunner",
        description: "Offline-capable shoot-day call sheet viewer",
        start_url: ".",
        display: "standalone",
        background_color: "#f7f4ee",
        theme_color: "#f7f4ee",
        // PNGs from scripts/make_icons.py: Android needs 192/512 and a full-bleed "maskable" it can cut to its own shape.
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
          { src: "icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // App shell and the bundled demo are precached; API reads are
        // network-first with a cache fallback (second offline layer under
        // the IndexedDB store in cache.ts).
        globPatterns: ["**/*.{js,css,html,svg,json}"],
        // generateSW cannot add custom event listeners itself; push-sw.js
        // (self.addEventListener('push', ...)) is imported into the
        // generated service worker instead (FR-16, ADR-007).
        importScripts: ["push-sw.js"],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/api/v1/public/call-sheets/"),
            handler: "NetworkFirst",
            options: {
              cacheName: "filmrunner-api-v1",
              networkTimeoutSeconds: 5,
              plugins: [
                {
                  // fetch() resolving does not mean the data is fresh: when
                  // this worker answers from its own cache (offline, or the
                  // network timed out), the fetch the page sees still
                  // "succeeds". Stamp every response with where it actually
                  // came from so loader.ts never has to guess.
                  fetchDidSucceed: async ({ response }) => {
                    const headers = new Headers(response.headers);
                    headers.set("x-filmrunner-source", "network");
                    headers.set("x-filmrunner-fetched-at", new Date().toISOString());
                    return new Response(await response.clone().blob(), {
                      status: response.status,
                      statusText: response.statusText,
                      headers,
                    });
                  },
                  cachedResponseWillBeUsed: async ({ cachedResponse }) => {
                    if (!cachedResponse) return cachedResponse;
                    const headers = new Headers(cachedResponse.headers);
                    headers.set("x-filmrunner-source", "cache");
                    return new Response(await cachedResponse.clone().blob(), {
                      status: cachedResponse.status,
                      statusText: cachedResponse.statusText,
                      headers,
                    });
                  },
                },
              ],
            },
          },
        ],
      },
    }),
  ],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        viewer: resolve(__dirname, "index.html"),
        editor: resolve(__dirname, "editor.html"),
        landing: resolve(__dirname, "landing.html"),
        privacy: resolve(__dirname, "privacy.html"),
      },
    },
  },
});
