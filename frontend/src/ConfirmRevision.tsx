import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { confirmRevision } from "./loader";
import { browserSupportsPush, currentSubscription, fetchVapidPublicKey, isOurApi, subscribe } from "./push";
import { t, type Lang } from "./i18n";

type PushState = "unknown" | "offer" | "on" | "blocked" | "failed" | "needs-install" | "none";

/** Opening a link is not reading it. This is the person's own word that they know, and the AD's list is built from it.
 *  The same tap turns on notifications: a browser only asks in response to a tap, and this is the moment the reason is obvious. */
export function ConfirmRevision({ apiBase, sheetId, token, letter, confirmedAt, offline, lang, onStale, pushable, changed }: {
  apiBase: string; sheetId: string; token: string; letter: string; confirmedAt: string | null; offline: boolean; lang: Lang; onStale: () => void;
  /** Push is crew-only today: an actor hears from the AD by message. */
  pushable: boolean;
  changed: boolean;
}) {
  const L = (key: Parameters<typeof t>[1], vars?: Record<string, string | number>) => t(lang, key, vars);
  const [done, setDone] = useState(confirmedAt);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<"stale" | "failed" | null>(null);
  const [push, setPush] = useState<PushState>("unknown");
  const [vapidKey, setVapidKey] = useState<string | null>(null);
  useEffect(() => { setDone(confirmedAt); setProblem(null); }, [letter, confirmedAt]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!pushable || !isOurApi(apiBase)) { setPush("none"); return; }
      // iOS Safari only offers push to a page added to the home screen.
      if (!browserSupportsPush()) { setPush("needs-install"); return; }
      const [key, existing] = await Promise.all([fetchVapidPublicKey(apiBase), currentSubscription()]);
      if (cancelled) return;
      setVapidKey(key);
      if (existing) setPush("on");
      else if (!key) setPush("none");
      else setPush(Notification.permission === "denied" ? "blocked" : "offer");
    })();
    return () => { cancelled = true; };
  }, [apiBase, pushable]);

  function turnOnPush() {
    if (!vapidKey) return;
    // Must start inside the tap: Safari refuses a permission request made after anything else was awaited.
    subscribe(apiBase, token, vapidKey)
      .then(() => setPush("on"))
      .catch(() => setPush(Notification.permission === "denied" ? "blocked" : "failed"));
  }

  async function confirm() {
    if (push === "offer") turnOnPush();
    setBusy(true);
    setProblem(null);
    // Never waits on the notification prompt: confirming counts whatever the answer to it is.
    const result = await confirmRevision(apiBase, sheetId, token, letter);
    setBusy(false);
    if (result.kind === "confirmed") setDone(result.confirmedAt);
    else if (result.kind === "stale") { setProblem("stale"); onStale(); }
    else setProblem("failed");
  }

  if (done) {
    const time = new Date(done).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return (
      <div className="confirm-done" id="confirmDone">
        <p className="confirm-done-line"><Icon name="check" />{L("confirm.done", { rev: letter, time })}</p>
        {push === "on" && <p className="confirm-push" id="confirmPushOn">{L("confirm.pushOn")}</p>}
        {push === "blocked" && <p className="confirm-push" id="confirmPushBlocked">{L("confirm.pushBlocked")}</p>}
        {push === "needs-install" && <p className="confirm-push" id="confirmPushInstall">{L("confirm.pushInstall")}</p>}
        {(push === "offer" || push === "failed") && (
          <button type="button" className="secondary" id="confirmPushEnable" onClick={turnOnPush}>
            <Icon name="bell" />{push === "failed" ? L("confirm.pushRetry") : L("confirm.pushEnable")}
          </button>
        )}
      </div>
    );
  }
  return (
    <div className={`confirm${offline ? " offline" : ""}`} id="confirm">
      <p className="confirm-ask" id="confirmAsk">{changed ? L("confirm.askChanged") : L("confirm.askFirst")}</p>
      <button type="button" id="confirmBtn" disabled={busy || offline} onClick={() => void confirm()}>
        {busy ? L("confirm.busy") : L("confirm.action", { rev: letter })}
      </button>
      {push === "offer" && !offline && <p className="confirm-note" id="confirmPushNote">{L("confirm.pushNote")}</p>}
      {offline && <p className="confirm-note" id="confirmOffline">{L("confirm.offline")}</p>}
      {problem === "stale" && <p className="confirm-note" role="alert" id="confirmStale">{L("confirm.stale")}</p>}
      {problem === "failed" && <p className="confirm-note" role="alert" id="confirmFailed">{L("confirm.failed")}</p>}
    </div>
  );
}
