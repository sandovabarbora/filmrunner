import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Connection } from "../api";
import { addDays, clearDraft, draftHasContent, draftKey, emptyDraft, loadDraft, nextDayFrom, saveDraft, type CastCallDraft, type Draft } from "../drafts";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import { crewLink, personalLink } from "./Production";
import { QrCode } from "./QrCode";
import { canWebShare, daySummaryText, personalMessageText, whatsappNumber, whatsappUrl } from "../shareText";
import { isBeyondWeatherForecastHorizon } from "../weatherHorizon";
import type { Actuals, CallSheetCreated, CastMember, CastStatus, CrewMember, HistoryEntry, Location, RevisionCreate, ScheduleItemCreate, SeenReport } from "../../types";
import { useL } from "../lang";

function revisionPayload(d: Draft): RevisionCreate {
  const clean = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    head_of_day_crew_member_id: d.headOfDayId,
    general_crew_call: clean(d.general_crew_call),
    shooting_call: clean(d.shooting_call),
    sunrise: clean(d.sunrise),
    sunset: clean(d.sunset),
    weather_forecast: clean(d.weather_forecast),
    safety_notes: clean(d.safety_notes),
    created_by: "editor",
    schedule_items: d.items.map((it, i) => ({ ...it, order_index: i + 1 })),
    // Always sent from the form (prefilled from the last revision), so the AD edits rather than retypes.
    crew_calls: Object.entries(d.crewCalls ?? {})
      .filter(([, v]) => v.call.trim() || v.pickup.trim() || v.note.trim())
      .map(([id, v]) => ({ crew_member_id: id, call_time: clean(v.call), pickup_time: clean(v.pickup), note: clean(v.note) })),
    cast_calls: Object.entries(d.castCalls ?? {}).map(([id, v]) => ({
      cast_member_id: id, status_code: v.status, pickup_time: clean(v.pickup), call_time: clean(v.call), makeup_hair_time: clean(v.makeup), on_set_time: clean(v.onSet),
    })),
  };
}

/** The server's current revision, poured into an editable draft (server is the source of truth once published). */
function draftFromServer(productionId: string, productionName: string | null, sheet: CallSheetCreated): Draft {
  const rev = sheet.current_revision;
  return {
    ...emptyDraft(productionId, productionName),
    id: draftKey(productionId, sheet.id),
    callSheetId: sheet.id,
    headOfDayId: rev?.head_of_day_crew_member_id ?? null,
    lastPublishedLetter: rev?.revision_letter ?? null,
    publishedAt: rev?.created_at ?? null,
    dirtySincePublish: false,
    shoot_date: sheet.shoot_date,
    day_number: sheet.day_number,
    day_count: sheet.day_count,
    unit_name: sheet.unit_name,
    general_crew_call: rev?.general_crew_call ?? "",
    shooting_call: rev?.shooting_call ?? "",
    sunrise: rev?.sunrise ?? "",
    sunset: rev?.sunset ?? "",
    weather_forecast: rev?.weather_forecast ?? "",
    safety_notes: rev?.safety_notes ?? "",
    items: [...(rev?.schedule_items ?? [])]
      .sort((a, b) => a.order_index - b.order_index)
      .map((it) => ({ order_index: it.order_index, scene_number: it.scene_number, int_ext: (it.int_ext === "INT" ? "INT" : "EXT"), day_night: (it.day_night === "NIGHT" ? "NIGHT" : "DAY"), set_description: it.set_description, location_id: it.location_id ?? null, page_count_eighths: it.page_count_eighths })),
    crewCalls: Object.fromEntries((rev?.crew_calls ?? []).map((e) => [e.crew_member_id, { call: e.call_time ?? "", pickup: e.pickup_time ?? "", note: e.note ?? "" }])),
    castCalls: Object.fromEntries((rev?.cast_calls ?? []).map((e) => [e.cast_member_id, { status: e.status_code, pickup: e.pickup_time ?? "", call: e.call_time ?? "", makeup: e.makeup_hair_time ?? "", onSet: e.on_set_time ?? "" }])),
  };
}

function nextLetter(letter: string): string {
  return String.fromCharCode(letter.charCodeAt(0) + 1);
}

