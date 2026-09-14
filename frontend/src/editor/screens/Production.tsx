import { useEffect, useState } from "react";
import { api, type Connection } from "../api";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import type { CallSheetCreated, CrewMember, Production } from "../../types";

export function crewLink(apiBase: string, sheetId: string): string {
  const base = window.location.href.replace(/editor\.html.*$/, "");
  return `${base}?sheet=${sheetId}&api=${encodeURIComponent(apiBase.replace(/\/$/, ""))}`;
}

export function ProductionScreen({ conn, productionId, production, tab, setNotice }: {
  conn: Connection; productionId: string; production: Production | null; tab: "days" | "crew"; setNotice: (n: Notice) => void;
}) {
  return (
    <>
      <div className="tabs" role="tablist">
        <a role="tab" aria-selected={tab === "days"} className={tab === "days" ? "on" : ""} href={href({ screen: "production", productionId, tab: "days" })}>Days</a>
        <a role="tab" aria-selected={tab === "crew"} className={tab === "crew" ? "on" : ""} href={href({ screen: "production", productionId, tab: "crew" })}>Crew</a>
      </div>
      {tab === "days" ? <Days conn={conn} productionId={productionId} setNotice={setNotice} /> : <Crew conn={conn} productionId={productionId} setNotice={setNotice} />}
      {production === null && <p className="hint">Production not found in this list; go back to Productions.</p>}
    </>
  );
}

function Days({ conn, productionId, setNotice }: { conn: Connection; productionId: string; setNotice: (n: Notice) => void }) {
  const [days, setDays] = useState<CallSheetCreated[] | null>(null);
  useEffect(() => {
    api.listCallSheets(conn, productionId).then(setDays).catch((err: unknown) => { setDays([]); setNotice(noticeFromError(err, "Cannot load days")); });
  }, [conn, productionId, setNotice]);

  return (
    <section className="block" aria-label="Days">
      <h2>Days</h2>
      {days === null && <p className="hint">Loading…</p>}
      {days && days.length === 0 && <p className="hint">No shoot days yet.</p>}
      {days && days.length > 0 && (
        <ul className="list" id="days">
          {days.map((d) => (
            <li key={d.id}>
              <a className="row" href={href({ screen: "day", productionId, callSheetId: d.id })}>
                <span className="name">Day {d.day_number} of {d.day_count} <span className="meta">· {d.shoot_date} · {d.unit_name}</span></span>
                <span className="rev-badge small" data-rev={d.current_revision?.revision_letter ?? "A"}>REV {d.current_revision?.revision_letter ?? "–"}</span>
              </a>
              <div className="row-actions">
                <a className="quiet-link" href={crewLink(conn.apiBase, d.id)} target="_blank" rel="noreferrer">Crew link</a>
                <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(crewLink(conn.apiBase, d.id))}>Copy</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <a className="button" id="newDay" href={href({ screen: "day", productionId, callSheetId: null })}>+ New day</a>
    </section>
  );
}

function Crew({ conn, productionId, setNotice }: { conn: Connection; productionId: string; setNotice: (n: Notice) => void }) {
  const [crew, setCrew] = useState<CrewMember[] | null>(null);
  const [form, setForm] = useState({ name: "", phone: "", department: "", position: "", hod: false });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listCrew(conn, productionId).then(setCrew).catch((err: unknown) => { setCrew([]); setNotice(noticeFromError(err, "Cannot load crew")); });
  }, [conn, productionId, setNotice]);

  async function add() {
    setBusy(true);
    try {
      const contact = await api.createContact(conn, { name: form.name.trim(), phone: form.phone.trim() || null, email: null });
      const member = await api.createCrewMember(conn, productionId, {
        contact_id: contact.id, department: form.department.trim(), position: form.position.trim(), standard_call_time: null, is_head_of_department: form.hod,
      });
      setCrew((c) => [...(c ?? []), member]);
      setForm({ name: "", phone: "", department: form.department, position: "", hod: false });
      setNotice({ kind: "ok", text: `${contact.name} added${form.hod ? " as head of department" : ""}.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not add the crew member"));
    } finally {
      setBusy(false);
    }
  }

  const canAdd = form.name.trim() && form.department.trim() && form.position.trim() && !busy;
  return (
    <section className="block" aria-label="Crew">
      <h2>Crew</h2>
      {crew === null && <p className="hint">Loading…</p>}
      {crew && crew.length === 0 && <p className="hint">No crew yet. Heads of department appear on every call sheet under "Who to call".</p>}
      {crew && crew.length > 0 && (
        <ul className="list" id="crew">
          {crew.map((m) => (
            <li key={m.id} className="row static">
              <span className="name">{m.contact.name}{m.is_head_of_department && <span className="tag">HoD</span>}</span>
              <span className="meta">{m.department} · {m.position}{m.contact.phone ? ` · ${m.contact.phone}` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="grid2">
        <label className="field" htmlFor="crewName"><span className="label">Name</span><input id="crewName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field" htmlFor="crewPhone"><span className="label">Phone</span><input id="crewPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
        <label className="field" htmlFor="crewDept"><span className="label">Department</span><input id="crewDept" placeholder="Camera" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></label>
        <label className="field" htmlFor="crewPos"><span className="label">Position</span><input id="crewPos" placeholder="DoP" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
      </div>
      <label className="check"><input id="crewHod" type="checkbox" checked={form.hod} onChange={(e) => setForm({ ...form, hod: e.target.checked })} /> Head of department (shown under "Who to call")</label>
      <button type="button" id="addCrew" className="secondary" disabled={!canAdd} onClick={() => void add()}>Add to crew</button>
    </section>
  );
}
