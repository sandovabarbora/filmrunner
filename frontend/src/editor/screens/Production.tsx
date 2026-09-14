import { useEffect, useState } from "react";
import { api, type Connection } from "../api";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import type { CallSheetCreated, CrewMember, Member, Production, ProductionRole } from "../../types";

export function crewLink(apiBase: string, sheetId: string): string {
  const base = window.location.href.replace(/editor\.html.*$/, "");
  return `${base}?sheet=${sheetId}&api=${encodeURIComponent(apiBase.replace(/\/$/, ""))}`;
}

export function can(production: Production | null, permission: string): boolean {
  return (production?.permissions ?? []).includes(permission as never);
}

export function ProductionScreen({ conn, productionId, production, tab, setNotice }: {
  conn: Connection; productionId: string; production: Production | null; tab: "days" | "crew" | "members"; setNotice: (n: Notice) => void;
}) {
  const manage = can(production, "production:manage_members");
  return (
    <>
      <div className="tabs" role="tablist">
        <a role="tab" aria-selected={tab === "days"} className={tab === "days" ? "on" : ""} href={href({ screen: "production", productionId, tab: "days" })}>Days</a>
        <a role="tab" aria-selected={tab === "crew"} className={tab === "crew" ? "on" : ""} href={href({ screen: "production", productionId, tab: "crew" })}>Crew</a>
        {manage && <a role="tab" aria-selected={tab === "members"} className={tab === "members" ? "on" : ""} href={href({ screen: "production", productionId, tab: "members" })}>Members</a>}
        {production?.my_role && <span className="role-chip" id="myRole">{production.my_role}</span>}
      </div>
      {tab === "days" && <Days conn={conn} productionId={productionId} canPublish={can(production, "day:publish")} setNotice={setNotice} />}
      {tab === "crew" && <Crew conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "members" && manage && <Members conn={conn} productionId={productionId} setNotice={setNotice} />}
      {production === null && <p className="hint">Production not found in this list; go back to Productions.</p>}
    </>
  );
}

function Days({ conn, productionId, canPublish, setNotice }: { conn: Connection; productionId: string; canPublish: boolean; setNotice: (n: Notice) => void }) {
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
      {canPublish
        ? <a className="button" id="newDay" href={href({ screen: "day", productionId, callSheetId: null })}>+ New day</a>
        : <p className="hint" id="readOnlyHint">You can view this production; publishing needs the editor or owner role.</p>}
    </section>
  );
}

function Crew({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
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
      {canEdit && (<>
      <div className="grid2">
        <label className="field" htmlFor="crewName"><span className="label">Name</span><input id="crewName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field" htmlFor="crewPhone"><span className="label">Phone</span><input id="crewPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
        <label className="field" htmlFor="crewDept"><span className="label">Department</span><input id="crewDept" placeholder="Camera" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></label>
        <label className="field" htmlFor="crewPos"><span className="label">Position</span><input id="crewPos" placeholder="DoP" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
      </div>
      <label className="check"><input id="crewHod" type="checkbox" checked={form.hod} onChange={(e) => setForm({ ...form, hod: e.target.checked })} /> Head of department (shown under "Who to call")</label>
      <button type="button" id="addCrew" className="secondary" disabled={!canAdd} onClick={() => void add()}>Add to crew</button>
      </>)}
    </section>
  );
}

function Members({ conn, productionId, setNotice }: { conn: Connection; productionId: string; setNotice: (n: Notice) => void }) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ProductionRole>("editor");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listMembers(conn, productionId).then(setMembers).catch((err: unknown) => { setMembers([]); setNotice(noticeFromError(err, "Cannot load members")); });
  }, [conn, productionId, setNotice]);

  async function add() {
    setBusy(true);
    try {
      const m = await api.addMember(conn, productionId, email.trim(), role);
      setMembers((ms) => [...(ms ?? []).filter((x) => x.id !== m.id), m]);
      setEmail("");
      setNotice({ kind: "ok", text: `${m.email} can now ${m.role === "viewer" ? "view" : m.role === "editor" ? "edit and publish" : "do everything"}. They sign in with that email.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not add the member"));
    } finally {
      setBusy(false);
    }
  }
  async function remove(m: Member) {
    try {
      await api.removeMember(conn, productionId, m.id);
      setMembers((ms) => (ms ?? []).filter((x) => x.id !== m.id));
    } catch (err) {
      setNotice(noticeFromError(err, "Could not remove the member"));
    }
  }

  return (
    <section className="block" aria-label="Members">
      <h2>Members</h2>
      <p className="hint">Owner: everything, incl. members. Editor: days, crew, publish. Viewer: read only.</p>
      {members === null && <p className="hint">Loading…</p>}
      {members && members.length > 0 && (
        <ul className="list" id="members">
          {members.map((m) => (
            <li key={m.id} className="row static">
              <span className="name">{m.email}<span className="tag">{m.role}</span>{!m.user_id && <span className="meta"> · not signed in yet</span>}</span>
              <button type="button" className="quiet danger" onClick={() => void remove(m)} aria-label={`Remove ${m.email}`}>Remove</button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid2">
        <label className="field" htmlFor="memberEmail"><span className="label">Email</span><input id="memberEmail" type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field" htmlFor="memberRole"><span className="label">Role</span>
          <select id="memberRole" value={role} onChange={(e) => setRole(e.target.value as ProductionRole)}>
            <option value="editor">editor</option><option value="viewer">viewer</option><option value="owner">owner</option>
          </select>
        </label>
      </div>
      <button type="button" id="addMember" className="secondary" disabled={!email.includes("@") || busy} onClick={() => void add()}>Invite</button>
    </section>
  );
}
