/**
 * Push event handling, imported into the workbox-generated service worker
 * via `workbox.importScripts` (vite.config.ts) — kept as a plain script
 * here because VitePWA's generateSW strategy cannot itself add custom
 * event listeners. See docs/adr/ADR-007-web-push-notifications.md.
 */

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    // Not JSON; show a generic notification rather than dropping it silently.
  }
  const title = data.title || "FilmRunner";
  const options = {
    body: data.body || "A call sheet was updated.",
    tag: data.tag || "filmrunner",
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only ever open our own pages, whatever a push message says.
  // The scope, not the origin: on GitHub Pages the origin is shared with other projects.
  const scope = self.registration.scope;
  const target = new URL((event.notification.data && event.notification.data.url) || scope, scope);
  const url = target.href.startsWith(scope) ? target.href : scope;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const c of clientList) {
        if (c.url === url && "focus" in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
