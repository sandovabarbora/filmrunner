import { useEffect, useRef, useState } from "react";
import { api, ApiError, loadConnection, saveConnection, type Connection } from "./api";
import { clearDraft, emptyDraft, loadDraft, saveDraft, type Draft } from "./drafts";
import type { Production, RevisionCreate, ScheduleItemCreate } from "../types";

type Notice = { kind: "ok" | "warn" | "error"; text: string } | null;

function viewerLink(apiBase: string, sheetId: string): string {
  const base = window.location.href.replace(/editor\.html.*$/, "");
  return `${base}?sheet=${sheetId}&api=${encodeURIComponent(apiBase.replace(/\/$/, ""))}`;
}

function revisionPayload(d: Draft): RevisionCreate {
  const clean = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    general_crew_call: clean(d.general_crew_call),
    shooting_call: clean(d.shooting_call),
    sunrise: clean(d.sunrise),
    sunset: clean(d.sunset),
    weather_forecast: clean(d.weather_forecast),
    safety_notes: clean(d.safety_notes),
    created_by: "editor",
    schedule_items: d.items.map((it, i) => ({ ...it, order_index: i + 1 })),
  };
}

export function EditorApp() {
  const [conn, setConn] = useState<Connection | null>(loadConnection);
  const [productions, setProductions] = useState<Production[] | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const latest = useRef<Draft | null>(null);

  // Load the draft once; save on every change, no debounce: an AD closes
  // the app the moment they finish typing, and IndexedDB writes are cheap.
  useEffect(() => {
    loadDraft().then((d) => setDraft(d ?? emptyDraft())).catch(() => setDraft(emptyDraft()));
  }, []);
  useEffect(() => {
    latest.current = draft;
    if (draft) void saveDraft(draft);
  }, [draft]);
  useEffect(() => {
    const flush = () => { if (latest.current) void saveDraft(latest.current); };
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  // Verify the connection and list productions whenever it changes.
  useEffect(() => {
    if (!conn) { setProductions(null); return; }
    api.listProductions(conn)
      .then(setProductions)
      .catch((err: unknown) => {
        setProductions(null);
        setNotice({ kind: "error", text: err instanceof ApiError && err.status === 401 ? "The token was rejected. Check it and connect again." : `Cannot reach the API: ${(err as Error).message}` });
      });
  }, [conn]);

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

  async function publish() {
    if (!conn || !draft) return;
    if (!draft.productionId) { setNotice({ kind: "error", text: "Pick or create a production first." }); return; }
    if (!draft.general_crew_call.trim()) { setNotice({ kind: "error", text: "Crew call is required; the crew wakes up for that number." }); return; }
    setBusy(true);
    setNotice(null);
    try {
      let sheetId = draft.callSheetId;
      let letter: string;
      if (!sheetId) {
        const created = await api.createCallSheet(conn, draft.productionId, {
          shoot_date: draft.shoot_date, day_number: draft.day_number, day_count: draft.day_count,
          unit_name: draft.unit_name, initial_revision: revisionPayload(draft),
        });
        sheetId = created.id;
        letter = created.current_revision?.revision_letter ?? "A";
      } else {
        const rev = await api.publishRevision(conn, sheetId, revisionPayload(draft));
        letter = rev.revision_letter;
      }
      update({ callSheetId: sheetId, lastPublishedLetter: letter, publishedAt: new Date().toISOString(), dirtySincePublish: false });
      setNotice({ kind: "ok", text: `Published REV ${letter}. Everyone with the link sees it now.` });
    } catch (err) {
      const msg = err instanceof ApiError ? (err.status === 0 ? "No connection. Your draft is safe on this phone; publish when you are back in signal." : `Publish failed: ${err.message}`) : String(err);
      setNotice({ kind: "error", text: msg });
    } finally {
      setBusy(false);
    }
  }

  async function newDay() {
    await clearDraft();
    setDraft({ ...emptyDraft(), productionId: draft?.productionId ?? null, productionName: draft?.productionName ?? null });
    setNotice(null);
  }

  if (!conn) return <Connect onConnect={(c) => { saveConnection(c); setConn(c); }} />;
  if (!draft) return <div className="wrap"><div className="skeleton" aria-hidden="true"><i /><i /><i /></div></div>;

  const published = draft.callSheetId && draft.lastPublishedLetter;

  return (
    <div className="wrap">
      <header className="masthead">
        <h1>FilmRunner</h1>
        <p className="sub">Editor · <button className="linklike" onClick={() => { saveConnection(null); setConn(null); }}>disconnect</button></p>
      </header>

      {notice && <div id="notice" className={`status ${notice.kind === "ok" ? "online" : notice.kind === "warn" ? "offline" : "error"}`} role="status">{notice.text}</div>}

      <section className="block" aria-label="Production">
        <h2>Production</h2>
        <ProductionPicker
          productions={productions}
          selectedId={draft.productionId}
          onPick={(p) => update({ productionId: p.id, productionName: p.name })}
          onCreate={async (name) => {
            try {
              const p = await api.createProduction(conn, name);
              setProductions((ps) => [...(ps ?? []), p]);
              update({ productionId: p.id, productionName: p.name });
            } catch (err) { setNotice({ kind: "error", text: `Could not create the production: ${(err as Error).message}` }); }
          }}
        />
      </section>

      <section className="block" aria-label="Shoot day">
        <h2>Shoot day</h2>
        <div className="grid2">
          <Field label="Date" id="shoot_date" type="date" value={draft.shoot_date} onChange={(v) => update({ shoot_date: v })} />
          <Field label="Unit" id="unit_name" value={draft.unit_name} onChange={(v) => update({ unit_name: v })} />
          <Field label="Day" id="day_number" type="number" value={String(draft.day_number)} onChange={(v) => update({ day_number: Math.max(1, Number(v) || 1) })} />
          <Field label="of" id="day_count" type="number" value={String(draft.day_count)} onChange={(v) => update({ day_count: Math.max(1, Number(v) || 1) })} />
        </div>
      </section>

      <section className="block" aria-label="Calls">
        <h2>Calls</h2>
        <div className="grid2">
          <Field label="Crew call" id="general_crew_call" placeholder="06:30" mono value={draft.general_crew_call} onChange={(v) => update({ general_crew_call: v })} />
          <Field label="Shooting call" id="shooting_call" placeholder="07:30" mono value={draft.shooting_call} onChange={(v) => update({ shooting_call: v })} />
          <Field label="Sunrise" id="sunrise" placeholder="06:41" mono value={draft.sunrise} onChange={(v) => update({ sunrise: v })} />
          <Field label="Sunset" id="sunset" placeholder="19:03" mono value={draft.sunset} onChange={(v) => update({ sunset: v })} />
        </div>
        <Field label="Weather" id="weather_forecast" value={draft.weather_forecast} onChange={(v) => update({ weather_forecast: v })} />
        <Field label="Safety notes" id="safety_notes" textarea value={draft.safety_notes} onChange={(v) => update({ safety_notes: v })} />
      </section>

      <section className="block" aria-label="Schedule">
        <h2>Schedule</h2>
        {draft.items.length === 0 && <p className="hint">No scenes yet. Add the first one; order is the shooting order.</p>}
        <ol className="items" id="items">
          {draft.items.map((it, i) => (
            <li key={i} className="item">
              <div className="item-row">
                <input className="mono scene" aria-label="Scene" placeholder="42" value={it.scene_number} onChange={(e) => updateItem(i, { scene_number: e.target.value })} />
                <select aria-label="Int/Ext" value={it.int_ext} onChange={(e) => updateItem(i, { int_ext: e.target.value as "INT" | "EXT" })}>
                  <option>INT</option><option>EXT</option>
                </select>
                <select aria-label="Day/Night" value={it.day_night} onChange={(e) => updateItem(i, { day_night: e.target.value as "DAY" | "NIGHT" })}>
                  <option>DAY</option><option>NIGHT</option>
                </select>
                <input className="mono pages" aria-label="Pages in eighths" type="number" min={0} value={it.page_count_eighths} onChange={(e) => updateItem(i, { page_count_eighths: Math.max(0, Number(e.target.value) || 0) })} />
                <span className="hint">/8</span>
              </div>
              <input className="set" aria-label="Set" placeholder="RIVERBANK, TROJA. Marta finds the boat." value={it.set_description} onChange={(e) => updateItem(i, { set_description: e.target.value })} />
              <div className="item-actions">
                <button type="button" className="quiet" onClick={() => moveItem(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
                <button type="button" className="quiet" onClick={() => moveItem(i, 1)} disabled={i === draft.items.length - 1} aria-label="Move down">↓</button>
                <button type="button" className="quiet danger" onClick={() => setDraft((d) => d ? { ...d, items: d.items.filter((_, j) => j !== i), dirtySincePublish: !!d.callSheetId } : d)}>Remove</button>
              </div>
            </li>
          ))}
        </ol>
        <button type="button" id="addScene" className="secondary" onClick={() => setDraft((d) => d ? { ...d, items: [...d.items, { order_index: d.items.length + 1, scene_number: "", int_ext: "EXT", day_night: "DAY", set_description: "", page_count_eighths: 8 }] } : d)}>
          + Add scene
        </button>
      </section>

      <section className="publish" aria-label="Publish">
        <div className="publish-state" id="publishState">
          {!published && "Not published yet. Your draft is saved on this phone."}
          {published && !draft.dirtySincePublish && `REV ${draft.lastPublishedLetter} is live.`}
          {published && draft.dirtySincePublish && `Changes since REV ${draft.lastPublishedLetter}. Publish to send REV ${nextLetter(draft.lastPublishedLetter!)}.`}
        </div>
        <button id="publish" onClick={() => void publish()} disabled={busy}>
          {busy ? "Publishing…" : published ? `Publish REV ${nextLetter(draft.lastPublishedLetter!)}` : "Publish"}
        </button>
        {published && (
          <div className="share">
            <div className="label">Crew link</div>
            <a id="shareLink" href={viewerLink(conn.apiBase, draft.callSheetId!)} target="_blank" rel="noreferrer">{viewerLink(conn.apiBase, draft.callSheetId!)}</a>
            <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(viewerLink(conn.apiBase, draft.callSheetId!))}>Copy</button>
          </div>
        )}
        <button type="button" className="quiet" onClick={() => void newDay()}>Start a new day</button>
        <p className="hint">Connected with a shared token (temporary until sign-in lands).</p>
      </section>
    </div>
  );
}

function nextLetter(letter: string): string {
  return String.fromCharCode(letter.charCodeAt(0) + 1);
}

function Field(props: { label: string; id: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; mono?: boolean; textarea?: boolean }) {
  const { label, id, value, onChange, type = "text", placeholder, mono, textarea } = props;
  return (
    <label className="field" htmlFor={id}>
      <span className="label">{label}</span>
      {textarea
        ? <textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} rows={3} />
        : <input id={id} type={type} className={mono ? "mono" : undefined} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} inputMode={type === "number" ? "numeric" : undefined} />}
    </label>
  );
}

function ProductionPicker({ productions, selectedId, onPick, onCreate }: { productions: Production[] | null; selectedId: string | null; onPick: (p: Production) => void; onCreate: (name: string) => Promise<void> }) {
  const [name, setName] = useState("");
  if (productions === null) return <p className="hint">Loading productions…</p>;
  return (
    <div>
      {productions.length > 0 && (
        <select id="production" aria-label="Production" value={selectedId ?? ""} onChange={(e) => { const p = productions.find((x) => x.id === e.target.value); if (p) onPick(p); }}>
          <option value="" disabled>Choose a production</option>
          {productions.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}
      <div className="inline">
        <input id="newProduction" placeholder="New production name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" id="createProduction" className="secondary" disabled={!name.trim()} onClick={() => { void onCreate(name.trim()); setName(""); }}>Create</button>
      </div>
    </div>
  );
}

function Connect({ onConnect }: { onConnect: (c: Connection) => void }) {
  const [apiBase, setApiBase] = useState("https://filmrunner-api.fly.dev");
  const [token, setToken] = useState("");
  return (
    <div className="wrap">
      <header className="masthead"><h1>FilmRunner</h1><p className="sub">Editor</p></header>
      <section className="block" aria-label="Connect">
        <h2>Connect</h2>
        <p className="hint">Temporary until sign-in lands: paste the API token once; it stays on this phone.</p>
        <Field label="API" id="apiBase" value={apiBase} onChange={setApiBase} />
        <Field label="Token" id="token" type="password" value={token} onChange={setToken} />
        <button id="connect" disabled={!token.trim() || !apiBase.trim()} onClick={() => onConnect({ apiBase: apiBase.trim(), token: token.trim() })}>Connect</button>
      </section>
    </div>
  );
}
