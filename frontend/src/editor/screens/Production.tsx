import { useEffect, useRef, useState } from "react";
import { Avatar } from "../../Avatar";
import { api, type Connection } from "../api";
import { resizeImageToBlob } from "../resizeImage";
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

type CrewForm = { name: string; phone: string; department: string; position: string; call: string; hod: boolean };
const EMPTY_FORM: CrewForm = { name: "", phone: "", department: "", position: "", call: "", hod: false };

function Crew({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const [crew, setCrew] = useState<CrewMember[] | null>(null);
  const [form, setForm] = useState<CrewForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<CrewMember | null>(null);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listCrew(conn, productionId).then(setCrew).catch((err: unknown) => { setCrew([]); setNotice(noticeFromError(err, "Cannot load crew")); });
  }, [conn, productionId, setNotice]);

  function startEdit(m: CrewMember) {
    setEditing(m);
    setForm({ name: m.contact.name, phone: m.contact.phone ?? "", department: m.department, position: m.position, call: m.standard_call_time ?? "", hod: m.is_head_of_department });
  }
  function cancelEdit() { setEditing(null); setForm({ ...EMPTY_FORM, department: form.department }); }

  async function save() {
    setBusy(true);
    try {
      if (editing) {
        const contact = await api.updateContact(conn, editing.contact_id, { name: form.name.trim(), phone: form.phone.trim() || null });
        const member = await api.updateCrewMember(conn, productionId, editing.id, {
          department: form.department.trim(), position: form.position.trim(), standard_call_time: form.call.trim() || null, is_head_of_department: form.hod,
        });
        setCrew((c) => (c ?? []).map((x) => (x.id === member.id ? { ...member, contact } : x)));
        setNotice({ kind: "ok", text: `${contact.name} updated. The sheet shows it immediately.` });
        cancelEdit();
      } else {
        const contact = await api.createContact(conn, { name: form.name.trim(), phone: form.phone.trim() || null, email: null });
        const member = await api.createCrewMember(conn, productionId, {
          contact_id: contact.id, department: form.department.trim(), position: form.position.trim(), standard_call_time: form.call.trim() || null, is_head_of_department: form.hod,
        });
        setCrew((c) => [...(c ?? []), member]);
        setForm({ ...EMPTY_FORM, department: form.department });
        setNotice({ kind: "ok", text: `${contact.name} added${form.hod ? " as head of department" : ""}.` });
      }
    } catch (err) {
      setNotice(noticeFromError(err, editing ? "Could not save the changes" : "Could not add the crew member"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(m: CrewMember) {
    if (!window.confirm(`Remove ${m.contact.name} from the crew? Their personal link stops working.`)) return;
    try {
      await api.removeCrewMember(conn, productionId, m.id);
      setCrew((c) => (c ?? []).filter((x) => x.id !== m.id));
      if (editing?.id === m.id) cancelEdit();
      setNotice({ kind: "ok", text: `${m.contact.name} removed.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not remove"));
    }
  }

  function applyContactPhoto(contactId: string, photoUrl: string | null) {
    setCrew((c) => (c ?? []).map((x) => (x.contact_id === contactId ? { ...x, contact: { ...x.contact, photo_url: photoUrl } } : x)));
    setEditing((e) => (e && e.contact_id === contactId ? { ...e, contact: { ...e.contact, photo_url: photoUrl } } : e));
  }

  async function uploadPhoto(m: CrewMember, file: File) {
    setPhotoBusy(true);
    try {
      const resized = await resizeImageToBlob(file);
      const contact = await api.uploadContactPhoto(conn, m.contact_id, resized);
      applyContactPhoto(m.contact_id, contact.photo_url);
      setNotice({ kind: "ok", text: `Photo updated for ${m.contact.name}.` });
    } catch (err) {
      // A failed upload never touches the rest of the person's saved fields.
      setNotice(noticeFromError(err, "Could not upload the photo"));
    } finally {
      setPhotoBusy(false);
    }
  }

  async function removePhoto(m: CrewMember) {
    setPhotoBusy(true);
    try {
      const contact = await api.removeContactPhoto(conn, m.contact_id);
      applyContactPhoto(m.contact_id, contact.photo_url);
    } catch (err) {
      setNotice(noticeFromError(err, "Could not remove the photo"));
    } finally {
      setPhotoBusy(false);
    }
  }

  const canSave = form.name.trim() && form.department.trim() && form.position.trim() && !busy;
  return (
    <section className="block" aria-label="Crew">
      <h2>Crew</h2>
      {crew === null && <p className="hint">Loading…</p>}
      {crew && crew.length === 0 && <p className="hint">No crew yet. Heads of department appear on every call sheet under "Who to call".</p>}
      {crew && crew.length > 0 && (
        <ul className="list" id="crew">
          {crew.map((m) => (
            <li key={m.id} className={`row static${editing?.id === m.id ? " editing" : ""}`}>
              <span className="name crew-name">
                <Avatar name={m.contact.name} photoUrl={m.contact.photo_url} size={28} />
                <span>{m.contact.name}{m.is_head_of_department && <span className="tag">HoD</span>}
                  <span className="meta"> · {m.department} · {m.position}{m.contact.phone ? ` · ${m.contact.phone}` : ""}{m.standard_call_time ? ` · call ${m.standard_call_time}` : ""}</span>
                </span>
              </span>
              {canEdit && (
                <span className="row-actions">
                  <button type="button" className="quiet" onClick={() => startEdit(m)} aria-label={`Edit ${m.contact.name}`}>Edit</button>
                  <button type="button" className="quiet danger" onClick={() => void remove(m)} aria-label={`Remove ${m.contact.name}`}>Remove</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (<>
      <h3 className="subhead" id="crewFormTitle">{editing ? `Editing ${editing.contact.name}` : "Add a person"}</h3>
      {editing && (
        <div className="inline photo-field" id="crewPhotoField">
          <Avatar name={editing.contact.name} photoUrl={editing.contact.photo_url} size={48} />
          <button type="button" className="quiet" disabled={photoBusy} onClick={() => photoInputRef.current?.click()}>
            {photoBusy ? "Uploading…" : editing.contact.photo_url ? "Change photo" : "Add photo"}
          </button>
          {editing.contact.photo_url && (
            <button type="button" className="quiet danger" disabled={photoBusy} onClick={() => void removePhoto(editing)}>Remove photo</button>
          )}
          <input
            ref={photoInputRef}
            id="crewPhotoInput"
            type="file"
            accept="image/jpeg,image/png"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file && editing) void uploadPhoto(editing, file);
            }}
          />
        </div>
      )}
      <div className="grid2">
        <label className="field" htmlFor="crewName"><span className="label">Name</span><input id="crewName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field" htmlFor="crewPhone"><span className="label">Phone</span><input id="crewPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
        <label className="field" htmlFor="crewDept"><span className="label">Department</span><input id="crewDept" placeholder="Camera" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></label>
        <label className="field" htmlFor="crewPos"><span className="label">Position</span><input id="crewPos" placeholder="DoP" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
        <label className="field" htmlFor="crewCall"><span className="label">Personal call (optional)</span><input id="crewCall" className="mono" placeholder="05:45" value={form.call} onChange={(e) => setForm({ ...form, call: e.target.value })} /></label>
      </div>
      <label className="check"><input id="crewHod" type="checkbox" checked={form.hod} onChange={(e) => setForm({ ...form, hod: e.target.checked })} /> Head of department (shown under "Who to call")</label>
      <div className="inline">
        <button type="button" id="addCrew" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? "Save changes" : "Add to crew"}</button>
        {editing && <button type="button" className="quiet" id="cancelEdit" onClick={cancelEdit}>Cancel</button>}
      </div>
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
