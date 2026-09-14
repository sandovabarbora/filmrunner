/**
 * Service worker: caches the app shell so the page itself loads with no
 * signal, and does network-first-with-cache-fallback for API GET requests
 * as a second offline layer underneath the IndexedDB store in app.js.
 *
 * Reference: https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
 */

const SHELL_CACHE = "filmrunner-shell-v2";
const API_CACHE = "filmrunner-api-v1";
const SHELL_ASSETS = ["./", "./index.html", "./manifest.json", "./icon.svg", "./demo/call-sheet.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== API_CACHE)
            .map((key) => caches.delete(key))
        )
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isApiCall = url.pathname.startsWith("/api/");

  if (isApiCall && event.request.method === "GET") {
    event.respondWith(networkFirstWithCache(event.request));
    return;
  }

  if (SHELL_ASSETS.some((asset) => url.pathname.endsWith(asset.replace("./", "")))) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});

async function networkFirstWithCache(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    throw err;
  }
}
