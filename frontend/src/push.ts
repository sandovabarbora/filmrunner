/**
 * Web Push opt-in for a crew member's own device (FR-16). Subscribing only
 * happens from a personal link (?me=<token>) — the AD cannot enable
 * notifications on someone else's phone.
 *
 * Reference: https://developer.mozilla.org/en-US/docs/Web/API/Push_API
 */

export type PushSupport = "unsupported" | "not-configured" | "denied" | "available";

function urlBase64ToUint8Array(base64Url: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

/** The sheet takes its API from the link, so a crafted link could otherwise sign someone up for notifications from a stranger's server. */
export function isOurApi(apiBase: string): boolean {
  try {
    const { origin, hostname } = new URL(apiBase);
    const configured = import.meta.env.VITE_API_BASE ? new URL(import.meta.env.VITE_API_BASE as string).origin : null;
    // Loopback stays for tests and development: reaching it would already mean running on the person's own phone.
    return origin === "https://filmrunner-api.fly.dev" || origin === configured || hostname === "localhost" || hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

export function browserSupportsPush(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export async function fetchVapidPublicKey(apiBase: string): Promise<string | null> {
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/push/vapid-key`, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return null;
    const data = (await resp.json()) as { public_key: string | null };
    return data.public_key;
  } catch {
    return null;
  }
}

/** The current subscription for this device, if any (independent of whether the backend still has it). */
export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!browserSupportsPush()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

/** Two places on the sheet can turn notifications on, and they must not disagree about the result. */
export const PUSH_CHANGED = "filmrunner:push-changed";

export async function subscribe(apiBase: string, token: string, vapidPublicKey: string): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notification permission was not granted");
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
  const json = subscription.toJSON();
  const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/crew/${encodeURIComponent(token)}/push-subscription`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth },
      link_url: window.location.href,
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) {
    await subscription.unsubscribe();
    throw new Error(`Could not save the subscription (HTTP ${resp.status})`);
  }
  window.dispatchEvent(new Event(PUSH_CHANGED));
}

export async function unsubscribe(apiBase: string, token: string): Promise<void> {
  const subscription = await currentSubscription();
  if (!subscription) return;
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  try {
    await fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/public/crew/${encodeURIComponent(token)}/push-subscription?endpoint=${encodeURIComponent(endpoint)}`,
      { method: "DELETE", signal: AbortSignal.timeout(10_000) }
    );
  } catch {
    // The device already unsubscribed locally; a stale server-side row is
    // harmless (the next push attempt fails 410 and gets cleaned up then).
  }
}
