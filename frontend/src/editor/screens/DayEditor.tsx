import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Connection } from "../api";
import { addDays, clearDraft, draftHasContent, draftKey, emptyDraft, loadDraft, nextDayFrom, saveDraft, type CastCallDraft, type Draft } from "../drafts";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import { crewLink, personalLink } from "./Production";
import { QrCode } from "./QrCode";
import { canWebShare, daySummaryText, personalMessageText, whatsappNumber, whatsappUrl } from "../shareText";
import type { CallSheetCreated, CastMember, CastStatus, CrewMember, Location, RevisionCreate, ScheduleItemCreate } from "../../types";

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
  const [dayStatus, setDayStatus] = useState<string | null>(null);  // FR-34: "cancelled" shows the banner and the restore button
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
          if (!cancelled) setDayStatus(sheet.status ?? "published");
          const fromServer = draftFromServer(productionId, productionName, sheet);
          // Keep unpublished local edits if they are newer than the last publish.
          const keepLocal = local && local.dirtySincePublish && local.lastPublishedLetter === fromServer.lastPublishedLetter;
          if (!cancelled) { setDraft(keepLocal ? local : fromServer); setReadOnly(false); }
        } catch (err) {
          if (cancelled) return;
          if (local) { setDraft(local); setReadOnly(true); setNotice({ kind: "warn", text: "Offline: showing the last copy on this phone. Reconnect to publish." }); }
          else { setDraft(null); setReadOnly(true); setNotice(noticeFromError(err, "Cannot load this day")); }
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
    if (!locationId) { setNotice({ kind: "warn", text: "Pick a location for the first scene to get a weather suggestion." }); return; }
    setSuggestingWeather(true);
    try {
      const { suggestion } = await api.weatherSuggestion(conn, productionId, locationId, draft.shoot_date);
      setWeatherSuggestion(suggestion ?? null);
      if (!suggestion) setNotice({ kind: "warn", text: "No weather suggestion available for that date/location." });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not get a weather suggestion"));
    } finally {
      setSuggestingWeather(false);
    }
  }

  async function publish() {
    if (!draft || readOnly) return;
    if (!draft.general_crew_call.trim()) { setNotice({ kind: "error", text: "Crew call is required; the crew wakes up for that number." }); return; }
    setBusy(true);
    try {
      if (!draft.callSheetId) {
        const created = await api.createCallSheet(conn, productionId, {
          shoot_date: draft.shoot_date, day_number: draft.day_number, day_count: draft.day_count, unit_name: draft.unit_name, initial_revision: revisionPayload(draft),
        });
        await clearDraft(key);
        const letter = created.current_revision?.revision_letter ?? "A";
        await saveDraft({ ...draft, id: draftKey(productionId, created.id), callSheetId: created.id, lastPublishedLetter: letter, publishedAt: new Date().toISOString(), dirtySincePublish: false });
        setNotice({ kind: "ok", text: `Published REV ${letter}. Everyone with the link sees it now.` });
        window.location.hash = href({ screen: "day", productionId, callSheetId: created.id });
      } else {
        const rev = await api.publishRevision(conn, draft.callSheetId, revisionPayload(draft));
        update({ lastPublishedLetter: rev.revision_letter, publishedAt: new Date().toISOString(), dirtySincePublish: false });
        setDayStatus("published");  // publishing puts a cancelled day back on
        setNotice({ kind: "ok", text: `Published REV ${rev.revision_letter}. Everyone with the link sees it now.` });
      }
    } catch (err) {
      setNotice(err instanceof ApiError && err.status === 0
        ? { kind: "warn", text: "No connection. Your draft is safe on this phone; publish when you are back in signal." }
        : noticeFromError(err, "Publish failed"));
    } finally {
      setBusy(false);
    }
  }

  /** FR-34: the day is off. Nothing is deleted; the sheet says CANCELLED and every subscriber is told. */
  async function cancelDay() {
    if (!draft?.callSheetId) return;
    setBusy(true);
    try {
      const sheet = await api.cancelCallSheet(conn, draft.callSheetId);
      setDayStatus("cancelled"); setConfirmCancel(false);
      const n = sheet.current_revision?.notifications;
      setNotice({ kind: "ok", text: `Day ${draft.day_number} cancelled.${n ? ` Told ${n.delivered} of ${n.attempted} subscribed phones.` : ""} The sheet now says so; the link still works.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not cancel the day"));
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
      setNotice({ kind: "warn", text: `Day ${draft.day_number} is back on. Publish a revision so the crew gets told.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not restore the day"));
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
    setNotice({ kind: "ok", text: `Day ${draft.day_number + 1} started from Day ${draft.day_number}. Change the date and scenes, then publish.` });
    window.location.hash = href({ screen: "day", productionId, callSheetId: null });
  }

  /** Phone share sheet (WhatsApp is one tap away) when the browser has one; otherwise copy and show the text with a wa.me link. */
  async function shareAsText(title: string, text: string) {
    if (canWebShare()) {
      try { await navigator.share({ title, text }); return; }
      catch (err) { if ((err as { name?: string }).name === "AbortError") return; }
    }
    try { await navigator.clipboard?.writeText(text); setNotice({ kind: "ok", text: "Copied. Paste it into the WhatsApp group." }); }
    catch { setNotice({ kind: "warn", text: "Could not copy; select the text below." }); }
    setShareText(text);
  }

  if (!draft) return <div className="skeleton" aria-hidden="true"><i /><i /><i /></div>;
  const published = draft.callSheetId && draft.lastPublishedLetter;
  // The message must say what the link says: with unpublished edits the text would lie (FR-29 dod).
  const shareable = !!published && !draft.dirtySincePublish;
  const dis = readOnly;

  return (
    <>
      <section className="block" aria-label="Shoot day">
        <h2>Shoot day</h2>
        <div className="grid2">
          <Field label="Date" id="shoot_date" type="date" value={draft.shoot_date} onChange={(v) => update({ shoot_date: v })} disabled={dis || !!draft.callSheetId} />
          <Field label="Unit" id="unit_name" value={draft.unit_name} onChange={(v) => update({ unit_name: v })} disabled={dis || !!draft.callSheetId} />
          <Field label="Day" id="day_number" type="number" value={String(draft.day_number)} onChange={(v) => update({ day_number: Math.max(1, Number(v) || 1) })} disabled={dis || !!draft.callSheetId} />
          <Field label="of" id="day_count" type="number" value={String(draft.day_count)} onChange={(v) => update({ day_count: Math.max(1, Number(v) || 1) })} disabled={dis || !!draft.callSheetId} />
        </div>
        {draft.callSheetId && <p className="hint">Date, unit and day number are fixed once published; times, notes and scenes change through revisions.</p>}
      </section>

      <section className="block" aria-label="Calls">
        <h2>Calls</h2>
        <div className="grid2">
          <Field label="Crew call" id="general_crew_call" placeholder="06:30" mono value={draft.general_crew_call} onChange={(v) => update({ general_crew_call: v })} disabled={dis} />
          <Field label="Shooting call" id="shooting_call" placeholder="07:30" mono value={draft.shooting_call} onChange={(v) => update({ shooting_call: v })} disabled={dis} />
          <Field label="Sunrise" id="sunrise" placeholder="06:41" mono value={draft.sunrise} onChange={(v) => update({ sunrise: v })} disabled={dis} />
          <Field label="Sunset" id="sunset" placeholder="19:03" mono value={draft.sunset} onChange={(v) => update({ sunset: v })} disabled={dis} />
        </div>
        <Field label="Weather" id="weather_forecast" value={draft.weather_forecast} onChange={(v) => update({ weather_forecast: v })} disabled={dis} />
        {!dis && (
          <div className="inline">
            <button type="button" className="quiet" disabled={suggestingWeather} onClick={() => void suggestWeather()}>
              {suggestingWeather ? "Looking…" : "Suggest weather"}
            </button>
            {weatherSuggestion && (
              <button type="button" className="quiet" onClick={() => { update({ weather_forecast: weatherSuggestion }); setWeatherSuggestion(null); }}>
                Use: {weatherSuggestion}
              </button>
            )}
          </div>
        )}
        <p className="hint" id="sunHint" data-state={sunState}>
          {sunState === "none" && (locations.length === 0
            ? <>Add a location to this day to get sunrise, sunset, weather and the nearest hospital. <a href={href({ screen: "production", productionId, tab: "locations" })}>Locations</a></>
            : <>Pick a location on a scene below to get sunrise, sunset, weather and the nearest hospital. No location yet? <a href={href({ screen: "production", productionId, tab: "locations" })}>Locations</a></>)}
          {sunState === "filled" && <>Sunrise and sunset come from the first scene's location; edit them if you know better.</>}
          {sunState === "no-coords" && <>That location has no map position, so sunrise and sunset cannot be computed; type them, or add an address under <a href={href({ screen: "production", productionId, tab: "locations" })}>Locations</a>.</>}
          {sunState === "failed" && <>Could not fetch suggestions; type sunrise and sunset yourself.</>}
        </p>
        <Field label="Safety notes" id="safety_notes" textarea value={draft.safety_notes} onChange={(v) => update({ safety_notes: v })} disabled={dis} />
        <label className="field" htmlFor="headOfDay">
          <span className="label">Head of day</span>
          <select id="headOfDay" value={draft.headOfDayId ?? ""} onChange={(e) => update({ headOfDayId: e.target.value || null })} disabled={dis}>
            <option value="">— not set —</option>
            {crew.map((m) => <option key={m.id} value={m.id}>{m.contact.name} · {m.position}{m.is_head_of_department ? " (HoD)" : ""}</option>)}
          </select>
          {crew.length === 0 && <span className="hint">Add crew under the Crew tab to pick who runs the day.</span>}
        </label>
      </section>

      <section className="block" aria-label="Personal calls">
        <h2>Personal calls</h2>
        <p className="hint">Only for people whose call differs from the crew call today. Empty means the general call (or their standing time). Carried over to the next revision.</p>
        {crew.length === 0 && <p className="hint">Add crew under the Crew tab first.</p>}
        <ul className="items" id="personalCalls">
          {crew.map((m) => {
            const v = draft.crewCalls?.[m.id] ?? { call: "", pickup: "", note: "" };
            const set = (patch: Partial<typeof v>) => update({ crewCalls: { ...(draft.crewCalls ?? {}), [m.id]: { ...v, ...patch } } });
            return (
              <li key={m.id} className="item pcall">
                <div className="pcall-who"><span className="name">{m.contact.name}</span><span className="meta"> · {m.department} · {m.position}{m.standard_call_time ? ` · usually ${m.standard_call_time}` : ""}</span></div>
                <div className="pcall-row">
                  <input className="mono" aria-label={`Call for ${m.contact.name}`} placeholder="call" value={v.call} disabled={dis} onChange={(e) => set({ call: e.target.value })} />
                  <input className="mono" aria-label={`Pickup for ${m.contact.name}`} placeholder="pickup" value={v.pickup} disabled={dis} onChange={(e) => set({ pickup: e.target.value })} />
                  <input aria-label={`Note for ${m.contact.name}`} placeholder="note" value={v.note} disabled={dis} onChange={(e) => set({ note: e.target.value })} />
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      {cast.length > 0 && (
        <section className="block" aria-label="Cast calls">
          <h2>Cast</h2>
          <p className="hint">Tick who works today and set their times. W work · SW start · WF finish · SWF start and finish · H hold · R rehearsal. Carried over to the next revision.</p>
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
                    <label className="check"><input type="checkbox" aria-label={`${a.contact.name} works today`} checked={!!v} disabled={dis} onChange={(e) => (e.target.checked ? setEntry({}) : clear())} /> <span className="name">{a.contact.name}</span></label>
                    <span className="meta"> · {a.character_name}</span>
                  </div>
                  {v && (
                    <div className="pcall-row cast-row">
                      <select aria-label={`Status for ${a.contact.name}`} value={v.status} disabled={dis} onChange={(e) => setEntry({ status: e.target.value as CastStatus })}>
                        {(["W", "SW", "WF", "SWF", "H", "R"] as CastStatus[]).map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <input className="mono" aria-label={`Pickup for ${a.contact.name}`} placeholder="pickup" value={v.pickup} disabled={dis} onChange={(e) => setEntry({ pickup: e.target.value })} />
                      <input className="mono" aria-label={`Call for ${a.contact.name}`} placeholder="call" value={v.call} disabled={dis} onChange={(e) => setEntry({ call: e.target.value })} />
                      <input className="mono" aria-label={`Make-up for ${a.contact.name}`} placeholder="M/H" value={v.makeup} disabled={dis} onChange={(e) => setEntry({ makeup: e.target.value })} />
                      <input className="mono" aria-label={`On set for ${a.contact.name}`} placeholder="on set" value={v.onSet} disabled={dis} onChange={(e) => setEntry({ onSet: e.target.value })} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="block" aria-label="Schedule">
        <h2>Schedule</h2>
        {draft.items.length === 0 && <p className="hint">No scenes yet. Add the first one; order is the shooting order.</p>}
        <ol className="items" id="items">
          {draft.items.map((it, i) => (
            <li key={i} className="item">
              <div className="item-row">
                <input className="mono scene" aria-label="Scene" placeholder="42" value={it.scene_number} disabled={dis} onChange={(e) => updateItem(i, { scene_number: e.target.value })} />
                <select aria-label="Int/Ext" value={it.int_ext} disabled={dis} onChange={(e) => updateItem(i, { int_ext: e.target.value as "INT" | "EXT" })}><option>INT</option><option>EXT</option></select>
                <select aria-label="Day/Night" value={it.day_night} disabled={dis} onChange={(e) => updateItem(i, { day_night: e.target.value as "DAY" | "NIGHT" })}><option>DAY</option><option>NIGHT</option></select>
                <input className="mono pages" aria-label="Pages in eighths" type="number" min={0} value={it.page_count_eighths} disabled={dis} onChange={(e) => updateItem(i, { page_count_eighths: Math.max(0, Number(e.target.value) || 0) })} />
                <span className="hint">/8</span>
              </div>
              <input className="set" aria-label="Set" placeholder="RIVERBANK, TROJA. Marta finds the boat." value={it.set_description} disabled={dis} onChange={(e) => updateItem(i, { set_description: e.target.value })} />
              <select aria-label="Location" value={it.location_id ?? ""} disabled={dis} onChange={(e) => updateItem(i, { location_id: e.target.value || null })}>
                <option value="">— no location —</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
              {!dis && (
                <div className="item-actions">
                  <button type="button" className="quiet" onClick={() => moveItem(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
                  <button type="button" className="quiet" onClick={() => moveItem(i, 1)} disabled={i === draft.items.length - 1} aria-label="Move down">↓</button>
                  <button type="button" className="quiet danger" onClick={() => setDraft((d) => d ? { ...d, items: d.items.filter((_, j) => j !== i), dirtySincePublish: !!d.callSheetId } : d)}>Remove</button>
                </div>
              )}
            </li>
          ))}
        </ol>
        {!dis && (
          <button type="button" id="addScene" className="secondary" onClick={() => setDraft((d) => d ? { ...d, items: [...d.items, { order_index: d.items.length + 1, scene_number: "", int_ext: "EXT", day_night: "DAY", set_description: "", location_id: null, page_count_eighths: 8 }] } : d)}>
            + Add scene
          </button>
        )}
      </section>

      <section className="publish" aria-label="Publish">
        {dayStatus === "cancelled" && (
          <div className="cancelled-banner" id="cancelledBanner" role="status">
            <strong>CANCELLED</strong> — this day is off. The crew link says so.
            {!readOnly && <button type="button" className="quiet" id="restoreDay" disabled={busy} onClick={() => void restoreDay()}>Restore the day</button>}
          </div>
        )}
        <div className="publish-state" id="publishState">
          {offline && "Read-only while offline. Reconnect to publish."}
          {!offline && !canPublish && "Read-only: your role on this production can view but not publish."}
          {!readOnly && !published && "Not published yet. Your draft is saved on this phone."}
          {!readOnly && published && !draft.dirtySincePublish && `REV ${draft.lastPublishedLetter} is live.`}
          {!readOnly && published && draft.dirtySincePublish && `Changes since REV ${draft.lastPublishedLetter}. Publish to send REV ${nextLetter(draft.lastPublishedLetter!)}.`}
        </div>
        <button id="publish" onClick={() => void publish()} disabled={busy || readOnly}>
          {busy ? "Publishing…" : published ? `Publish REV ${nextLetter(draft.lastPublishedLetter!)}` : "Publish"}
        </button>
        {published && !readOnly && dayStatus !== "cancelled" && (
          <div className="inline cancel-day" id="cancelDay">
            {!confirmCancel
              ? <button type="button" className="quiet danger" id="cancelDayBtn" disabled={busy} onClick={() => setConfirmCancel(true)}>Cancel this day…</button>
              : <>
                  <span className="hint">Every subscribed phone gets "Day {draft.day_number}: CANCELLED". The sheet stays readable. Sure?</span>
                  <button type="button" className="quiet danger" id="confirmCancelDay" disabled={busy} onClick={() => void cancelDay()}>Yes, cancel Day {draft.day_number}</button>
                  <button type="button" className="quiet" onClick={() => setConfirmCancel(false)}>Keep it</button>
                </>}
          </div>
        )}
        {published && !readOnly && (
          <div className="inline next-day" id="nextDay">
            {!nextDayClash
              ? <button type="button" className="secondary" id="startNextDay" onClick={() => void startNextDay(false)}>Start Day {draft.day_number + 1} from this one</button>
              : <>
                  <span className="hint" id="nextDayClash">An unpublished new day already exists on this phone.</span>
                  <button type="button" className="quiet danger" id="replaceNextDay" onClick={() => void startNextDay(true)}>Replace it</button>
                  <button type="button" className="quiet" onClick={() => setNextDayClash(false)}>Keep it</button>
                </>}
          </div>
        )}
        {published && (
          <div className="share">
            <div className="label">Crew link</div>
            <a id="shareLink" href={crewLink(conn.apiBase, draft.callSheetId!)} target="_blank" rel="noreferrer">{crewLink(conn.apiBase, draft.callSheetId!)}</a>
            <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(crewLink(conn.apiBase, draft.callSheetId!))}>Copy</button>
            <div className="inline share-text-actions">
              <button type="button" id="sendDayAsText" className="secondary" disabled={!shareable}
                onClick={() => void shareAsText(`Day ${draft.day_number}`, daySummaryText(draft, locations, crewLink(conn.apiBase, draft.callSheetId!)))}>
                Send day as text
              </button>
              {shareable
                ? <a className="quiet-link" id="dayWhatsapp" href={whatsappUrl(null, daySummaryText(draft, locations, crewLink(conn.apiBase, draft.callSheetId!)))} target="_blank" rel="noreferrer">Open in WhatsApp</a>
                : <span className="hint" id="shareTextHint">Publish first so the text matches the link.</span>}
            </div>
            {shareText !== null && (
              <div className="share-preview">
                <textarea id="shareTextPreview" readOnly value={shareText} rows={8} aria-label="Message text" onFocus={(e) => e.currentTarget.select()} />
                <button type="button" className="quiet" onClick={() => setShareText(null)}>Close</button>
              </div>
            )}
            <div className="qr" id="shareQr">
              <QrCode value={crewLink(conn.apiBase, draft.callSheetId!)} />
              <span className="hint">Scan to open the crew link</span>
            </div>
          </div>
        )}
        {published && crew.length > 0 && (
          <div className="share" id="personalLinks">
            <div className="label">Personal links · one per person, for the whole shoot</div>
            <p className="hint">Each link opens that person's next day with their own call. Send it once; every new day and revision shows up in it.</p>
            <ul className="list">
              {crew.map((m) => {
                const link = personalLink(conn.apiBase, m.personal_token);  // stable for the whole shoot (FR-32)
                const number = whatsappNumber(m.contact.phone);
                const message = () => personalMessageText(draft, m, locations, link);
                return (
                  <li key={m.id} className="row static">
                    <span className="name">{m.contact.name}<span className="meta"> · {m.department}</span></span>
                    <span className="row-actions">
                      <a className="quiet-link" href={link} target="_blank" rel="noreferrer">Open</a>
                      <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(link)} aria-label={`Copy link for ${m.contact.name}`}>Copy</button>
                      {number && shareable
                        ? <a className="quiet-link whatsapp" href={whatsappUrl(number, message())} target="_blank" rel="noreferrer" aria-label={`WhatsApp ${m.contact.name}`} data-number={number}>WhatsApp</a>
                        : <button type="button" className="quiet" disabled={!shareable} onClick={() => void shareAsText(`Day ${draft.day_number} · ${m.contact.name}`, message())} aria-label={`Send message to ${m.contact.name}`}>Message</button>}
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
