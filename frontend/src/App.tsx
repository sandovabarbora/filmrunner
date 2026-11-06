import { useEffect, useRef, useState } from "react";
import { CallSheetView, StillBackground } from "./CallSheetView";
import { loadCallSheet, loadNextDay, loadPersonal, markSeen, publicCallSheetUrl, type LoadResult, type PersonalResult } from "./loader";
import { useLogoGesture } from "./logoGesture";
import { NotificationToggle } from "./NotificationToggle";
import { SandboxBar } from "./SandboxBar";
import { leaveSandbox, loadSandbox } from "./sandbox";
import { ConfirmRevision } from "./ConfirmRevision";
import type { CrewDayRef, CrewNextDay } from "./types";
import { detectLang, fmtDate, fmtSavedAt, rememberLang, t, type Lang } from "./i18n";

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

function plusOneDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return "";
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/**
 * FR-42: what the sheet says about tomorrow, from the stable-link answer alone.
 * The next day by date after the one shown: on the following date it is "tomorrow"; later means a day off first.
 */
function tomorrowLine(days: CrewDayRef[], currentId: string): { kind: "day" | "cancelled" | "off"; day: CrewDayRef } | null {
  const current = days.find((d) => d.call_sheet_id === currentId);
  if (!current) return null;
  const next = [...days].filter((d) => d.shoot_date > current.shoot_date).sort((a, b) => a.shoot_date.localeCompare(b.shoot_date))[0];
  if (!next) return null;
  if (next.shoot_date !== plusOneDay(current.shoot_date)) return { kind: "off", day: next };
  return { kind: next.status === "cancelled" ? "cancelled" : "day", day: next };
}

const SLOW_LOAD_NOTE_MS = 4_000;

function personalData(p: PersonalResult | null) {
  return p?.kind === "live" || p?.kind === "saved" ? p.data : null;
}

/** A read that could not reach the server says nothing about the person, so it does not take away the block they are reading. A 404 does. */
function afterRead(shown: PersonalResult | null, next: PersonalResult): PersonalResult | null {
  return next.kind === "unreachable" && personalData(shown) ? shown : next;
}

