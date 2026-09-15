import { useEffect, useState } from "react";
import { browserSupportsPush, currentSubscription, fetchVapidPublicKey, subscribe, unsubscribe } from "./push";

type State =
  | { kind: "checking" }
  | { kind: "unsupported" }
  | { kind: "not-configured" }
  | { kind: "off"; vapidPublicKey: string }
  | { kind: "on" }
  | { kind: "busy" }
  | { kind: "error"; text: string };

/** "Enable notifications" for a crew member's own device, shown on their personal link only (FR-16). */
export function NotificationToggle({ apiBase, token }: { apiBase: string; token: string }) {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!browserSupportsPush()) {
        if (!cancelled) setState({ kind: "unsupported" });
        return;
      }
      const [key, existing] = await Promise.all([fetchVapidPublicKey(apiBase), currentSubscription()]);
      if (cancelled) return;
      if (existing) { setState({ kind: "on" }); return; }
      if (!key) { setState({ kind: "not-configured" }); return; }
      setState({ kind: "off", vapidPublicKey: key });
    })();
    return () => { cancelled = true; };
  }, [apiBase]);

  async function enable(vapidPublicKey: string) {
    setState({ kind: "busy" });
    try {
      await subscribe(apiBase, token, vapidPublicKey);
      setState({ kind: "on" });
    } catch (err) {
      setState({ kind: "error", text: err instanceof Error ? err.message : "Could not enable notifications" });
    }
  }

  async function disable() {
    setState({ kind: "busy" });
    await unsubscribe(apiBase, token);
    const key = await fetchVapidPublicKey(apiBase);
    setState(key ? { kind: "off", vapidPublicKey: key } : { kind: "not-configured" });
  }

  if (state.kind === "checking" || state.kind === "unsupported" || state.kind === "not-configured") return null;

  return (
    <div className="notify" id="notifyToggle">
      {state.kind === "on" && (
        <>
          <span className="notify-on">🔔 Notifications on for this device</span>
          <button type="button" className="quiet" onClick={() => void disable()}>Turn off</button>
        </>
      )}
      {state.kind === "off" && (
        <button type="button" className="secondary" onClick={() => void enable(state.vapidPublicKey)}>
          Notify me when this call sheet changes
        </button>
      )}
      {state.kind === "busy" && <span className="hint">Working…</span>}
      {state.kind === "error" && (
        <div className="status error" role="status">{state.text}</div>
      )}
    </div>
  );
}
