import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { confirmRevision } from "./loader";
import { t, type Lang } from "./i18n";

/** Opening a link is not reading it. This is the crew member's own word that they know, and the AD's list is built from it. */
export function ConfirmRevision({ apiBase, sheetId, token, letter, confirmedAt, offline, lang, onStale }: {
  apiBase: string; sheetId: string; token: string; letter: string; confirmedAt: string | null; offline: boolean; lang: Lang; onStale: () => void;
}) {
  const L = (key: Parameters<typeof t>[1], vars?: Record<string, string | number>) => t(lang, key, vars);
  const [done, setDone] = useState(confirmedAt);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<"stale" | "failed" | null>(null);
  useEffect(() => { setDone(confirmedAt); setProblem(null); }, [letter, confirmedAt]);

  async function confirm() {
    setBusy(true);
    setProblem(null);
    const result = await confirmRevision(apiBase, sheetId, token, letter);
    setBusy(false);
    if (result.kind === "confirmed") setDone(result.confirmedAt);
    else if (result.kind === "stale") { setProblem("stale"); onStale(); }
    else setProblem("failed");
  }

  if (done) {
    const time = new Date(done).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return <p className="confirm-done" id="confirmDone"><Icon name="check" />{L("confirm.done", { rev: letter, time })}</p>;
  }
  return (
    <div className="confirm" id="confirm">
      <button type="button" id="confirmBtn" disabled={busy || offline} onClick={() => void confirm()}>
        {busy ? L("confirm.busy") : L("confirm.action", { rev: letter })}
      </button>
      {offline && <p className="confirm-note" id="confirmOffline">{L("confirm.offline")}</p>}
      {problem === "stale" && <p className="confirm-note" role="alert" id="confirmStale">{L("confirm.stale")}</p>}
      {problem === "failed" && <p className="confirm-note" role="alert" id="confirmFailed">{L("confirm.failed")}</p>}
    </div>
  );
}