export function App() {
  const [mode, setMode] = useState<Mode>(modeFromLocation);
  // FR-48: labels in the crew member's language; the toggle is remembered per device.
  const [lang, setLang] = useState<Lang>(detectLang);
  const L = (key: Parameters<typeof t>[1], vars?: Record<string, string | number>) => t(lang, key, vars);
  function switchLang() { const next: Lang = lang === "cs" ? "en" : "cs"; rememberLang(next); setLang(next); }
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const [mine, setMine] = useState<CrewNextDay | null>(null);
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [sheetId, setSheetId] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "", text: "" });
  const [result, setResult] = useState<LoadResult | null>(null);
  const [personal, setPersonal] = useState<PersonalResult | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  // FR-47: the PDF button appends ?print=1 so the printed page opens the print dialog on load, no extra tap.
  const [printRequested] = useState(() => new URLSearchParams(window.location.search).get("print") === "1");
  const printedRef = useRef(false);
  const refreshRef = useRef<() => Promise<void>>(() => Promise.resolve());
  // Reads overlap (first load, the re-check, the poll). An answer counts unless a read started after it has already answered,
  // so a late failure cannot overwrite a newer answer, and a first load is not held back waiting for a newer read.
  const sheetReads = useRef({ started: 0, answered: 0 });
  const personalReads = useRef({ started: 0, answered: 0 });

  async function readPersonal(api: string, sheet: string, me: string) {
    const read = ++personalReads.current.started;
    const p = await loadPersonal(api, sheet, me);
    if (read < personalReads.current.answered) return;
    personalReads.current.answered = read;
    setPersonal((shown) => afterRead(shown, p));
  }

  async function load(url: string, id: string, me: string | null = null) {
    const read = ++sheetReads.current.started;
    const r = await loadCallSheet(url, id);
    if (read < sheetReads.current.answered) return;
    sheetReads.current.answered = read;
    setResult(r);
    // A live load through a personal link is a read receipt (FR-36); a cached copy is not — the AD must not think REV B arrived.
    if (r.kind === "live" && me && mode.kind === "share") markSeen(mode.api, id, me);
    if (r.kind === "live") setStatus({ kind: "online", text: L("status.live") });
    if (r.kind === "cached") setStatus({ kind: "offline", text: L("status.cached", { rev: r.data.current_revision?.revision_letter ?? "—", when: fmtSavedAt(lang, r.fetchedAt) }) });
    if (r.kind === "unknown") setStatus({ kind: "offline", text: L("status.unknown") });
    if (r.kind === "not_found") setStatus({ kind: "error", text: L("status.notfound") });
    if (r.kind === "error") setStatus({ kind: "error", text: L("status.error", { reason: r.reason }) });
  }

  useEffect(() => {
    if (mode.kind === "demo") void load(DEMO_URL, DEMO_ID);
    if (mode.kind === "share") {
      void load(publicCallSheetUrl(mode.api, mode.sheet), mode.sheet, mode.me);
      if (mode.me) {
        void readPersonal(mode.api, mode.sheet, mode.me);
        // A day link opened through a personal token still gets "tomorrow" and the other days (FR-42, FR-32).
        if (!mine) void loadNextDay(mode.api, mode.me).then((next) => { if (next && next !== "invalid") setMine(next); });
      }
    }
    if (mode.kind === "mine") {
      // The stable link: resolve to a day, then behave exactly like the day's own share link.
      void loadNextDay(mode.api, mode.me).then((next) => {
        if (next === "invalid") { setPersonal({ kind: "invalid" }); setStatus({ kind: "error", text: L("status.invalidToken") }); return; }
        if (next === null) { setStatus({ kind: "error", text: L("status.unreachable") }); return; }
        setMine(next);
        if (!next.call_sheet_id) { setStatus({ kind: "offline", text: L("status.noDay", { production: next.production_name }) }); return; }
        setMode({ kind: "share", api: mode.api, sheet: next.call_sheet_id, me: mode.me });
      });
    }
  }, [mode]);

  useEffect(() => {
    // FR-130: a tab left open from before a publish must not keep showing the
    // old revision forever — loadCallSheet() already goes network-first each
    // call, so re-running it is enough; nothing here was re-running it. A
    // periodic poll covers a screen left on through the shoot; the
    // visibilitychange listener covers the common case of picking the phone
    // back up, without waiting out the full interval.
    if (mode.kind !== "share") return;
    let latest = 0;
    const refresh = async () => {
      const mine = ++latest;
      // The block first: a block newer than the sheet for a moment is harmless, a new revision over an old call time is not.
      if (mode.me) {
        await readPersonal(mode.api, mode.sheet, mode.me);
        if (mine !== latest) return;
      }
      if (mine === latest) await load(publicCallSheetUrl(mode.api, mode.sheet), mode.sheet, mode.me);
    };
    refreshRef.current = refresh;
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => { document.removeEventListener("visibilitychange", onVisible); window.clearInterval(timer); };
  }, [mode]);

  useEffect(() => {
    // The first answer on a first visit goes round the worker, so its cache has nothing for a later open with no signal.
    // Once the worker has control, one more read goes through it, and a worker that replaced an unstamped one can now say what is live.
    const sw = navigator.serviceWorker;
    if (mode.kind !== "share" || !sw) return;
    const recheck = () => void refreshRef.current();
    sw.addEventListener("controllerchange", recheck, { once: true });
    return () => sw.removeEventListener("controllerchange", recheck);
  }, [mode]);

  useEffect(() => {
    if (!printRequested || printedRef.current) return;
    if (result && (result.kind === "live" || result.kind === "cached")) {
      printedRef.current = true;
      // Let the sheet paint before the print dialog steals focus.
      const t = setTimeout(() => window.print(), 60);
      return () => clearTimeout(t);
    }
  }, [printRequested, result]);

  const shareUrl = mode.kind === "share"
    ? `${window.location.origin}${window.location.pathname}?sheet=${mode.sheet}&api=${encodeURIComponent(mode.api)}`
    : null;

  const onLogoTap = useLogoGesture(() => { window.location.href = "editor.html#/test"; });

  const subtitle =
    mode.kind === "dev" ? L("sub.dev") : mode.kind === "share" || mode.kind === "mine" ? L("sub.your") : mode.kind === "demo" ? L("sub.demo") : L("sub.home");
  const loading = result === null && status.kind === "" && (mode.kind === "demo" || mode.kind === "share" || mode.kind === "mine");
  const sheetShown = !!result && result.kind !== "error" && result.kind !== "not_found";
  const myBlock = personalData(personal);

  useEffect(() => {
    if (!loading) { setSlowLoad(false); return; }
    const timer = window.setTimeout(() => setSlowLoad(true), SLOW_LOAD_NOTE_MS);
    return () => window.clearTimeout(timer);
  }, [loading]);

  async function retry() {
    setRetrying(true);
    await refreshRef.current();
    setRetrying(false);
  }

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
      {new URLSearchParams(window.location.search).has("sandbox") && (
        <SandboxBar persona={loadSandbox()?.current ?? null} lang={lang} switchHref="editor.html#/test" onExit={() => { leaveSandbox(); window.location.href = "./"; }} />
      )}
      <header className="masthead">
        <h1 onClick={onLogoTap}>FilmRunner</h1>
        <p className="sub" id="subtitle">{subtitle}</p>
        {/* FR-82: no aria-label — the printed target-language name (e.g. "Čeština") is the accessible name too, so it can never drift from what's on screen; `title` carries the same explanation as a hover tooltip. */}
        <button type="button" className="lang-toggle" id="langToggle" onClick={switchLang} title={lang === "cs" ? "Switch to English" : "Přepnout do češtiny"}>{L("lang.toggle")}</button>
      </header>
      <p className="print-meta" aria-hidden="true">{L("print.meta", { when: new Date().toLocaleString() })}</p>
      <main id="main">

      {mode.kind === "home" && (
        <section className="home" aria-label="Start">
          <StillBackground />
          <p className="home-mark" aria-hidden="true" onClick={onLogoTap}>FilmRunner</p>
          <div className="home-card">
            <h2>{L("home.crew")}</h2>
            <p>{L("home.crewText")}</p>
            <a className="button" id="openDemo" href="?demo=1">{L("home.demo")}</a>
          </div>
          <div className="home-card">
            <h2>{L("home.running")}</h2>
            <p>{L("home.runningText")}</p>
            <a className="button primary" id="openEditor" href="editor.html">{L("home.editor")}</a>
          </div>
          <p className="home-about"><a id="openLanding" href="landing.html">{L("home.about")}</a></p>
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
      {loading && slowLoad && <p className="slow-load" id="slowLoad" role="status">{L("status.slow")}</p>}

      {personal?.kind === "invalid" && (
        <div className="status offline" id="personalInvalid" role="status">{L("personal.invalid")}</div>
      )}
      {sheetShown && personal?.kind === "unreachable" && (
        <div className="status offline" id="personalUnreachable" role="status">
          <p className="status-line">{L("personal.unreachable")}</p>
          <button type="button" className="secondary" id="personalRetry" disabled={retrying} onClick={() => void retry()}>{retrying ? L("personal.retrying") : L("personal.retry")}</button>
        </div>
      )}
      {/* With the whole sheet on a saved copy its banner already says this. */}
      {sheetShown && personal?.kind === "saved" && result.kind !== "cached" && (
        <div className="status offline" id="personalSaved" role="status">{L("personal.saved", { when: fmtSavedAt(lang, personal.savedAt) })}</div>
      )}
      {result && result.kind !== "error" && result.kind !== "not_found" && (
        <CallSheetView
          callSheet={result.data}
          personal={myBlock}
          freshness={result.kind === "cached" ? { fromCache: true, fetchedAt: result.fetchedAt } : { fromCache: false }}
          shareUrl={shareUrl}
          lang={lang}
          dayHref={mode.kind === "share" ? (id) => `?api=${encodeURIComponent(mode.api)}&sheet=${id}${mode.me ? `&me=${encodeURIComponent(mode.me)}` : ""}` : undefined}
          confirm={mode.kind === "share" && mode.me && myBlock && myBlock.works_today !== false && result.data.status !== "cancelled" && result.data.current_revision ? (
            <ConfirmRevision
              apiBase={mode.api}
              sheetId={mode.sheet}
              token={mode.me}
              letter={result.data.current_revision.revision_letter}
              // The block and the sheet refresh separately: a confirmation counts only for the revision on screen.
              confirmedAt={myBlock.revision_letter === result.data.current_revision.revision_letter ? myBlock.confirmed_at ?? null : null}
              // An `unknown` sheet can still confirm: the server refuses a stale letter, so a wrong guess about its freshness costs nothing.
              // The person's own block has no such check: they must not confirm a revision whose times for them they have not seen.
              waitingFor={result.kind === "cached" ? "sheet" : personal?.kind === "live" && myBlock.revision_letter === result.data.current_revision.revision_letter ? null : "block"}
              lang={lang}
              onStale={() => void refreshRef.current()}
              pushable={!myBlock.is_cast}
              changed={result.data.current_revision.revision_letter !== "A"}
            />
          ) : null}
        />
      )}
      {/* Push is crew-only: an actor's phone hears from the AD by SMS or WhatsApp, with the times in the message. */}
      {mode.kind === "share" && mode.me && myBlock && !myBlock.is_cast && (
        <NotificationToggle apiBase={mode.api} token={mode.me} lang={lang} />
      )}
      {mine && mode.kind === "share" && result && result.kind !== "error" && result.kind !== "not_found" && (() => {
        const t = tomorrowLine(mine.days, mode.sheet);
        if (!t) return null;
        const dayHref = `?api=${encodeURIComponent(mode.api)}&sheet=${t.day.call_sheet_id}&me=${encodeURIComponent(mode.me ?? "")}`;
        return (
          <aside className="tomorrow" id="tomorrow" data-kind={t.kind} aria-label={L("tomorrow")}>
            <span className="k">{L("tomorrow")}</span>{" "}
            {t.kind === "off" && <>{L("tomorrow.off")} <a href={dayHref}>{L("day.n", { n: t.day.day_number })} · {fmtDate(lang, t.day.shoot_date)}</a></>}
            {t.kind === "cancelled" && <>{L("day.n", { n: t.day.day_number })} · {fmtDate(lang, t.day.shoot_date)} · <strong>{L("tomorrow.cancelled")}</strong></>}
            {t.kind === "day" && (
              <>
                <a href={dayHref}>{L("day.n", { n: t.day.day_number })} · {fmtDate(lang, t.day.shoot_date)}</a>
                {t.day.general_crew_call && <> · {L("tomorrow.crewCall")} <b>{t.day.general_crew_call}</b></>}
                {t.day.first_location_name && <> · {t.day.first_location_name}</>}
              </>
            )}
          </aside>
        );
      })()}
      {mine && mine.days.length > 1 && mode.kind === "share" && (
        <nav className="other-days" id="otherDays" aria-label="Other days">
          <span className="label">{L("days")}</span>
          {mine.days.map((d) => (
            d.call_sheet_id === mode.sheet
              ? <span key={d.call_sheet_id} className="day on" aria-current="page">{L("day.n", { n: d.day_number })} · {fmtDate(lang, d.shoot_date)}{d.status === "cancelled" ? ` · ${L("tomorrow.cancelled")}` : ""}</span>
              : <a key={d.call_sheet_id} className={`day${d.status === "cancelled" ? " off" : ""}`} href={`?api=${encodeURIComponent(mode.api)}&sheet=${d.call_sheet_id}&me=${encodeURIComponent(mode.me ?? "")}`}>{L("day.n", { n: d.day_number })} · {fmtDate(lang, d.shoot_date)}{d.status === "cancelled" ? ` · ${L("tomorrow.cancelled")}` : ""}</a>
          ))}
        </nav>
      )}
      {result?.kind === "error" && (
        <div className="empty" role="status">
          {L("empty.notCached")}
        </div>
      )}
      {result?.kind === "not_found" && (
        <div className="empty" id="notFound" role="status">
          {L("empty.notFound")}
        </div>
      )}
      {(!result || result.kind === "error" || result.kind === "not_found") && <div id="sheet" className="sheet" />}
      {/* FR-77: only appears once loading is settled (result, error, or not-found), so it never sits
          pre-rendered above the ~10,000px sheet swap and gets pushed down as a layout shift. */}
      {mode.kind !== "dev" && !loading && <p className="privacy-line"><a href="privacy.html" id="privacyLink">{L("privacy")}</a></p>}
      </main>
    </div>
  );
}
