import { useEffect, useState } from "react";
import { CallSheetView } from "./CallSheetView";
import { loadCallSheet, loadNextDay, loadPersonal, markSeen, publicCallSheetUrl, type LoadResult } from "./loader";
import { NotificationToggle } from "./NotificationToggle";
import type { CrewNextDay, PersonalSheet } from "./types";

/**
 * The URL decides what the page is:
 *   ?sheet=<id>&api=<base>  a shared call sheet from a FilmRunner API (crew link)
 *   ?me=<token>&api=<base>  a crew member's one link for the whole shoot: opens their next day (FR-32)
 *   ?dev=1                  the lookup form, for local development
 *   anything else           the bundled demo, so the public URL never shows a form
 */
type Mode =
  | { kind: "share"; api: string; sheet: string; me: string | null }
  | { kind: "mine"; api: string; me: string }
  | { kind: "dev" }
  | { kind: "demo" }
  | { kind: "home" };

const DEMO_URL = "demo/call-sheet.json";
const DEMO_ID = "demo";

function modeFromLocation(): Mode {
  const params = new URLSearchParams(window.location.search);
  const sheet = params.get("sheet");
  const api = params.get("api");
  if (sheet && api) return { kind: "share", api, sheet, me: params.get("me") };
  const me = params.get("me");
  if (me && api) return { kind: "mine", api, me };
  if (params.get("dev") === "1") return { kind: "dev" };
  if (params.get("demo") === "1") return { kind: "demo" };
  return { kind: "home" };
}

type Status = { kind: "" | "online" | "offline" | "error"; text: string };