export function DayEditor({ conn, productionId, productionName, callSheetId, canPublish, setNotice }: {
  conn: Connection; productionId: string; productionName: string | null; callSheetId: string | null; canPublish: boolean; setNotice: (n: Notice) => void;
}) {
  const L = useL();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [offline, setOffline] = useState(false);
  const readOnly = offline || !canPublish;
  const setReadOnly = setOffline;
  const [crew, setCrew] = useState<CrewMember[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [weatherSuggestion, setWeatherSuggestion] = useState<string | null>(null);
  const [suggestingWeather, setSuggestingWeather] = useState(false);
  // FR-27: what the sunrise/sunset hint says — depends on whether a scene has a location and whether the lookup worked.
  const [sunState, setSunState] = useState<"none" | "filled" | "no-coords" | "failed">("none");
  const [busy, setBusy] = useState(false);
  const [shareText, setShareText] = useState<string | null>(null);
  const [nextDayClash, setNextDayClash] = useState(false);  // an unpublished new day already exists on this phone
  const [seen, setSeen] = useState<SeenReport | null>(null);  // FR-36: who opened the current revision
  const [history, setHistory] = useState<HistoryEntry[]>([]);  // FR-50: who published each revision, when, what changed
  const [dayStatus, setDayStatus] = useState<string | null>(null);  // FR-34: "cancelled" shows the banner and the restore button
  // FR-65: the production's numbers after the day; saved on their own, no revision, never on the crew's sheet.
  const EMPTY_ACTUALS: Actuals = { first_shot: null, lunch_out: null, lunch_in: null, wrap: null, note: null };
  const [actuals, setActuals] = useState<Actuals>(EMPTY_ACTUALS);
  const [actualsDirty, setActualsDirty] = useState(false);
  const [actualsBusy, setActualsBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const latest = useRef<Draft | null>(null);
  const key = draftKey(productionId, callSheetId);

  // Load: an existing day comes from the server (falling back to the local draft when offline);
  // a new day comes from the local draft or starts empty.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const local = await loadDraft(key).catch(() => null);
      if (callSheetId) {
        try {
          const sheet = await api.getCallSheet(conn, callSheetId);
          if (!cancelled) { setDayStatus(sheet.status ?? "published"); setActuals(sheet.actuals ?? EMPTY_ACTUALS); setActualsDirty(false); }
          const fromServer = draftFromServer(productionId, productionName, sheet);
          // Keep unpublished local edits if they are newer than the last publish.
          const keepLocal = local && local.dirtySincePublish && local.lastPublishedLetter === fromServer.lastPublishedLetter;
          if (!cancelled) { setDraft(keepLocal ? local : fromServer); setReadOnly(false); }
        } catch (err) {
          if (cancelled) return;
          if (local) { setDraft(local); setReadOnly(true); setNotice({ kind: "warn", text: L("Offline: showing the last copy on this phone. Reconnect to publish.") }); }
          else { setDraft(null); setReadOnly(true); setNotice(noticeFromError(err, L("Cannot load this day"))); }
        }
      } else if (!cancelled) {
        if (local) { setDraft(local); setReadOnly(false); return; }
        // A brand-new day continues the production's numbering: the day after the last one, one date on.
        const fresh = emptyDraft(productionId, productionName);
        try {
          const days = await api.listCallSheets(conn, productionId);
          const last = [...days].sort((a, b) => a.day_number - b.day_number).at(-1);
          if (last) { fresh.day_number = last.day_number + 1; fresh.day_count = Math.max(last.day_count, fresh.day_number); fresh.shoot_date = addDays(last.shoot_date, 1); fresh.unit_name = last.unit_name; }
        } catch { /* offline or not allowed: the defaults are fine */ }
        if (!cancelled) { setDraft(fresh); setReadOnly(false); }
      }
    })();
    api.listCrew(conn, productionId).then((c) => { if (!cancelled) setCrew(c); }).catch(() => undefined);
    api.listLocations(conn, productionId).then((l) => { if (!cancelled) setLocations(l); }).catch(() => undefined);
    api.listCast(conn, productionId).then((c) => { if (!cancelled) setCast(c); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [conn, productionId, productionName, callSheetId, key, setNotice]);

  useEffect(() => { latest.current = draft; if (draft) void saveDraft(draft); }, [draft]);

  const publishedLetter = draft?.callSheetId ? draft.lastPublishedLetter : null;
  useEffect(() => {
    if (!callSheetId || !publishedLetter) { setSeen(null); return; }
    let cancelled = false;
    const refresh = () => api.seenReport(conn, callSheetId).then((r) => { if (!cancelled) setSeen(r); }).catch(() => undefined);
    void refresh();
    const timer = window.setInterval(refresh, 60_000);  // people open the link over the evening; the AD keeps the screen open
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [conn, callSheetId, publishedLetter]);
  useEffect(() => {
    if (!callSheetId || !publishedLetter) { setHistory([]); return; }
    let cancelled = false;
    api.history(conn, callSheetId).then((h) => { if (!cancelled) setHistory(h); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [conn, callSheetId, publishedLetter]);
  useEffect(() => {
    const flush = () => { if (latest.current) void saveDraft(latest.current); };
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  function update(patch: Partial<Draft>) {
    // Any edit to a published day marks it dirty, unless the patch says otherwise (a publish resets it).
    setDraft((d) => (d ? { ...d, dirtySincePublish: d.callSheetId ? true : d.dirtySincePublish, ...patch } : d));
  }
  function updateItem(i: number, patch: Partial<ScheduleItemCreate>) {
    setDraft((d) => d ? { ...d, dirtySincePublish: !!d.callSheetId, items: d.items.map((it, j) => (j === i ? { ...it, ...patch } : it)) } : d);
  }
  function moveItem(i: number, dir: -1 | 1) {
    setDraft((d) => {
      if (!d) return d;
      const j = i + dir;
      if (j < 0 || j >= d.items.length) return d;
      const items = [...d.items];
      [items[i], items[j]] = [items[j], items[i]];
      return { ...d, items, dirtySincePublish: !!d.callSheetId };
    });
  }

  function firstLocationId(): string | null {
    const ordered = [...(draft?.items ?? [])].sort((a, b) => a.order_index - b.order_index);
    return ordered.find((it) => it.location_id)?.location_id ?? null;
  }

  // FR-27: as soon as the first scene has a location, sunrise and sunset appear without a reload —
  // the same computation publish would do, just earlier, and never over a value the AD typed.
  const firstLoc = firstLocationId();
  const shootDate = draft?.shoot_date ?? "";
  useEffect(() => {
    if (!firstLoc || !shootDate) { setSunState("none"); return; }
    let cancelled = false;
    api.sunTimes(conn, productionId, firstLoc, shootDate)
      .then((sun) => {
        if (cancelled) return;
        if (!sun.sunrise || !sun.sunset) { setSunState("no-coords"); return; }
        setSunState("filled");
        setDraft((d) => {
          if (!d || (d.sunrise && d.sunset)) return d;
          return { ...d, sunrise: d.sunrise || sun.sunrise!, sunset: d.sunset || sun.sunset!, dirtySincePublish: !!d.callSheetId };
        });
      })
      .catch(() => { if (!cancelled) setSunState("failed"); });
    return () => { cancelled = true; };
  }, [conn, productionId, firstLoc, shootDate]);

  async function suggestWeather() {
    if (!draft) return;
    const locationId = firstLocationId();
    if (!locationId) { setNotice({ kind: "warn", text: L("Pick a location for the first scene to get a weather suggestion.") }); return; }
    const today = new Date().toISOString().slice(0, 10);
    if (isBeyondWeatherForecastHorizon(draft.shoot_date, today)) {
      setNotice({ kind: "warn", text: L("Too far ahead to forecast yet — try again closer to the date.") });
      return;
    }
    setSuggestingWeather(true);
    try {
      const { suggestion } = await api.weatherSuggestion(conn, productionId, locationId, draft.shoot_date);
      setWeatherSuggestion(suggestion ?? null);
      if (!suggestion) setNotice({ kind: "warn", text: L("Could not get a weather forecast right now — the provider may be unreachable. Try again shortly.") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not get a weather suggestion")));
    } finally {
      setSuggestingWeather(false);
    }
  }

  async function publish() {
    if (!draft || readOnly) return;
    if (!draft.general_crew_call.trim()) { setNotice({ kind: "error", text: L("Crew call is required; the crew wakes up for that number.") }); return; }
    setBusy(true);
    try {
      if (!draft.callSheetId) {
        const created = await api.createCallSheet(conn, productionId, {
          shoot_date: draft.shoot_date, day_number: draft.day_number, day_count: draft.day_count, unit_name: draft.unit_name, initial_revision: revisionPayload(draft),
        });
        await clearDraft(key);
        const letter = created.current_revision?.revision_letter ?? "A";
        await saveDraft({ ...draft, id: draftKey(productionId, created.id), callSheetId: created.id, lastPublishedLetter: letter, publishedAt: new Date().toISOString(), dirtySincePublish: false });
        setNotice({ kind: "ok", text: L("Published REV {rev}. Everyone with the link sees it now.", { rev: letter }) });
        window.location.hash = href({ screen: "day", productionId, callSheetId: created.id });
      } else {
        const rev = await api.publishRevision(conn, draft.callSheetId, revisionPayload(draft));
        update({ lastPublishedLetter: rev.revision_letter, publishedAt: new Date().toISOString(), dirtySincePublish: false });
        setDayStatus("published");  // publishing puts a cancelled day back on, and makes a planned day real
        setNotice({ kind: "ok", text: L("Published REV {rev}. Everyone with the link sees it now.", { rev: rev.revision_letter }) });
      }
    } catch (err) {
      setNotice(err instanceof ApiError && err.status === 0
        ? { kind: "warn", text: L("No connection. Your draft is safe on this phone; publish when you are back in signal.") }
        : noticeFromError(err, L("Publish failed")));
    } finally {
      setBusy(false);
    }
  }

  async function saveActuals() {
    if (!draft?.callSheetId) return;
    setActualsBusy(true);
    try {
      const sheet = await api.setActuals(conn, draft.callSheetId, actuals);
      setActuals(sheet.actuals ?? EMPTY_ACTUALS); setActualsDirty(false);
      setNotice({ kind: "ok", text: L("Actual times saved. They stay with the production; the crew's sheet does not change.") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not save the actual times")));
    } finally {
      setActualsBusy(false);
    }
  }

  /** FR-56: a planned day nobody has seen can simply go. */
  async function deleteDraft() {
    if (!draft?.callSheetId) return;
    setBusy(true);
    try {
      await api.deleteDraftCallSheet(conn, draft.callSheetId);
      await clearDraft(key);
      setNotice({ kind: "ok", text: L("Planned Day {n} deleted.", { n: draft.day_number }) });
      window.location.hash = href({ screen: "production", productionId, tab: "days" });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not delete the planned day")));
    } finally {
      setBusy(false);
    }
  }

  /** FR-34: the day is off. Nothing is deleted; the sheet says CANCELLED and every subscriber is told. */
  async function cancelDay() {
    if (!draft?.callSheetId) return;
    setBusy(true);
    try {
      await api.cancelCallSheet(conn, draft.callSheetId);
      setDayStatus("cancelled"); setConfirmCancel(false);
      setNotice({ kind: "ok", text: L("Day {n} cancelled.", { n: draft.day_number }) + L(" The sheet now says so; the link still works.") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not cancel the day")));
    } finally {
      setBusy(false);
    }
  }
  async function restoreDay() {
    if (!draft?.callSheetId) return;
    setBusy(true);
    try {
      await api.restoreCallSheet(conn, draft.callSheetId);
      setDayStatus("published");
      setNotice({ kind: "warn", text: L("Day {n} is back on. Publish a revision so the crew gets told.", { n: draft.day_number }) });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not restore the day")));
    } finally {
      setBusy(false);
    }
  }

  /** FR-30: tomorrow starts as today. Goes to the new-day screen with the copy as its draft; asks before replacing an unpublished new day. */
  async function startNextDay(replace: boolean) {
    if (!draft) return;
    const newKey = draftKey(productionId, null);
    if (!replace && draftHasContent(await loadDraft(newKey).catch(() => null))) { setNextDayClash(true); return; }
    await saveDraft(nextDayFrom(draft));
    setNextDayClash(false);
    setNotice({ kind: "ok", text: L("Day {next} started from Day {n}. Change the date and scenes, then publish.", { next: draft.day_number + 1, n: draft.day_number }) });
    window.location.hash = href({ screen: "day", productionId, callSheetId: null });
  }

  /** Phone share sheet (WhatsApp is one tap away) when the browser has one; otherwise copy and show the text with a wa.me link. */
  async function shareAsText(title: string, text: string) {
    if (canWebShare()) {
      try { await navigator.share({ title, text }); return; }
      catch (err) { if ((err as { name?: string }).name === "AbortError") return; }
    }
    try { await navigator.clipboard?.writeText(text); setNotice({ kind: "ok", text: L("Copied. Paste it into the WhatsApp group.") }); }
    catch { setNotice({ kind: "warn", text: L("Could not copy; select the text below.") }); }
    setShareText(text);
  }

  if (!draft) return <div className="skeleton" aria-hidden="true"><i /><i /><i /></div>;
  // A planned (draft) day exists on the server but nobody has seen it: no sharing, no receipts, publish sends REV A.
  const planned = dayStatus === "draft";
  const published = draft.callSheetId && draft.lastPublishedLetter && !planned;
  // The message must say what the link says: with unpublished edits the text would lie (FR-29 dod).
  const shareable = !!published && !draft.dirtySincePublish;
  const dis = readOnly;

  return (
    <>
      <section className="block" aria-label={L("Shoot day")}>
        <h2>{L("Shoot day")}</h2>
        <div className="grid2">
          <Field label={L("Date")} id="shoot_date" type="date" value={draft.shoot_date} onChange={(v) => update({ shoot_date: v })} disabled={dis || !!draft.callSheetId} />
          <Field label={L("Unit")} id="unit_name" value={draft.unit_name} onChange={(v) => update({ unit_name: v })} disabled={dis || !!draft.callSheetId} />
          <Field label={L("Day")} id="day_number" type="number" value={String(draft.day_number)} onChange={(v) => update({ day_number: Math.max(1, Number(v) || 1) })} disabled={dis || !!draft.callSheetId} />
          <Field label={L("of")} id="day_count" type="number" value={String(draft.day_count)} onChange={(v) => update({ day_count: Math.max(1, Number(v) || 1) })} disabled={dis || !!draft.callSheetId} />
        </div>
        {draft.callSheetId && <p className="hint">{L("Date, unit and day number are fixed once published; times, notes and scenes change through revisions.")}</p>}
      </section>

      <section className="block" aria-label={L("Calls")}>
        <h2>{L("Calls")}</h2>
        <div className="grid2">
          <Field label={L("Crew call")} id="general_crew_call" placeholder="06:30" mono value={draft.general_crew_call} onChange={(v) => update({ general_crew_call: v })} disabled={dis} />
          <Field label={L("Shooting call")} id="shooting_call" placeholder="07:30" mono value={draft.shooting_call} onChange={(v) => update({ shooting_call: v })} disabled={dis} />
          <Field label={L("Sunrise")} id="sunrise" placeholder="06:41" mono value={draft.sunrise} onChange={(v) => update({ sunrise: v })} disabled={dis} />
          <Field label={L("Sunset")} id="sunset" placeholder="19:03" mono value={draft.sunset} onChange={(v) => update({ sunset: v })} disabled={dis} />
        </div>
        <Field label={L("Weather")} id="weather_forecast" value={draft.weather_forecast} onChange={(v) => update({ weather_forecast: v })} disabled={dis} />
        {!dis && (
          <div className="inline">
            <button type="button" className="quiet" disabled={suggestingWeather} onClick={() => void suggestWeather()}>
              {suggestingWeather ? L("Looking…") : L("Suggest weather")}
            </button>
            {weatherSuggestion && (
              <button type="button" className="quiet" onClick={() => { update({ weather_forecast: weatherSuggestion }); setWeatherSuggestion(null); }}>
                {L("Use: {text}", { text: weatherSuggestion })}
              </button>
            )}
          </div>
        )}
        <p className="hint" id="weatherHint">{L("Left blank, weather fills in from the first location's forecast when you publish — like sunrise and sunset.")}</p>
        <p className="hint" id="sunHint" data-state={sunState}>
          {sunState === "none" && (locations.length === 0
            ? <>{L("Add a location to this day to get sunrise, sunset, weather and the nearest hospital.")} <a href={href({ screen: "production", productionId, tab: "locations" })}>{L("Locations")}</a></>
            : <>{L("Pick a location on a scene below to get sunrise, sunset, weather and the nearest hospital. No location yet?")} <a href={href({ screen: "production", productionId, tab: "locations" })}>{L("Locations")}</a></>)}
          {sunState === "filled" && <>{L("Sunrise and sunset come from the first scene's location; edit them if you know better.")}</>}
          {sunState === "no-coords" && <>{L("That location has no map position, so sunrise and sunset cannot be computed; type them, or add an address under")} <a href={href({ screen: "production", productionId, tab: "locations" })}>{L("Locations")}</a>.</>}
          {sunState === "failed" && <>{L("Could not fetch suggestions; type sunrise and sunset yourself.")}</>}
        </p>
        <Field label={L("Safety notes")} id="safety_notes" textarea value={draft.safety_notes} onChange={(v) => update({ safety_notes: v })} disabled={dis} />
        <label className="field" htmlFor="headOfDay">
          <span className="label">{L("Head of day")}</span>
          <select id="headOfDay" value={draft.headOfDayId ?? ""} onChange={(e) => update({ headOfDayId: e.target.value || null })} disabled={dis}>
            <option value="">{L("— not set —")}</option>
            {crew.map((m) => <option key={m.id} value={m.id}>{m.contact.name} · {m.position}{m.is_head_of_department ? " (HoD)" : ""}</option>)}
          </select>
          {crew.length === 0 && <span className="hint">{L("Add crew under the Crew tab to pick who runs the day.")}</span>}
        </label>
      </section>

      <section className="block" aria-label={L("Personal calls")}>
        <h2>{L("Personal calls")}</h2>
        <p className="hint">{L("Only for people whose call differs from the crew call today. Empty means the general call (or their standing time). Carried over to the next revision.")}</p>
        {crew.length === 0 && <p className="hint">{L("Add crew under the Crew tab first.")}</p>}
        {(() => {
          // FR-44: with 40 people on the crew, list only those with an entry today; the rest are one pick away.
          const withEntry = crew.filter((m) => draft.crewCalls?.[m.id] !== undefined);
          const without = crew.filter((m) => draft.crewCalls?.[m.id] === undefined);
          const remove = (id: string) => { const next = { ...(draft.crewCalls ?? {}) }; delete next[id]; update({ crewCalls: next }); };
          return (
            <>
              <ul className="items" id="personalCalls">
                {withEntry.map((m) => {
                  const v = draft.crewCalls![m.id];
                  const set = (patch: Partial<typeof v>) => update({ crewCalls: { ...(draft.crewCalls ?? {}), [m.id]: { ...v, ...patch } } });
                  return (
                    <li key={m.id} className="item pcall">
                      <div className="pcall-who">
                        <span className="name">{m.contact.name}</span><span className="meta"> · {m.department} · {m.position}{m.standard_call_time ? ` · ${L("usually {time}", { time: m.standard_call_time })}` : ""}</span>
                        {!dis && <button type="button" className="quiet danger" onClick={() => remove(m.id)} aria-label={L("Drop {name} from personal calls", { name: m.contact.name })}>×</button>}
                      </div>
                      <div className="pcall-row">
                        <input className="mono" aria-label={L("Call for {name}", { name: m.contact.name })} placeholder={L("call")} value={v.call} disabled={dis} onChange={(e) => set({ call: e.target.value })} />
                        <input className="mono" aria-label={L("Pickup for {name}", { name: m.contact.name })} placeholder={L("pickup")} value={v.pickup} disabled={dis} onChange={(e) => set({ pickup: e.target.value })} />
                        <input aria-label={L("Note for {name}", { name: m.contact.name })} placeholder={L("note")} value={v.note} disabled={dis} onChange={(e) => set({ note: e.target.value })} />
                      </div>
                    </li>
                  );
                })}
              </ul>
              {!dis && without.length > 0 && (
                <label className="field" htmlFor="addPersonalCall">
                  <span className="label">{L("Personal call for…")}</span>
                  <select id="addPersonalCall" value="" onChange={(e) => { const id = e.target.value; if (id) update({ crewCalls: { ...(draft.crewCalls ?? {}), [id]: { call: "", pickup: "", note: "" } } }); }}>
                    <option value="">{L("— pick a person ({n} without one) —", { n: without.length })}</option>
                    {without.map((m) => <option key={m.id} value={m.id}>{m.contact.name} · {m.department}{m.standard_call_time ? ` · ${L("usually {time}", { time: m.standard_call_time })}` : ""}</option>)}
                  </select>
                </label>
              )}
            </>
          );
        })()}
      </section>

      {cast.length > 0 && (
        <section className="block" aria-label={L("Cast calls")}>
          <h2>{L("Cast")}</h2>
          <p className="hint">{L("Tick who works today and set their times. W work · SW start · WF finish · SWF start and finish · H hold · R rehearsal. Carried over to the next revision.")}</p>
          <ul className="items" id="castCalls">
            {cast.map((a) => {
              const v = draft.castCalls?.[a.id] ?? null;
              // First tick starts from their usual pickup; later edits patch the existing entry.
              const fresh: CastCallDraft = { status: "W", pickup: a.standard_pickup_time ?? "", call: "", makeup: "", onSet: "" };
              const setEntry = (patch: Partial<CastCallDraft>) =>
                update({ castCalls: { ...(draft.castCalls ?? {}), [a.id]: { ...(v ?? fresh), ...patch } } });
              const clear = () => { const next = { ...(draft.castCalls ?? {}) }; delete next[a.id]; update({ castCalls: next }); };
              return (
                <li key={a.id} className={`item pcall${v ? "" : " off"}`}>
                  <div className="pcall-who">
                    <label className="check"><input type="checkbox" aria-label={L("{name} works today", { name: a.contact.name })} checked={!!v} disabled={dis} onChange={(e) => (e.target.checked ? setEntry({}) : clear())} /> <span className="name">{a.contact.name}</span></label>
                    <span className="meta"> · {a.character_name}</span>
                  </div>
                  {v && (
                    <div className="pcall-row cast-row">
                      <select aria-label={L("Status for {name}", { name: a.contact.name })} value={v.status} disabled={dis} onChange={(e) => setEntry({ status: e.target.value as CastStatus })}>
                        {(["W", "SW", "WF", "SWF", "H", "R"] as CastStatus[]).map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <input className="mono" aria-label={L("Pickup for {name}", { name: a.contact.name })} placeholder={L("pickup")} value={v.pickup} disabled={dis} onChange={(e) => setEntry({ pickup: e.target.value })} />
                      <input className="mono" aria-label={L("Call for {name}", { name: a.contact.name })} placeholder={L("call")} value={v.call} disabled={dis} onChange={(e) => setEntry({ call: e.target.value })} />
                      <input className="mono" aria-label={L("Make-up for {name}", { name: a.contact.name })} placeholder="M/H" value={v.makeup} disabled={dis} onChange={(e) => setEntry({ makeup: e.target.value })} />
                      <input className="mono" aria-label={L("On set for {name}", { name: a.contact.name })} placeholder={L("on set")} value={v.onSet} disabled={dis} onChange={(e) => setEntry({ onSet: e.target.value })} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="block" aria-label={L("Schedule")}>
        <h2>{L("Schedule")}</h2>
        {draft.items.length === 0 && <p className="hint">{L("No scenes yet. Add the first one; order is the shooting order.")}</p>}
        <ol className="items" id="items">
          {draft.items.map((it, i) => (
            <li key={i} className="item">
              <div className="item-row">
                <input className="mono scene" aria-label={L("Scene")} placeholder="42" value={it.scene_number} disabled={dis} onChange={(e) => updateItem(i, { scene_number: e.target.value })} />
                <select aria-label={L("Int/Ext")} value={it.int_ext} disabled={dis} onChange={(e) => updateItem(i, { int_ext: e.target.value as "INT" | "EXT" })}><option>INT</option><option>EXT</option></select>
                <select aria-label={L("Day/Night")} value={it.day_night} disabled={dis} onChange={(e) => updateItem(i, { day_night: e.target.value as "DAY" | "NIGHT" })}><option>DAY</option><option>NIGHT</option></select>
                <input className="mono pages" aria-label={L("Pages in eighths")} type="number" min={0} value={it.page_count_eighths} disabled={dis} onChange={(e) => updateItem(i, { page_count_eighths: Math.max(0, Number(e.target.value) || 0) })} />
                <span className="hint">/8</span>
              </div>
              <input className="set" aria-label={L("Set")} placeholder="RIVERBANK, TROJA. Marta finds the boat." value={it.set_description} disabled={dis} onChange={(e) => updateItem(i, { set_description: e.target.value })} />
              <select aria-label={L("Location")} value={it.location_id ?? ""} disabled={dis} onChange={(e) => updateItem(i, { location_id: e.target.value || null })}>
                <option value="">{L("— no location —")}</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
              {!dis && (
                <div className="item-actions">
                  <button type="button" className="quiet" onClick={() => moveItem(i, -1)} disabled={i === 0} aria-label={L("Move up")}>↑</button>
                  <button type="button" className="quiet" onClick={() => moveItem(i, 1)} disabled={i === draft.items.length - 1} aria-label={L("Move down")}>↓</button>
                  <button type="button" className="quiet danger" onClick={() => setDraft((d) => d ? { ...d, items: d.items.filter((_, j) => j !== i), dirtySincePublish: !!d.callSheetId } : d)}>{L("Remove")}</button>
                </div>
              )}
            </li>
          ))}
        </ol>
        {!dis && (
          <button type="button" id="addScene" className="secondary" onClick={() => setDraft((d) => d ? { ...d, items: [...d.items, { order_index: d.items.length + 1, scene_number: "", int_ext: "EXT", day_night: "DAY", set_description: "", location_id: null, page_count_eighths: 8 }] } : d)}>
            {L("+ Add scene")}
          </button>
        )}
      </section>

      <section className="publish" aria-label={L("Publish")}>
        {dayStatus === "cancelled" && (
          <div className="cancelled-banner" id="cancelledBanner" role="status">
            <strong>{L("CANCELLED")}</strong> — this day is off. The crew link says so.
            {!readOnly && <button type="button" className="quiet" id="restoreDay" disabled={busy} onClick={() => void restoreDay()}>{L("Restore the day")}</button>}
          </div>
        )}
        <div className="publish-state" id="publishState">
          {offline && L("Read-only while offline. Reconnect to publish.")}
          {!offline && !canPublish && L("Read-only: your role on this production can view but not publish.")}
          {!readOnly && !published && !planned && L("Not published yet. Your draft is saved on this phone.")}
          {!readOnly && planned && L("Planned day, not published: the crew cannot see it yet. Check it and publish to send REV A.")}
          {!readOnly && published && !draft.dirtySincePublish && L("REV {rev} is live.", { rev: draft.lastPublishedLetter! })}
          {!readOnly && published && draft.dirtySincePublish && L("Changes since REV {rev}. Publish to send REV {next}.", { rev: draft.lastPublishedLetter!, next: nextLetter(draft.lastPublishedLetter!) })}
        </div>
        <button id="publish" onClick={() => void publish()} disabled={busy || readOnly}>
          {busy ? L("Publishing…") : published ? L("Publish REV {rev}", { rev: nextLetter(draft.lastPublishedLetter!) }) : L("Publish")}
        </button>
        {planned && !readOnly && (
          <div className="inline">
            <button type="button" className="quiet danger" id="deleteDraftDay" disabled={busy} onClick={() => void deleteDraft()}>{L("Delete this planned day")}</button>
          </div>
        )}
        {published && seen && (
          <div className="seen" id="seenPanel">
            <div className="label">{L("REV {rev} opened by {seen} of {total}", { rev: seen.revision_letter, seen: seen.seen.length, total: seen.seen.length + seen.not_seen.length })}</div>
            {seen.not_seen.length === 0
              ? <p className="hint">{L("Everyone on the crew has opened it through their personal link.")}</p>
              : <ul className="chips" id="notSeen" aria-label={L("Not opened yet")}>
                  {seen.not_seen.map((e) => {
                    const number = whatsappNumber(e.phone);
                    const link = personalLink(conn.apiBase, e.personal_token);
                    const nudge = `Did you see REV ${seen.revision_letter} for Day ${draft.day_number}? Crew call ${draft.general_crew_call || "—"}. Your call sheet: ${link}`;
                    return (
                      <li key={e.crew_member_id} className="chip">
                        <span>{e.name}</span><span className="meta"> · {e.department}{e.subscribed ? ` ${L("· push on")}` : ""}</span>
                        {number && shareable && <a className="quiet-link whatsapp" href={whatsappUrl(number, nudge)} target="_blank" rel="noreferrer" aria-label={L("Nudge {name} on WhatsApp", { name: e.name })}>{L("nudge")}</a>}
                      </li>
                    );
                  })}
                </ul>}
            <p className="hint">{L("Counts a personal link opened live; a copy shown offline does not count. Refreshes every minute.")}</p>
          </div>
        )}
        {published && dayStatus !== "cancelled" && (
          <div className="actuals" id="actuals">
            <div className="label">{L("Actual times")}</div>
            <p className="hint">{L("After wrap: what really happened. For the production's records only; the crew's sheet does not change and nobody is notified.")}</p>
            <div className="actuals-grid">
              {([["first_shot", "First shot"], ["lunch_out", "Lunch out"], ["lunch_in", "Lunch in"], ["wrap", "Wrap"]] as const).map(([key, label]) => (
                <label key={key} className="field" htmlFor={`actual_${key}`}>
                  <span className="label">{L(label)}</span>
                  <input id={`actual_${key}`} className="mono" placeholder="19:40" value={actuals[key] ?? ""} disabled={readOnly || actualsBusy}
                    onChange={(e) => { setActuals({ ...actuals, [key]: e.target.value }); setActualsDirty(true); }} />
                </label>
              ))}
            </div>
            <label className="field" htmlFor="actual_note"><span className="label">{L("Note")}</span>
              <input id="actual_note" value={actuals.note ?? ""} disabled={readOnly || actualsBusy} placeholder={L("Rain from 15:00; lost the last two scenes")}
                onChange={(e) => { setActuals({ ...actuals, note: e.target.value }); setActualsDirty(true); }} />
            </label>
            {!readOnly && (
              <div className="inline">
                <button type="button" id="saveActuals" className="secondary" disabled={!actualsDirty || actualsBusy} onClick={() => void saveActuals()}>{actualsBusy ? L("Saving…") : L("Save actual times")}</button>
              </div>
            )}
          </div>
        )}
        {published && history.length > 0 && (
          <details className="history" id="historyPanel">
            <summary>{L("History")}</summary>
            <ul className="history-list" id="historyList">
              {[...history].reverse().map((h) => (
                <li key={h.revision_letter}>
                  <span className="rev">{L("REV {rev}", { rev: h.revision_letter })}</span>
                  {" · "}{new Date(h.created_at).toLocaleString()}
                  {" · "}{h.created_by}
                  {" · "}{L("{n} opened", { n: h.opened })}
                  {h.notifications && (
                    h.notifications.failed.length > 0
                      ? <>{" · "}{L("{delivered} of {attempted} notified, {failed} failed", { delivered: h.notifications.delivered, attempted: h.notifications.attempted, failed: h.notifications.failed.length })}</>
                      : <>{" · "}{L("{delivered} of {attempted} notified", { delivered: h.notifications.delivered, attempted: h.notifications.attempted })}</>
                  )}
                  {h.changes.length > 0 && (
                    <ul className="history-changes">
                      {h.changes.map((c) => (
                        <li key={c.field}>
                          <span className="k">{c.label}</span>{" "}
                          {c.before !== null ? <><s>{c.before}</s> → <b>{c.after ?? "—"}</b></> : <b>{c.after ?? "—"}</b>}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
        {published && !readOnly && dayStatus !== "cancelled" && (
          <div className="inline cancel-day" id="cancelDay">
            {!confirmCancel
              ? <button type="button" className="quiet danger" id="cancelDayBtn" disabled={busy} onClick={() => setConfirmCancel(true)}>{L("Cancel this day…")}</button>
              : <>
                  <span className="hint">{L("Every subscribed phone gets \"Day {n}: CANCELLED\". The sheet stays readable. Sure?", { n: draft.day_number })}</span>
                  <button type="button" className="quiet danger" id="confirmCancelDay" disabled={busy} onClick={() => void cancelDay()}>{L("Yes, cancel Day {n}", { n: draft.day_number })}</button>
                  <button type="button" className="quiet" onClick={() => setConfirmCancel(false)}>{L("Keep it")}</button>
                </>}
          </div>
        )}
        {published && !readOnly && (
          <div className="inline next-day" id="nextDay">
            {!nextDayClash
              ? <button type="button" className="secondary" id="startNextDay" onClick={() => void startNextDay(false)}>{L("Start Day {n} from this one", { n: draft.day_number + 1 })}</button>
              : <>
                  <span className="hint" id="nextDayClash">{L("An unpublished new day already exists on this phone.")}</span>
                  <button type="button" className="quiet danger" id="replaceNextDay" onClick={() => void startNextDay(true)}>{L("Replace it")}</button>
                  <button type="button" className="quiet" onClick={() => setNextDayClash(false)}>{L("Keep it")}</button>
                </>}
          </div>
        )}
        {published && (
          <div className="share">
            <div className="label">{L("Crew link")}</div>
            <a id="shareLink" href={crewLink(conn.apiBase, draft.callSheetId!)} target="_blank" rel="noreferrer">{crewLink(conn.apiBase, draft.callSheetId!)}</a>
            <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(crewLink(conn.apiBase, draft.callSheetId!))}>{L("Copy")}</button>
            <a className="quiet-link" id="pdfLink" href={`${crewLink(conn.apiBase, draft.callSheetId!)}&print=1`} target="_blank" rel="noreferrer">{L("PDF")}</a>
            <div className="inline share-text-actions">
              <button type="button" id="sendDayAsText" className="secondary" disabled={!shareable}
                onClick={() => void shareAsText(`Day ${draft.day_number}`, daySummaryText(draft, locations, crewLink(conn.apiBase, draft.callSheetId!), cast))}>
                {L("Send day as text")}
              </button>
              {shareable
                ? <a className="quiet-link" id="dayWhatsapp" href={whatsappUrl(null, daySummaryText(draft, locations, crewLink(conn.apiBase, draft.callSheetId!), cast))} target="_blank" rel="noreferrer">{L("Open in WhatsApp")}</a>
                : <span className="hint" id="shareTextHint">{L("Publish first so the text matches the link.")}</span>}
            </div>
            {shareText !== null && (
              <div className="share-preview">
                <textarea id="shareTextPreview" readOnly value={shareText} rows={8} aria-label={L("Message text")} onFocus={(e) => e.currentTarget.select()} />
                <button type="button" className="quiet" onClick={() => setShareText(null)}>{L("Close")}</button>
              </div>
            )}
            <div className="qr" id="shareQr">
              <QrCode value={crewLink(conn.apiBase, draft.callSheetId!)} />
              <span className="hint">{L("Scan to open the crew link")}</span>
            </div>
          </div>
        )}
        {published && crew.length > 0 && (
          <div className="share" id="personalLinks">
            <div className="label">{L("Personal links · one per person, for the whole shoot")}</div>
            <p className="hint">{L("Each link opens that person's next day with their own call. Send it once; every new day and revision shows up in it.")}</p>
            <ul className="list">
              {crew.map((m) => {
                const link = personalLink(conn.apiBase, m.personal_token);  // stable for the whole shoot (FR-32)
                const number = whatsappNumber(m.contact.phone);
                const message = () => personalMessageText(draft, m, locations, link);
                return (
                  <li key={m.id} className="row static">
                    <span className="name">{m.contact.name}<span className="meta"> · {m.department}</span></span>
                    <span className="row-actions">
                      <a className="quiet-link" href={link} target="_blank" rel="noreferrer">{L("Open")}</a>
                      <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(link)} aria-label={L("Copy link for {name}", { name: m.contact.name })}>{L("Copy")}</button>
                      {number && shareable
                        ? <a className="quiet-link whatsapp" href={whatsappUrl(number, message())} target="_blank" rel="noreferrer" aria-label={L("WhatsApp {name}", { name: m.contact.name })} data-number={number}>{L("WhatsApp")}</a>
                        : <button type="button" className="quiet" disabled={!shareable} onClick={() => void shareAsText(`Day ${draft.day_number} · ${m.contact.name}`, message())} aria-label={L("Send message to {name}", { name: m.contact.name })}>{L("Message")}</button>}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>
    </>
  );
}

function Field(props: { label: string; id: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; mono?: boolean; textarea?: boolean; disabled?: boolean }) {
  const { label, id, value, onChange, type = "text", placeholder, mono, textarea, disabled } = props;
  return (
    <label className="field" htmlFor={id}>
      <span className="label">{label}</span>
      {textarea
        ? <textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} rows={3} disabled={disabled} />
        : <input id={id} type={type} className={mono ? "mono" : undefined} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} inputMode={type === "number" ? "numeric" : undefined} disabled={disabled} />}
    </label>
  );
}
