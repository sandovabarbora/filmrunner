import { useEffect, useRef, useState } from "react";
import { Avatar } from "../../Avatar";
import { api, ApiError, type Connection } from "../api";
import { clearPendingCrewEdit, loadAllPendingCrewEdits, savePendingCrewEdit, type PendingCrewEdit } from "../crewEdits";
import { resizeImageToBlob } from "../resizeImage";
import { importableRows, parseCrewList } from "../crewImport";
import { allLinksText, onboardingMessageText, whatsappNumber, whatsappUrl } from "../shareText";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import type { CallSheetCreated, CastMember, CrewMember, Location, LocationUpdate, Member, Production, ProductionRole } from "../../types";

export function crewLink(apiBase: string, sheetId: string): string {
  const base = window.location.href.replace(/editor\.html.*$/, "");
  return `${base}?sheet=${sheetId}&api=${encodeURIComponent(apiBase.replace(/\/$/, ""))}`;
}

/** FR-32: one link per person for the whole shoot; it opens their next day and carries their personal block. */
export function personalLink(apiBase: string, token: string): string {
  const base = window.location.href.replace(/editor\.html.*$/, "");
  return `${base}?api=${encodeURIComponent(apiBase.replace(/\/$/, ""))}&me=${encodeURIComponent(token)}`;
}

export function can(production: Production | null, permission: string): boolean {
  return (production?.permissions ?? []).includes(permission as never);
}

