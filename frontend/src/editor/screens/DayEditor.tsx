import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Connection } from "../api";
import { clearDraft, draftKey, emptyDraft, loadDraft, saveDraft, type Draft } from "../drafts";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import { crewLink } from "./Production";
import { QrCode } from "./QrCode";
import type { CallSheetCreated, CrewMember, Location, RevisionCreate, ScheduleItemCreate } from "../../types";

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
  const [weatherSuggestion, setWeatherSuggestion] = useState<string | null>(null);
  const [suggestingWeather, setSuggestingWeather] = useState(false);
  const [busy, setBusy] = useState(false);
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
        setDraft(local ?? emptyDraft(productionId, productionName));
        setReadOnly(false);
      }
    })();
    api.listCrew(conn, productionId).then((c) => { if (!cancelled) setCrew(c); }).catch(() => undefined);
    api.listLocations(conn, productionId).then((l) => { if (!cancelled) setLocations(l); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [conn, productionId, productionName, callSheetId, key, setNotice]);

  useEffect(() => { latest.current = draft; if (draft) void saveDraft(draft); }, [draft]);
  useEffect(() => {
    const flush = () => { if (latest.current) void saveDraft(latest.current); };
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  function update(patch: Partial<Draft>) {
    setDraft((d) => (d ? { ...d, ...patch, dirtySincePublish: d.callSheetId ? true : d.dirtySincePublish } : d));
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

  if (!draft) return <div className="skeleton" aria-hidden="true"><i /><i /><i /></div>;
  const published = draft.callSheetId && draft.lastPublishedLetter;
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
        <p className="hint">Sunrise and sunset fill in automatically from the first scene's location when left blank on publish.</p>
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
        {published && (
          <div className="share">
            <div className="label">Crew link</div>
            <a id="shareLink" href={crewLink(conn.apiBase, draft.callSheetId!)} target="_blank" rel="noreferrer">{crewLink(conn.apiBase, draft.callSheetId!)}</a>
            <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(crewLink(conn.apiBase, draft.callSheetId!))}>Copy</button>
            <div className="qr" id="shareQr">
              <QrCode value={crewLink(conn.apiBase, draft.callSheetId!)} />
              <span className="hint">Scan to open the crew link</span>
            </div>
          </div>
        )}
        {published && crew.length > 0 && (
          <div className="share" id="personalLinks">
            <div className="label">Personal links · one per crew member</div>
            <ul className="list">
              {crew.map((m) => {
                const link = `${crewLink(conn.apiBase, draft.callSheetId!)}&me=${encodeURIComponent(m.personal_token)}`;
                return (
                  <li key={m.id} className="row static">
                    <span className="name">{m.contact.name}<span className="meta"> · {m.department}</span></span>
                    <span className="row-actions">
                      <a className="quiet-link" href={link} target="_blank" rel="noreferrer">Open</a>
                      <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(link)} aria-label={`Copy link for ${m.contact.name}`}>Copy</button>
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