export function App() {
  const [mode, setMode] = useState<Mode>(modeFromLocation);
  const [mine, setMine] = useState<CrewNextDay | null>(null);
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [sheetId, setSheetId] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "", text: "" });
  const [result, setResult] = useState<LoadResult | null>(null);
  const [personal, setPersonal] = useState<PersonalSheet | null | "invalid">(null);

  async function load(url: string, id: string, me: string | null = null) {
    const r = await loadCallSheet(url, id);
    setResult(r);
    // A live load through a personal link is a read receipt (FR-36); a cached copy is not — the AD must not think REV B arrived.
    if (r.kind === "live" && me && mode.kind === "share") markSeen(mode.api, id, me);
    if (r.kind === "live") setStatus({ kind: "online", text: "Live · saved on this phone for offline use." });
    if (r.kind === "cached") setStatus({ kind: "offline", text: `Offline · showing the copy saved ${new Date(r.fetchedAt).toLocaleString()}. Times may have changed since.` });
    if (r.kind === "unknown") setStatus({ kind: "offline", text: "Unknown freshness · this phone's saved app could not confirm whether this is live. Reinstall it (close and reopen) if this keeps happening." });
    if (r.kind === "not_found") setStatus({ kind: "error", text: "This call sheet does not exist or is not available any more." });
    if (r.kind === "error") setStatus({ kind: "error", text: `Could not load this call sheet (${r.reason}).` });
  }

  useEffect(() => {
    if (mode.kind === "demo") void load(DEMO_URL, DEMO_ID);
    if (mode.kind === "share") {
      void load(publicCallSheetUrl(mode.api, mode.sheet), mode.sheet, mode.me);
      if (mode.me) void loadPersonal(mode.api, mode.sheet, mode.me).then(setPersonal);
    }
    if (mode.kind === "mine") {
      // The stable link: resolve to a day, then behave exactly like the day's own share link.
      void loadNextDay(mode.api, mode.me).then((next) => {
        if (next === "invalid") { setPersonal("invalid"); setStatus({ kind: "error", text: "This personal link is not on any crew list. Ask your AD for a new one." }); return; }
        if (next === null) { setStatus({ kind: "error", text: "Could not reach the server and no day is saved on this phone yet. Open this link once in signal." }); return; }
        setMine(next);
        if (!next.call_sheet_id) { setStatus({ kind: "offline", text: `${next.production_name}: no shoot day published yet. Keep this link; it will open your next day.` }); return; }
        setMode({ kind: "share", api: mode.api, sheet: next.call_sheet_id, me: mode.me });
      });
    }
  }, [mode]);

  const subtitle =
    mode.kind === "dev" ? "Development" : mode.kind === "share" || mode.kind === "mine" ? "Your call sheet" : mode.kind === "demo" ? "Demo shoot day" : "The living call sheet";
  const loading = result === null && status.kind === "" && (mode.kind === "demo" || mode.kind === "share" || mode.kind === "mine");

  function onLookup() {
    const id = sheetId.trim();
    if (!id) {
      setStatus({ kind: "error", text: "Enter a call sheet ID." });
      return;
    }
    void load(publicCallSheetUrl(apiBase, id), id);
  }

  return (
    <div className="wrap">
      <header className="masthead">
        <h1>FilmRunner</h1>
        <p className="sub" id="subtitle">{subtitle}</p>
      </header>
      <p className="print-meta" aria-hidden="true">Printed {new Date().toLocaleString()} · check the live link before call; revisions replace this page.</p>

      {mode.kind === "home" && (
        <section className="home" aria-label="Start">
          <div className="home-card">
            <h2>Crew</h2>
            <p>Open the link your AD sent you. It works with no signal once opened, and updates itself when a revision goes out.</p>
            <a className="button" id="openDemo" href="?demo=1">See a demo call sheet</a>
          </div>
          <div className="home-card">
            <h2>Running a production</h2>
            <p>Create shoot days, publish revisions, keep the crew and their numbers in one place.</p>
            <a className="button primary" id="openEditor" href="editor.html">Open the editor</a>
          </div>
          <p className="home-about"><a id="openLanding" href="landing.html">What is FilmRunner?</a></p>
        </section>
      )}

      {mode.kind === "dev" && (
        <div className="lookup" id="lookup">
          <input id="apiBase" type="text" value={apiBase} onChange={(e) => setApiBase(e.target.value)}
            placeholder="API base, e.g. http://localhost:8000" />
          <input id="callSheetId" type="text" value={sheetId} onChange={(e) => setSheetId(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onLookup(); }} placeholder="Call sheet ID" />
          <button id="loadBtn" onClick={onLookup}>Load</button>
        </div>
      )}

      <div id="status" className={`status ${status.kind}`}>{status.text}</div>

      {loading && (
        <div className="skeleton" aria-hidden="true"><i /><i /><i /></div>
      )}

      {personal === "invalid" && (
        <div className="status offline" id="personalInvalid" role="status">This personal link is not on the crew list any more. Showing the general call sheet.</div>
      )}
      {mode.kind === "share" && mode.me && personal && personal !== "invalid" && (
        <NotificationToggle apiBase={mode.api} token={mode.me} />
      )}
      {result && result.kind !== "error" && result.kind !== "not_found" && (
        <CallSheetView
          callSheet={result.data}
          personal={personal && personal !== "invalid" ? personal : null}
          freshness={result.kind === "cached" ? { fromCache: true, fetchedAt: result.fetchedAt } : { fromCache: false }}
        />
      )}
      {mine && mine.days.length > 1 && mode.kind === "share" && (
        <nav className="other-days" id="otherDays" aria-label="Other days">
          <span className="label">Days</span>
          {mine.days.map((d) => (
            d.call_sheet_id === mode.sheet
              ? <span key={d.call_sheet_id} className="day on" aria-current="page">Day {d.day_number} · {d.shoot_date}{d.status === "cancelled" ? " · cancelled" : ""}</span>
              : <a key={d.call_sheet_id} className={`day${d.status === "cancelled" ? " off" : ""}`} href={`?api=${encodeURIComponent(mode.api)}&sheet=${d.call_sheet_id}&me=${encodeURIComponent(mode.me ?? "")}`}>Day {d.day_number} · {d.shoot_date}{d.status === "cancelled" ? " · cancelled" : ""}</a>
          ))}
        </nav>
      )}
      {result?.kind === "error" && (
        <div className="empty" role="status">
          This call sheet is not on this phone yet and the server could not be reached. Get back in signal and reload; it will be saved for offline use after the first load.
        </div>
      )}
      {result?.kind === "not_found" && (
        <div className="empty" id="notFound" role="status">
          This call sheet does not exist or is not available any more. Check the link with whoever sent it — reloading will not help.
        </div>
      )}
      {(!result || result.kind === "error" || result.kind === "not_found") && <div id="sheet" className="sheet" />}
    </div>
  );
}