/** First-run guidance: the four things a production needs before the crew gets a link. Hidden once all are done. */
function Checklist({ conn, productionId, canEdit, refreshKey }: { conn: Connection; productionId: string; canEdit: boolean; refreshKey: number }) {
  const [state, setState] = useState<{ crew: number; days: number; published: number } | null>(null);
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listCrew(conn, productionId), api.listCallSheets(conn, productionId)])
      .then(([crew, days]) => { if (!cancelled) setState({ crew: crew.length, days: days.length, published: days.filter((d) => d.current_revision).length }); })
      .catch(() => { if (!cancelled) setState(null); });
    return () => { cancelled = true; };
  }, [conn, productionId, refreshKey]);
  if (!state || !canEdit) return null;
  const steps = [
    { done: true, text: "Production created" },
    { done: state.crew > 0, text: "Add the crew: names, numbers, heads of department", href: href({ screen: "production", productionId, tab: "crew" }) },
    { done: state.days > 0, text: "Create the first shoot day", href: href({ screen: "day", productionId, callSheetId: null }) },
    { done: state.published > 0, text: "Publish it and send the crew link (or personal links)", href: href({ screen: "production", productionId, tab: "days" }) },
  ];
  if (steps.every((st) => st.done)) return null;
  const next = steps.find((st) => !st.done);
  return (
    <section className="checklist" id="checklist" aria-label="Getting started">
      <h2>Getting started</h2>
      <ol>
        {steps.map((st) => (
          <li key={st.text} className={st.done ? "done" : st === next ? "next" : ""}>
            <span className="mark" aria-hidden="true">{st.done ? "✓" : "○"}</span>
            {st.href && !st.done ? <a href={st.href}>{st.text}</a> : <span>{st.text}</span>}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function ProductionScreen({ conn, productionId, production, tab, setNotice, onUpdated }: {
  conn: Connection; productionId: string; production: Production | null; tab: "days" | "crew" | "cast" | "locations" | "members" | "settings";
  setNotice: (n: Notice) => void; onUpdated: (p: Production) => void;
}) {
  const manage = can(production, "production:manage_members");
  const edit = can(production, "production:edit");
  return (
    <>
      <Checklist conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} refreshKey={tab === "days" ? 0 : 1} />
      <div className="tabs" role="tablist">
        <a role="tab" aria-selected={tab === "days"} className={tab === "days" ? "on" : ""} href={href({ screen: "production", productionId, tab: "days" })}>Days</a>
        <a role="tab" aria-selected={tab === "crew"} className={tab === "crew" ? "on" : ""} href={href({ screen: "production", productionId, tab: "crew" })}>Crew</a>
        <a role="tab" aria-selected={tab === "cast"} className={tab === "cast" ? "on" : ""} href={href({ screen: "production", productionId, tab: "cast" })}>Cast</a>
        <a role="tab" aria-selected={tab === "locations"} className={tab === "locations" ? "on" : ""} href={href({ screen: "production", productionId, tab: "locations" })}>Locations</a>
        {manage && <a role="tab" aria-selected={tab === "members"} className={tab === "members" ? "on" : ""} href={href({ screen: "production", productionId, tab: "members" })}>Members</a>}
        {edit && <a role="tab" aria-selected={tab === "settings"} className={tab === "settings" ? "on" : ""} href={href({ screen: "production", productionId, tab: "settings" })}>Settings</a>}
        {production?.my_role && <span className="role-chip" id="myRole">{production.my_role}</span>}
      </div>
      {tab === "days" && <Days conn={conn} productionId={productionId} canPublish={can(production, "day:publish")} setNotice={setNotice} />}
      {tab === "crew" && <Crew conn={conn} productionId={productionId} productionName={production?.name ?? null} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "cast" && <Cast conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "locations" && <Locations conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "members" && manage && <Members conn={conn} productionId={productionId} setNotice={setNotice} />}
      {tab === "settings" && edit && production && <Settings conn={conn} production={production} setNotice={setNotice} onUpdated={onUpdated} />}
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
                <span className="name">Day {d.day_number} of {d.day_count} <span className="meta">· {d.shoot_date} · {d.unit_name}</span>{d.status === "cancelled" && <span className="tag warn">CANCELLED</span>}</span>
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

/** A pending edit overlaid onto the server's copy of a crew member, for display and for re-editing. */
function applyPendingEdit(m: CrewMember, p: PendingCrewEdit): CrewMember {
  return {
    ...m,
    contact: { ...m.contact, name: p.name, phone: p.phone || null },
    department: p.department,
    position: p.position,
    standard_call_time: p.standard_call_time,
    is_head_of_department: p.is_head_of_department,
  };
}

function Crew({ conn, productionId, productionName, canEdit, setNotice }: { conn: Connection; productionId: string; productionName: string | null; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const [crew, setCrew] = useState<CrewMember[] | null>(null);
  const [form, setForm] = useState<CrewForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<CrewMember | null>(null);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);
  // Edits made offline (FR-18 failure case): kept in IndexedDB and overlaid on the crew list until they sync.
  const [pending, setPending] = useState<Map<string, PendingCrewEdit>>(new Map());

  async function syncPendingEdit(edit: PendingCrewEdit, announce: boolean): Promise<void> {
    try {
      const contact = await api.updateContact(conn, edit.contactId, { name: edit.name, phone: edit.phone || null });
      const member = await api.updateCrewMember(conn, productionId, edit.memberId, {
        department: edit.department, position: edit.position, standard_call_time: edit.standard_call_time, is_head_of_department: edit.is_head_of_department,
      });
      await clearPendingCrewEdit(edit.memberId);
      setCrew((c) => (c ?? []).map((x) => (x.id === member.id ? { ...member, contact } : x)));
      setPending((p) => { if (!p.has(edit.memberId)) return p; const n = new Map(p); n.delete(edit.memberId); return n; });
      if (announce) setNotice({ kind: "ok", text: `${contact.name} synced.` });
    } catch (err) {
      if (announce) setNotice(err instanceof ApiError && err.status === 0
        ? { kind: "warn", text: "Still offline; the change stays on this phone." }
        : noticeFromError(err, "Could not sync the change"));
    }
  }

  useEffect(() => {
    let cancelled = false;
    api.listCrew(conn, productionId)
      .then(async (list) => {
        if (cancelled) return;
        setCrew(list);
        const stored = await loadAllPendingCrewEdits(productionId).catch(() => []);
        if (cancelled || stored.length === 0) return;
        setPending(new Map(stored.map((e) => [e.memberId, e])));
        for (const edit of stored) void syncPendingEdit(edit, false);
      })
      .catch((err: unknown) => { setCrew([]); setNotice(noticeFromError(err, "Cannot load crew")); });
    return () => { cancelled = true; };
  }, [conn, productionId, setNotice]);

  const visibleCrew = crew ? crew.map((m) => (pending.has(m.id) ? applyPendingEdit(m, pending.get(m.id)!) : m)) : null;

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
        if (pending.has(editing.id)) {
          await clearPendingCrewEdit(editing.id);
          setPending((p) => { const n = new Map(p); n.delete(editing.id); return n; });
        }
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
      // An edit to an existing person is never lost offline: it queues on this phone (FR-18 failure case).
      // Adding a new person offline has nothing to queue against yet (no crew-member id), so it just fails as before.
      if (editing && err instanceof ApiError && err.status === 0) {
        const edit: PendingCrewEdit = {
          memberId: editing.id, productionId, contactId: editing.contact_id,
          name: form.name.trim(), phone: form.phone.trim(),
          department: form.department.trim(), position: form.position.trim(),
          standard_call_time: form.call.trim() || null, is_head_of_department: form.hod,
          savedAt: new Date().toISOString(),
        };
        await savePendingCrewEdit(edit);
        setPending((p) => new Map(p).set(edit.memberId, edit));
        setNotice({ kind: "warn", text: "No connection. The change is kept on this phone as not saved; it will sync when you are back online." });
        cancelEdit();
      } else {
        setNotice(noticeFromError(err, editing ? "Could not save the changes" : "Could not add the crew member"));
      }
    } finally {
      setBusy(false);
    }
  }

  // FR-31: paste the whole list. Rows are created one by one so a failure names the person, not the batch.
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const parsed = pasteOpen ? parseCrewList(pasteText, (crew ?? []).map((m) => m.contact.name)) : [];
  const toImport = importableRows(parsed);
  async function importPasted() {
    setBusy(true);
    const added: CrewMember[] = [];
    const failed: string[] = [];
    for (const row of toImport) {
      try {
        const contact = await api.createContact(conn, { name: row.name, phone: row.phone, email: null });
        const member = await api.createCrewMember(conn, productionId, {
          contact_id: contact.id, department: row.department, position: row.position, standard_call_time: null, is_head_of_department: row.hod,
        });
        added.push(member);
      } catch {
        failed.push(row.name);
      }
    }
    setCrew((c) => [...(c ?? []), ...added]);
    setBusy(false);
    if (failed.length === 0) { setPasteText(""); setPasteOpen(false); }
    else setPasteText(parsed.filter((r) => failed.includes(r.name)).map((r) => `${r.department}: ${r.name}, ${r.position}${r.phone ? `, ${r.phone}` : ""}`).join("\n"));
    setNotice(failed.length === 0
      ? { kind: "ok", text: `Added ${added.length} ${added.length === 1 ? "person" : "people"} to the crew.` }
      : { kind: "warn", text: `Added ${added.length}; could not add ${failed.join(", ")}. They stay in the box so you can try again.` });
  }

  async function remove(m: CrewMember) {
    if (!window.confirm(`Remove ${m.contact.name} from the crew? Their personal link stops working.`)) return;
    try {
      await api.removeCrewMember(conn, productionId, m.id);
      setCrew((c) => (c ?? []).filter((x) => x.id !== m.id));
      if (editing?.id === m.id) cancelEdit();
      if (pending.has(m.id)) {
        await clearPendingCrewEdit(m.id);
        setPending((p) => { const n = new Map(p); n.delete(m.id); return n; });
      }
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
      {visibleCrew && visibleCrew.length > 0 && (
        <ul className="list" id="crew">
          {visibleCrew.map((m) => (
            <li key={m.id} className={`row static${editing?.id === m.id ? " editing" : ""}`}>
              <span className="name crew-name">
                <Avatar name={m.contact.name} photoUrl={m.contact.photo_url} size={28} />
                <span>{m.contact.name}{m.is_head_of_department && <span className="tag">HoD</span>}
                  {pending.has(m.id) && <span className="tag warn" id={`notSaved-${m.id}`}>not saved</span>}
                  <span className="meta"> · {m.department} · {m.position}{m.contact.phone ? ` · ${m.contact.phone}` : ""}{m.standard_call_time ? ` · call ${m.standard_call_time}` : ""}</span>
                </span>
              </span>
              {canEdit && (
                <span className="row-actions">
                  {pending.has(m.id) && (
                    <button type="button" className="quiet" onClick={() => void syncPendingEdit(pending.get(m.id)!, true)} aria-label={`Sync ${m.contact.name}`}>Sync</button>
                  )}
                  <button type="button" className="quiet" onClick={() => { void navigator.clipboard?.writeText(personalLink(conn.apiBase, m.personal_token)); setNotice({ kind: "ok", text: `${m.contact.name}'s link copied. One link for the whole shoot; it always opens their next day.` }); }} aria-label={`Copy link for ${m.contact.name}`}>Link</button>
                  {whatsappNumber(m.contact.phone) && (
                    <a className="quiet-link whatsapp" href={whatsappUrl(whatsappNumber(m.contact.phone), onboardingMessageText(productionName, m, personalLink(conn.apiBase, m.personal_token)))}
                      target="_blank" rel="noreferrer" aria-label={`Send link to ${m.contact.name} on WhatsApp`}>WhatsApp</a>
                  )}
                  <button type="button" className="quiet" onClick={() => startEdit(m)} aria-label={`Edit ${m.contact.name}`}>Edit</button>
                  <button type="button" className="quiet danger" onClick={() => void remove(m)} aria-label={`Remove ${m.contact.name}`}>Remove</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {visibleCrew && visibleCrew.length > 0 && (
        <div className="inline" id="allLinks">
          <button type="button" className="quiet" id="copyAllLinks" onClick={() => {
            void navigator.clipboard?.writeText(allLinksText(visibleCrew, (m) => personalLink(conn.apiBase, m.personal_token)));
            setNotice({ kind: "ok", text: `${visibleCrew.length} links copied, one per line with the name. Each person's link is theirs alone; send them one by one, not to the group.` });
          }}>Copy all links</button>
          <span className="hint">Each link is personal: it shows that person's call and counts as them opening the sheet. WhatsApp sends it to them directly.</span>
        </div>
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
        {!editing && <button type="button" className="quiet" id="pasteCrew" onClick={() => setPasteOpen((o) => !o)}>{pasteOpen ? "Close the list" : "Paste a list…"}</button>}
      </div>
      {pasteOpen && !editing && (
        <div className="paste-crew" id="pasteCrewPanel">
          <p className="hint">One person per line: name, position, phone — or name, department, position, phone. A line like "Camera:" sets the department for the lines below. "HoD" marks a head of department.</p>
          <textarea id="pasteCrewText" rows={6} placeholder={"Camera:\nJan Novák, DoP, 777 123 456, HoD\nPetra K., 1st AC\nElectric:\nTomáš Novák, Gaffer"} value={pasteText} onChange={(e) => setPasteText(e.target.value)} disabled={busy} />
          {parsed.length > 0 && (
            <ul className="list preview" id="pastePreview">
              {parsed.map((r) => (
                <li key={r.line} className={`row static${r.warning ? " warn" : ""}`}>
                  <span className="name">{r.name}{r.hod && <span className="tag">HoD</span>}
                    <span className="meta"> · {r.department} · {r.position}{r.phone ? ` · ${r.phone}` : ""}</span>
                    {r.warning && <span className="meta warn-text"> · {r.warning}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="inline">
            <button type="button" id="importCrew" className="secondary" disabled={toImport.length === 0 || busy} onClick={() => void importPasted()}>
              {busy ? "Adding…" : `Add ${toImport.length} ${toImport.length === 1 ? "person" : "people"}`}
            </button>
          </div>
        </div>
      )}
      </>)}
    </section>
  );
}

/** FR-34: rename, or move the production along prep → shooting → wrapped. Nothing else lives here on purpose. */
function Settings({ conn, production, setNotice, onUpdated }: { conn: Connection; production: Production; setNotice: (n: Notice) => void; onUpdated: (p: Production) => void }) {
  const [name, setName] = useState(production.name);
  const [status, setStatus] = useState(production.status);
  const [busy, setBusy] = useState(false);
  const changed = name.trim() !== production.name || status !== production.status;
  async function save() {
    setBusy(true);
    try {
      const updated = await api.updateProduction(conn, production.id, { name: name.trim(), status });
      onUpdated(updated);
      setNotice({ kind: "ok", text: `Saved. ${updated.name} is ${updated.status}.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not save the production"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="block" aria-label="Settings">
      <h2>Settings</h2>
      <div className="grid2">
        <label className="field" htmlFor="productionName"><span className="label">Name</span><input id="productionName" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="field" htmlFor="productionStatus"><span className="label">Status</span>
          <select id="productionStatus" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="prep">prep</option><option value="shooting">shooting</option><option value="wrapped">wrapped</option>
          </select>
        </label>
      </div>
      <p className="hint">Wrapped productions stay readable; every link keeps working. Days are never deleted — cancel a day from its own screen.</p>
      <div className="inline">
        <button type="button" id="saveProduction" className="secondary" disabled={!changed || !name.trim() || busy} onClick={() => void save()}>Save</button>
      </div>
    </section>
  );
}

type CastForm = { name: string; phone: string; character: string; pickup: string };
const EMPTY_CAST_FORM: CastForm = { name: "", phone: "", character: "", pickup: "" };

/** FR-33: the people in front of the camera. Per-day times are set on the day (status, pickup, M/H, on set). */
function Cast({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const [cast, setCast] = useState<CastMember[] | null>(null);
  const [form, setForm] = useState<CastForm>(EMPTY_CAST_FORM);
  const [editing, setEditing] = useState<CastMember | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.listCast(conn, productionId).then((c) => { if (!cancelled) setCast(c); }).catch((err) => { if (!cancelled) setNotice(noticeFromError(err, "Could not load the cast")); });
    return () => { cancelled = true; };
  }, [conn, productionId, setNotice]);

  function startEdit(a: CastMember) {
    setEditing(a);
    setForm({ name: a.contact.name, phone: a.contact.phone ?? "", character: a.character_name, pickup: a.standard_pickup_time ?? "" });
  }
  function cancelEdit() { setEditing(null); setForm(EMPTY_CAST_FORM); }

  async function save() {
    setBusy(true);
    try {
      if (editing) {
        const contact = await api.updateContact(conn, editing.contact_id, { name: form.name.trim(), phone: form.phone.trim() || null });
        const actor = await api.updateCastMember(conn, productionId, editing.id, { character_name: form.character.trim(), standard_pickup_time: form.pickup.trim() || null });
        setCast((c) => (c ?? []).map((x) => (x.id === actor.id ? { ...actor, contact } : x)));
        setNotice({ kind: "ok", text: `${contact.name} updated.` });
        cancelEdit();
      } else {
        const contact = await api.createContact(conn, { name: form.name.trim(), phone: form.phone.trim() || null, email: null });
        const actor = await api.createCastMember(conn, productionId, { contact_id: contact.id, character_name: form.character.trim(), standard_pickup_time: form.pickup.trim() || null });
        setCast((c) => [...(c ?? []), actor]);
        setForm(EMPTY_CAST_FORM);
        setNotice({ kind: "ok", text: `${contact.name} added as ${actor.character_name}. Set their times on each day.` });
      }
    } catch (err) {
      setNotice(noticeFromError(err, editing ? "Could not save the changes" : "Could not add the cast member"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(a: CastMember) {
    setBusy(true);
    try {
      await api.deleteCastMember(conn, productionId, a.id);
      setCast((c) => (c ?? []).filter((x) => x.id !== a.id));
      setNotice({ kind: "ok", text: `${a.contact.name} removed from the cast. Their lines drop from the sheets.` });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not remove the cast member"));
    } finally {
      setBusy(false);
    }
  }

  const canSave = form.name.trim() && form.character.trim() && !busy;
  return (
    <section className="block" aria-label="Cast">
      <h2>Cast</h2>
      {cast === null && <p className="hint">Loading…</p>}
      {cast && cast.length === 0 && <p className="hint">No cast yet. Add the actors once; each day then gets its own status, pickup, make-up and on-set times.</p>}
      {cast && cast.length > 0 && (
        <ul className="list" id="cast">
          {cast.map((a) => (
            <li key={a.id} className={`row static${editing?.id === a.id ? " editing" : ""}`}>
              <span className="name crew-name">
                <Avatar name={a.contact.name} photoUrl={a.contact.photo_url} size={28} />
                <span>{a.contact.name}
                  <span className="meta"> · {a.character_name}{a.contact.phone ? ` · ${a.contact.phone}` : ""}{a.standard_pickup_time ? ` · pickup ${a.standard_pickup_time}` : ""}</span>
                </span>
              </span>
              {canEdit && (
                <span className="row-actions">
                  <button type="button" className="quiet" onClick={() => startEdit(a)} aria-label={`Edit ${a.contact.name}`}>Edit</button>
                  <button type="button" className="quiet danger" disabled={busy} onClick={() => void remove(a)} aria-label={`Remove ${a.contact.name}`}>Remove</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (<>
        <h3 className="subhead" id="castFormTitle">{editing ? `Editing ${editing.contact.name}` : "Add an actor"}</h3>
        <div className="grid2">
          <label className="field" htmlFor="castName"><span className="label">Name</span><input id="castName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field" htmlFor="castCharacter"><span className="label">Character</span><input id="castCharacter" placeholder="MARTA" value={form.character} onChange={(e) => setForm({ ...form, character: e.target.value })} /></label>
          <label className="field" htmlFor="castPhone"><span className="label">Phone</span><input id="castPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
          <label className="field" htmlFor="castPickup"><span className="label">Usual pickup (optional)</span><input id="castPickup" className="mono" placeholder="05:30" value={form.pickup} onChange={(e) => setForm({ ...form, pickup: e.target.value })} /></label>
        </div>
        <div className="inline">
          <button type="button" id="addCast" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? "Save changes" : "Add to cast"}</button>
          {editing && <button type="button" className="quiet" onClick={cancelEdit}>Cancel</button>}
        </div>
      </>)}
    </section>
  );
}

type LocationForm = { name: string; address: string; parking_notes: string; nearest_hospital: string };
const EMPTY_LOCATION_FORM: LocationForm = { name: "", address: "", parking_notes: "", nearest_hospital: "" };

function Locations({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [form, setForm] = useState<LocationForm>(EMPTY_LOCATION_FORM);
  const [editing, setEditing] = useState<Location | null>(null);
  const [busy, setBusy] = useState(false);
  const [hospitalSuggestion, setHospitalSuggestion] = useState<string | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  useEffect(() => {
    api.listLocations(conn, productionId).then(setLocations).catch((err: unknown) => { setLocations([]); setNotice(noticeFromError(err, "Cannot load locations")); });
  }, [conn, productionId, setNotice]);

  function startEdit(l: Location) {
    setEditing(l);
    setHospitalSuggestion(null);
    setForm({ name: l.name, address: l.address ?? "", parking_notes: l.parking_notes ?? "", nearest_hospital: l.nearest_hospital ?? "" });
  }
  function cancelEdit() { setEditing(null); setHospitalSuggestion(null); setForm(EMPTY_LOCATION_FORM); }

  async function save() {
    setBusy(true);
    try {
      if (editing) {
        const updated = await api.updateLocation(conn, productionId, editing.id, {
          name: form.name.trim(), address: form.address.trim() || null,
          parking_notes: form.parking_notes.trim() || null, nearest_hospital: form.nearest_hospital.trim() || null,
        } satisfies LocationUpdate);
        setLocations((ls) => (ls ?? []).map((x) => (x.id === updated.id ? updated : x)));
        setNotice({ kind: "ok", text: `${updated.name} updated.` });
        cancelEdit();
      } else {
        const created = await api.createLocation(conn, productionId, {
          name: form.name.trim(), address: form.address.trim() || null,
          parking_notes: form.parking_notes.trim() || null, nearest_hospital: form.nearest_hospital.trim() || null,
        });
        setLocations((ls) => [...(ls ?? []), created]);
        setForm(EMPTY_LOCATION_FORM);
        setNotice({ kind: "ok", text: `${created.name} added${created.address ? (created.geocoded_display_name ? `, resolved to ${created.geocoded_display_name}` : ", could not resolve that address — check it") : ""}.` });
      }
    } catch (err) {
      setNotice(noticeFromError(err, editing ? "Could not save the changes" : "Could not add the location"));
    } finally {
      setBusy(false);
    }
  }

  async function suggestHospital() {
    if (!editing) return;
    setSuggesting(true);
    try {
      const { suggestion } = await api.hospitalSuggestion(conn, productionId, editing.id);
      setHospitalSuggestion(suggestion ?? null);
      if (!suggestion) setNotice({ kind: "warn", text: "No hospital suggestion nearby; enter one by hand." });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not get a suggestion"));
    } finally {
      setSuggesting(false);
    }
  }

  const canSave = form.name.trim() && !busy;
  return (
    <section className="block" aria-label="Locations">
      <h2>Locations</h2>
      <p className="hint">An address is geocoded on save so a scene can be tied to it for sunrise/sunset and a nearby hospital can be suggested.</p>
      {locations === null && <p className="hint">Loading…</p>}
      {locations && locations.length === 0 && <p className="hint">No locations yet.</p>}
      {locations && locations.length > 0 && (
        <ul className="list" id="locations">
          {locations.map((l) => (
            <li key={l.id} className={`row static${editing?.id === l.id ? " editing" : ""}`}>
              <span className="name">{l.name}
                <span className="meta">
                  {l.address ? ` · ${l.address}` : ""}
                  {l.address && !l.geocoded_display_name ? " · not resolved, check the address" : ""}
                  {l.geocoded_display_name ? ` · resolved: ${l.geocoded_display_name}` : ""}
                  {l.nearest_hospital ? ` · hospital: ${l.nearest_hospital}` : ""}
                </span>
              </span>
              {canEdit && (
                <span className="row-actions">
                  <button type="button" className="quiet" onClick={() => startEdit(l)} aria-label={`Edit ${l.name}`}>Edit</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (<>
      <h3 className="subhead" id="locationFormTitle">{editing ? `Editing ${editing.name}` : "Add a location"}</h3>
      <div className="grid2">
        <label className="field" htmlFor="locName"><span className="label">Name</span><input id="locName" placeholder="Riverbank, Troja" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field" htmlFor="locAddress"><span className="label">Address</span><input id="locAddress" placeholder="Nábřeží, Praha" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></label>
      </div>
      {editing?.address === form.address && editing?.geocoded_display_name && (
        <p className="hint">Resolved to: {editing.geocoded_display_name}. Wrong place? Change the address and save again.</p>
      )}
      <label className="field" htmlFor="locParking"><span className="label">Parking notes</span><input id="locParking" value={form.parking_notes} onChange={(e) => setForm({ ...form, parking_notes: e.target.value })} /></label>
      <label className="field" htmlFor="locHospital"><span className="label">Nearest hospital</span><input id="locHospital" value={form.nearest_hospital} onChange={(e) => setForm({ ...form, nearest_hospital: e.target.value })} /></label>
      {editing && editing.geo_lat != null && (
        <div className="inline">
          <button type="button" className="quiet" disabled={suggesting} onClick={() => void suggestHospital()}>{suggesting ? "Looking…" : "Suggest nearest hospital"}</button>
          {hospitalSuggestion && (
            <button type="button" className="quiet" onClick={() => { setForm({ ...form, nearest_hospital: hospitalSuggestion }); setHospitalSuggestion(null); }}>
              Use: {hospitalSuggestion}
            </button>
          )}
        </div>
      )}
      <div className="inline">
        <button type="button" id="addLocation" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? "Save changes" : "Add location"}</button>
        {editing && <button type="button" className="quiet" id="cancelLocationEdit" onClick={cancelEdit}>Cancel</button>}
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
