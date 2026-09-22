import { useEffect, useRef, useState } from "react";
import { Avatar } from "../../Avatar";
import { api, ApiError, type Connection } from "../api";
import { clearPendingCrewEdit, loadAllPendingCrewEdits, savePendingCrewEdit, type PendingCrewEdit } from "../crewEdits";
import { resizeImageToBlob } from "../resizeImage";
import { importableRows, parseCrewList, type ParsedCrewRow } from "../crewImport";
import { columnLetter, detectColumns, rowsToCrew, type ColumnMap, type Role } from "../crewFileImport";
import { detectScheduleColumns, locationNames, rowsToSchedule, type ImportedDay } from "../scheduleImport";
import { allLinksText, onboardingMessageText, whatsappNumber, whatsappUrl } from "../shareText";
import { PersonPicker } from "../PersonPicker";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import type { CallSheetCreated, CastMember, CrewMember, Location, LocationUpdate, Member, Production, ProductionRole } from "../../types";
import { useL } from "../lang";

/** FR-45: a picked contact is reused; a phone typed differently here corrects it for every production. */
async function reuseOrCreateContact(conn: Connection, contactId: string | null, name: string, phone: string | null) {
  if (!contactId) return api.createContact(conn, { name, phone, email: null });
  return api.updateContact(conn, contactId, { name, phone });
}

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
  const L = useL();
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
    { done: true, text: L("Production created") },
    { done: state.crew > 0, text: L("Add the crew: names, numbers, heads of department"), href: href({ screen: "production", productionId, tab: "crew" }) },
    { done: state.days > 0, text: L("Create the first shoot day"), href: href({ screen: "day", productionId, callSheetId: null }) },
    { done: state.published > 0, text: L("Publish it and send the crew link (or personal links)"), href: href({ screen: "production", productionId, tab: "days" }) },
  ];
  if (steps.every((st) => st.done)) return null;
  const next = steps.find((st) => !st.done);
  return (
    <section className="checklist" id="checklist" aria-label={L("Getting started")}>
      <h2>{L("Getting started")}</h2>
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
  const L = useL();
  const manage = can(production, "production:manage_members");
  const edit = can(production, "production:edit");
  return (
    <>
      <Checklist conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} refreshKey={tab === "days" ? 0 : 1} />
      <div className="tabs" role="tablist">
        <a role="tab" aria-selected={tab === "days"} className={tab === "days" ? "on" : ""} href={href({ screen: "production", productionId, tab: "days" })}>{L("Days")}</a>
        <a role="tab" aria-selected={tab === "crew"} className={tab === "crew" ? "on" : ""} href={href({ screen: "production", productionId, tab: "crew" })}>{L("Crew")}</a>
        <a role="tab" aria-selected={tab === "cast"} className={tab === "cast" ? "on" : ""} href={href({ screen: "production", productionId, tab: "cast" })}>{L("Cast")}</a>
        <a role="tab" aria-selected={tab === "locations"} className={tab === "locations" ? "on" : ""} href={href({ screen: "production", productionId, tab: "locations" })}>{L("Locations")}</a>
        {manage && <a role="tab" aria-selected={tab === "members"} className={tab === "members" ? "on" : ""} href={href({ screen: "production", productionId, tab: "members" })}>{L("Members")}</a>}
        {edit && <a role="tab" aria-selected={tab === "settings"} className={tab === "settings" ? "on" : ""} href={href({ screen: "production", productionId, tab: "settings" })}>{L("Settings")}</a>}
        {production?.my_role && <span className="role-chip" id="myRole">{production.my_role}</span>}
      </div>
      {tab === "days" && <Days conn={conn} productionId={productionId} canPublish={can(production, "day:publish")} setNotice={setNotice} />}
      {tab === "crew" && <Crew conn={conn} productionId={productionId} productionName={production?.name ?? null} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "cast" && <Cast conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "locations" && <Locations conn={conn} productionId={productionId} canEdit={can(production, "crew:edit")} setNotice={setNotice} />}
      {tab === "members" && manage && <Members conn={conn} productionId={productionId} setNotice={setNotice} />}
      {tab === "settings" && edit && production && <Settings conn={conn} production={production} setNotice={setNotice} onUpdated={onUpdated} />}
      {production === null && <p className="hint">{L("Production not found in this list; go back to Productions.")}</p>}
    </>
  );
}

function Days({ conn, productionId, canPublish, setNotice }: { conn: Connection; productionId: string; canPublish: boolean; setNotice: (n: Notice) => void }) {
  const L = useL();
  const [days, setDays] = useState<CallSheetCreated[] | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    api.listCallSheets(conn, productionId).then(setDays).catch((err: unknown) => { setDays([]); setNotice(noticeFromError(err, "Cannot load days")); });
  }, [conn, productionId, setNotice, reload]);

  // FR-56: the shooting schedule from a spreadsheet becomes planned (draft) days on the server.
  const [imported, setImported] = useState<{ fileName: string; days: ImportedDay[] } | null>(null);
  const [importing, setImporting] = useState(false);
  async function readScheduleFile(file: File) {
    try {
      const XLSX = await import("xlsx");
      const wb = XLSX.read(await file.arrayBuffer(), { type: "array", cellDates: false });
      const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets[wb.SheetNames[0]], { header: 1, raw: false, defval: "" });
      const detected = detectScheduleColumns(rows);
      if (!detected) { setNotice({ kind: "error", text: L("No scene column found. The sheet needs a header row with a Scene (Obraz) column.") }); return; }
      const parsed = rowsToSchedule(rows, detected.headerIndex, detected.map);
      if (parsed.length === 0) { setNotice({ kind: "warn", text: L("No scene rows under the header.") }); return; }
      setImported({ fileName: file.name, days: parsed });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not read that file")));
    }
  }
  const existingDates = new Set((days ?? []).map((d) => d.shoot_date));
  const importable = (imported?.days ?? []).filter((d) => !d.shoot_date || !existingDates.has(d.shoot_date));
  async function createImportedDays() {
    if (!imported) return;
    setImporting(true);
    try {
      const [locations, cast] = await Promise.all([api.listLocations(conn, productionId), api.listCast(conn, productionId)]);
      const locByName = new Map(locations.map((l) => [l.name.toLowerCase(), l.id]));
      for (const name of locationNames(importable)) {
        if (!locByName.has(name.toLowerCase())) {
          const created = await api.createLocation(conn, productionId, { name, address: null, parking_notes: null, nearest_hospital: null });
          locByName.set(name.toLowerCase(), created.id);
        }
      }
      const castByName = new Map(cast.map((a) => [a.contact.name.toLowerCase(), a.id]));
      const maxDay = Math.max(0, ...(days ?? []).map((d) => d.day_number), ...importable.map((d) => d.day_number ?? 0));
      const today = new Date().toISOString().slice(0, 10);
      let nextNumber = maxDay;
      let created = 0;
      const unmatchedCast = new Set<string>();
      for (const d of importable) {
        const castIds = new Set<string>();
        for (const sc of d.scenes) for (const n of sc.cast) { const id = castByName.get(n.toLowerCase()); if (id) castIds.add(id); else unmatchedCast.add(n); }
        const dayNumber = d.day_number ?? ++nextNumber;
        await api.createCallSheet(conn, productionId, {
          shoot_date: d.shoot_date ?? today, day_number: dayNumber, day_count: Math.max(maxDay, dayNumber, importable.length),
          unit_name: d.shoot_date ? "Main Unit" : "Imported schedule", draft: true,
          initial_revision: {
            created_by: "schedule-import", general_crew_call: null, shooting_call: null, sunrise: null, sunset: null, weather_forecast: null, safety_notes: null, head_of_day_crew_member_id: null,
            schedule_items: d.scenes.map((sc, i) => ({ order_index: i + 1, scene_number: sc.scene_number, int_ext: sc.int_ext, day_night: sc.day_night, set_description: sc.set_description, page_count_eighths: sc.page_count_eighths, location_id: sc.location ? locByName.get(sc.location.toLowerCase()) ?? null : null })),
            cast_calls: [...castIds].map((id) => ({ cast_member_id: id, status_code: "W" as const, pickup_time: null, call_time: null, makeup_hair_time: null, on_set_time: null })),
            crew_calls: [],
          },
        });
        created += 1;
      }
      setImported(null); setReload((n) => n + 1);
      const skipped = (imported.days.length - importable.length);
      setNotice({ kind: "ok", text: (created === 1 ? L("1 planned day created as a draft — the crew sees nothing until you publish it.") : L("{n} planned days created as drafts — the crew sees nothing until you publish each one.", { n: created })) + (skipped ? L(" {n} skipped (a day with that date already exists).", { n: skipped }) : "") + (unmatchedCast.size ? L(" Cast not on the Cast tab yet: {names}.", { names: [...unmatchedCast].join(", ") }) : "") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not create the days"))); setReload((n) => n + 1);
    } finally {
      setImporting(false);
    }
  }

  return (
    <section className="block" aria-label={L("Days")}>
      <h2>{L("Days")}</h2>
      {days === null && <p className="hint">{L("Loading…")}</p>}
      {days && days.length === 0 && <p className="hint">{L("No shoot days yet.")}</p>}
      {days && days.length > 0 && (
        <ul className="list" id="days">
          {days.map((d) => (
            <li key={d.id}>
              <a className="row" href={href({ screen: "day", productionId, callSheetId: d.id })}>
                <span className="name">{L("Day")} {d.day_number} {L("of")} {d.day_count} <span className="meta">· {d.shoot_date} · {d.unit_name}</span>{d.status === "cancelled" && <span className="tag warn">{L("CANCELLED")}</span>}{d.status === "draft" && <span className="tag">{L("DRAFT")}</span>}
                  <span className="meta day-glance">
                    {d.current_revision?.general_crew_call && <>{L("call")} <b>{d.current_revision.general_crew_call}</b></>}
                    {d.opened?.first_location_name && <> · {d.opened.first_location_name}</>}
                    {d.opened && d.opened.total > 0 && <> · <span className={d.opened.seen === d.opened.total ? "seen-all" : ""}>{L("opened {seen}/{total}", { seen: d.opened.seen, total: d.opened.total })}</span></>}
                  </span>
                </span>
                <span className="rev-badge small" data-rev={d.current_revision?.revision_letter ?? "A"}>REV {d.current_revision?.revision_letter ?? "–"}</span>
              </a>
              <div className="row-actions">
                <a className="quiet-link" href={crewLink(conn.apiBase, d.id)} target="_blank" rel="noreferrer">{L("Crew link")}</a>
                <button type="button" className="quiet" onClick={() => navigator.clipboard?.writeText(crewLink(conn.apiBase, d.id))}>{L("Copy")}</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {canPublish
        ? <div className="inline day-actions">
            <a className="button" id="newDay" href={href({ screen: "day", productionId, callSheetId: null })}>{L("+ New day")}</a>
            <label className="quiet-link" htmlFor="scheduleFile">{L("Import schedule… (.xlsx, .csv)")}</label>
            <input id="scheduleFile" type="file" accept=".xlsx,.xls,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" className="visually-hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void readScheduleFile(f); }} disabled={importing} />
          </div>
        : <p className="hint" id="readOnlyHint">{L("You can view this production; publishing needs the editor or owner role.")}</p>}
      {imported && (
        <div className="paste-crew" id="schedulePreview">
          <div className="label">{imported.fileName} · {imported.days.length === 1 ? L("1 day") : L("{n} days", { n: imported.days.length })}</div>
          <ul className="list preview">
            {imported.days.map((d, i) => {
              const dup = !!d.shoot_date && existingDates.has(d.shoot_date);
              return (
                <li key={i} className={`row static${dup || d.warnings.length ? " warn" : ""}`}>
                  <span className="name">{d.day_number ? L("Day {n}", { n: d.day_number }) : L("Imported schedule")}{d.shoot_date && <span className="meta"> · {d.shoot_date}</span>}
                    <span className="meta"> · {d.scenes.length === 1 ? L("1 scene") : L("{n} scenes", { n: d.scenes.length })} · {d.scenes.map((s) => s.scene_number).join(", ")}</span>
                    {dup && <span className="meta warn-text"> {L("· a day with this date exists, skipped")}</span>}
                    {d.warnings.map((w) => <span key={w} className="meta warn-text"> · {w}</span>)}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="hint">{L("Days are created as drafts: the crew sees nothing until you open each day, check it and publish. Locations named in the file that are not on the Locations tab yet are created there (address to fill in). The file stays on this phone.")}</p>
          <div className="inline">
            <button type="button" id="createImportedDays" className="secondary" disabled={importable.length === 0 || importing} onClick={() => void createImportedDays()}>
              {importing ? L("Creating…") : importable.length === 1 ? L("Create 1 day") : L("Create {n} days", { n: importable.length })}
            </button>
            <button type="button" className="quiet" onClick={() => setImported(null)}>{L("Cancel")}</button>
          </div>
        </div>
      )}
    </section>
  );
}

type CrewForm = { name: string; phone: string; department: string; position: string; call: string; hod: boolean; contactId: string | null };
const EMPTY_FORM: CrewForm = { name: "", phone: "", department: "", position: "", call: "", hod: false, contactId: null };

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
  const L = useL();
  const [crew, setCrew] = useState<CrewMember[] | null>(null);
  const [form, setForm] = useState<CrewForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<CrewMember | null>(null);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);
  // Edits made offline (FR-18 failure case): kept in IndexedDB and overlaid on the crew list until they sync.
  const [pending, setPending] = useState<Map<string, PendingCrewEdit>>(new Map());

  // FR-46: reuse a crew list already entered on another production instead of retyping it.
  const [copyOpen, setCopyOpen] = useState(false);
  const [otherProductions, setOtherProductions] = useState<Production[] | null>(null);
  const [copySourceId, setCopySourceId] = useState("");
  const [copySourceName, setCopySourceName] = useState("");
  const [copyPreview, setCopyPreview] = useState<CrewMember[] | null>(null);
  const [copySelected, setCopySelected] = useState<Set<string>>(new Set());
  const [copyBusy, setCopyBusy] = useState(false);

  async function toggleCopyCrew() {
    setCopyOpen((o) => !o);
    if (otherProductions === null) {
      try {
        const all = await api.listProductions(conn);
        setOtherProductions(all.filter((p) => p.id !== productionId));
      } catch (err) {
        setOtherProductions([]);
        setNotice(noticeFromError(err, "Could not load your other productions"));
      }
    }
  }

  async function pickCopySource(sourceId: string, sourceName: string) {
    setCopySourceId(sourceId);
    setCopySourceName(sourceName);
    setCopyPreview(null);
    setCopySelected(new Set());
    if (!sourceId) return;
    try {
      const people = await api.listCrew(conn, sourceId);
      setCopyPreview(people);
      const already = new Set((crew ?? []).map((m) => m.contact_id));
      setCopySelected(new Set(people.filter((m) => !already.has(m.contact_id)).map((m) => m.id)));
    } catch (err) {
      setCopyPreview([]);
      setNotice(noticeFromError(err, "Could not load that production's crew"));
    }
  }

  function toggleCopySelected(id: string) {
    setCopySelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function copySelectedCrew() {
    if (!copyPreview) return;
    setCopyBusy(true);
    const toAdd = copyPreview.filter((m) => copySelected.has(m.id));
    const added: CrewMember[] = [];
    const failed: string[] = [];
    for (const m of toAdd) {
      try {
        // Standing call times belong to a production, not to the person; never copied.
        const member = await api.createCrewMember(conn, productionId, {
          contact_id: m.contact_id, department: m.department, position: m.position, standard_call_time: null, is_head_of_department: m.is_head_of_department,
        });
        added.push(member);
      } catch {
        failed.push(m.contact.name);
      }
    }
    setCrew((c) => [...(c ?? []), ...added]);
    setCopyBusy(false);
    if (failed.length === 0) {
      setCopyOpen(false); setCopySourceId(""); setCopySourceName(""); setCopyPreview(null); setCopySelected(new Set());
    }
    setNotice(failed.length === 0
      ? { kind: "ok", text: added.length === 1 ? L("Added 1 person from {source}.", { source: copySourceName }) : L("Added {n} people from {source}.", { n: added.length, source: copySourceName }) }
      : { kind: "warn", text: L("Added {n}; could not add {names}.", { n: added.length, names: failed.join(", ") }) });
  }

  async function syncPendingEdit(edit: PendingCrewEdit, announce: boolean): Promise<void> {
    try {
      const contact = await api.updateContact(conn, edit.contactId, { name: edit.name, phone: edit.phone || null });
      const member = await api.updateCrewMember(conn, productionId, edit.memberId, {
        department: edit.department, position: edit.position, standard_call_time: edit.standard_call_time, is_head_of_department: edit.is_head_of_department,
      });
      await clearPendingCrewEdit(edit.memberId);
      setCrew((c) => (c ?? []).map((x) => (x.id === member.id ? { ...member, contact } : x)));
      setPending((p) => { if (!p.has(edit.memberId)) return p; const n = new Map(p); n.delete(edit.memberId); return n; });
      if (announce) setNotice({ kind: "ok", text: L("{name} synced.", { name: contact.name }) });
    } catch (err) {
      if (announce) setNotice(err instanceof ApiError && err.status === 0
        ? { kind: "warn", text: L("Still offline; the change stays on this phone.") }
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
    setForm({ name: m.contact.name, phone: m.contact.phone ?? "", department: m.department, position: m.position, call: m.standard_call_time ?? "", hod: m.is_head_of_department, contactId: m.contact_id });
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
        setNotice({ kind: "ok", text: L("{name} updated. The sheet shows it immediately.", { name: contact.name }) });
        cancelEdit();
      } else {
        // FR-45: a picked person is reused (their phone corrected if edited here); otherwise a new contact.
        const contact = await reuseOrCreateContact(conn, form.contactId, form.name.trim(), form.phone.trim() || null);
        const member = await api.createCrewMember(conn, productionId, {
          contact_id: contact.id, department: form.department.trim(), position: form.position.trim(), standard_call_time: form.call.trim() || null, is_head_of_department: form.hod,
        });
        setCrew((c) => [...(c ?? []), member]);
        setForm({ ...EMPTY_FORM, department: form.department });
        setNotice({ kind: "ok", text: form.hod ? L("{name} added as head of department.", { name: contact.name }) : L("{name} added.", { name: contact.name }) });
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
        setNotice({ kind: "warn", text: L("No connection. The change is kept on this phone as not saved; it will sync when you are back online.") });
        cancelEdit();
      } else {
        setNotice(noticeFromError(err, editing ? L("Could not save the changes") : L("Could not add the crew member")));
      }
    } finally {
      setBusy(false);
    }
  }

  // FR-31: paste the whole list. Rows are created one by one so a failure names the person, not the batch.
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  // FR-55: a spreadsheet file (parsed in the browser, never uploaded) feeds the same preview as a paste.
  const [fileRows, setFileRows] = useState<unknown[][] | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileMap, setFileMap] = useState<{ headerIndex: number; map: ColumnMap } | null>(null);
  async function readCrewFile(file: File) {
    try {
      const XLSX = await import("xlsx");
      const wb = XLSX.read(await file.arrayBuffer(), { type: "array" });
      const sheet = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, raw: false, defval: "" });
      const detected = detectColumns(rows);
      setFileRows(rows); setFileName(file.name); setPasteText("");
      setFileMap(detected ?? { headerIndex: 0, map: {} });
      if (!detected) setNotice({ kind: "warn", text: L("Which column has the names? Pick it below; the first row is treated as the header.") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not read that file")));
    }
  }
  // FR-57: an old call sheet PDF goes to the API (text extraction, Claude when configured) and comes back as candidates.
  const [pdfRows, setPdfRows] = useState<{ fileName: string; method: string; rows: ParsedCrewRow[]; warnings: string[] } | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  async function readCallSheetPdf(file: File) {
    setPdfBusy(true);
    try {
      const result = await api.importCallSheetPdf(conn, productionId, file);
      const known = new Set((crew ?? []).map((m) => m.contact.name.trim().toLowerCase()));
      const rows: ParsedCrewRow[] = result.contacts.map((c, i) => {
        const warnings = [...c.warnings];
        if (known.has(c.name.trim().toLowerCase())) warnings.push("already on the crew");
        return { line: i + 1, name: c.name, department: c.department ?? "General", position: c.position ?? "Crew", phone: c.phone, hod: false, warning: warnings.length ? warnings.join("; ") : null };
      });
      setPdfRows({ fileName: file.name, method: result.method, rows, warnings: result.warnings });
      clearFile(); setPasteText("");
      if (rows.length === 0) setNotice({ kind: "warn", text: result.warnings[0] ?? L("No contacts found in that PDF.") });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not read that call sheet")));
    } finally {
      setPdfBusy(false);
    }
  }
  const knownNames = (crew ?? []).map((m) => m.contact.name);
  const parsed = !pasteOpen ? []
    : pdfRows ? pdfRows.rows
    : fileRows && fileMap ? (fileMap.map.name === undefined ? [] : rowsToCrew(fileRows, fileMap.headerIndex, fileMap.map, knownNames))
    : parseCrewList(pasteText, knownNames);
  const toImport = importableRows(parsed);
  const fileHeaders = fileRows && fileMap ? (fileRows[fileMap.headerIndex] ?? []).map((h, i) => (String(h ?? "").trim() || `Column ${columnLetter(i)}`)) : [];
  const clearFile = () => { setFileRows(null); setFileMap(null); setFileName(""); };
  async function importPasted() {
    setBusy(true);
    const added: CrewMember[] = [];
    const failed: string[] = [];
    for (const row of toImport) {
      try {
        // FR-45: the same person on another production (same name and phone digits) is reused, not duplicated.
        const match = (await api.searchContacts(conn, row.name).catch(() => []))
          .find((c) => c.name.trim().toLowerCase() === row.name.toLowerCase() && !!row.phone && whatsappNumber(c.phone) === whatsappNumber(row.phone));
        const contact = match ?? await api.createContact(conn, { name: row.name, phone: row.phone, email: null });
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
    if (failed.length === 0) { setPasteText(""); clearFile(); setPdfRows(null); setPasteOpen(false); }
    else { clearFile(); setPdfRows(null); setPasteText(parsed.filter((r) => failed.includes(r.name)).map((r) => `${r.department}: ${r.name}, ${r.position}${r.phone ? `, ${r.phone}` : ""}`).join("\n")); }
    setNotice(failed.length === 0
      ? { kind: "ok", text: added.length === 1 ? L("Added 1 person to the crew.") : L("Added {n} people to the crew.", { n: added.length }) }
      : { kind: "warn", text: L("Added {n}; could not add {names}. They stay in the box so you can try again.", { n: added.length, names: failed.join(", ") }) });
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
      setNotice({ kind: "ok", text: L("{name} removed.", { name: m.contact.name }) });
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
      setNotice({ kind: "ok", text: L("Photo updated for {name}.", { name: m.contact.name }) });
    } catch (err) {
      // A failed upload never touches the rest of the person's saved fields.
      setNotice(noticeFromError(err, L("Could not upload the photo")));
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
      setNotice(noticeFromError(err, L("Could not remove the photo")));
    } finally {
      setPhotoBusy(false);
    }
  }

  const canSave = form.name.trim() && form.department.trim() && form.position.trim() && !busy;
  return (
    <section className="block" aria-label={L("Crew")}>
      <h2>{L("Crew")}</h2>
      {crew === null && <p className="hint">{L("Loading…")}</p>}
      {crew && crew.length === 0 && (
        <p className="hint">No crew yet. Heads of department appear on every call sheet under "Who to call".{canEdit && " Paste a list, import a file, or copy the crew from another production."}</p>
      )}
      {visibleCrew && visibleCrew.length > 0 && (
        <ul className="list" id="crew">
          {visibleCrew.map((m) => (
            <li key={m.id} className={`row static${editing?.id === m.id ? " editing" : ""}`}>
              <span className="name crew-name">
                <Avatar name={m.contact.name} photoUrl={m.contact.photo_url} size={28} />
                <span>{m.contact.name}{m.is_head_of_department && <span className="tag">HoD</span>}
                  {pending.has(m.id) && <span className="tag warn" id={`notSaved-${m.id}`}>{L("not saved")}</span>}
                  <span className="meta"> · {m.department} · {m.position}{m.contact.phone ? ` · ${m.contact.phone}` : ""}{m.standard_call_time ? ` · call ${m.standard_call_time}` : ""}</span>
                </span>
              </span>
              {canEdit && (
                <span className="row-actions">
                  {pending.has(m.id) && (
                    <button type="button" className="quiet" onClick={() => void syncPendingEdit(pending.get(m.id)!, true)} aria-label={L("Sync {name}", { name: m.contact.name })}>{L("Sync")}</button>
                  )}
                  <button type="button" className="quiet" onClick={() => { void navigator.clipboard?.writeText(personalLink(conn.apiBase, m.personal_token)); setNotice({ kind: "ok", text: L("{name}'s link copied. One link for the whole shoot; it always opens their next day.", { name: m.contact.name }) }); }} aria-label={L("Copy link for {name}", { name: m.contact.name })}>{L("Link")}</button>
                  {whatsappNumber(m.contact.phone) && (
                    <a className="quiet-link whatsapp" href={whatsappUrl(whatsappNumber(m.contact.phone), onboardingMessageText(productionName, m, personalLink(conn.apiBase, m.personal_token)))}
                      target="_blank" rel="noreferrer" aria-label={L("Send link to {name} on WhatsApp", { name: m.contact.name })}>{L("WhatsApp")}</a>
                  )}
                  <button type="button" className="quiet" onClick={() => startEdit(m)} aria-label={L("Edit {name}", { name: m.contact.name })}>{L("Edit")}</button>
                  <button type="button" className="quiet danger" onClick={() => void remove(m)} aria-label={L("Remove {name}", { name: m.contact.name })}>{L("Remove")}</button>
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
            setNotice({ kind: "ok", text: L("{n} links copied, one per line with the name. Each person's link is theirs alone; send them one by one, not to the group.", { n: visibleCrew.length }) });
          }}>{L("Copy all links")}</button>
          <span className="hint">{L("Each link is personal: it shows that person's call and counts as them opening the sheet. WhatsApp sends it to them directly.")}</span>
        </div>
      )}
      {canEdit && (<>
      <h3 className="subhead" id="crewFormTitle">{editing ? L("Editing {name}", { name: editing.contact.name }) : L("Add a person")}</h3>
      {editing && (
        <div className="inline photo-field" id="crewPhotoField">
          <Avatar name={editing.contact.name} photoUrl={editing.contact.photo_url} size={48} />
          <button type="button" className="quiet" disabled={photoBusy} onClick={() => photoInputRef.current?.click()}>
            {photoBusy ? "Uploading…" : editing.contact.photo_url ? "Change photo" : "Add photo"}
          </button>
          {editing.contact.photo_url && (
            <button type="button" className="quiet danger" disabled={photoBusy} onClick={() => void removePhoto(editing)}>{L("Remove photo")}</button>
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
        <label className="field" htmlFor="crewName"><span className="label">{L("Name")}</span>
          {editing
            ? <input id="crewName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            : <PersonPicker conn={conn} id="crewName" value={form.name} onChange={(name) => setForm({ ...form, name, contactId: null })}
                onPick={(c) => setForm({ ...form, name: c.name, phone: c.phone ?? "", contactId: c.id })} />}
        </label>
        <label className="field" htmlFor="crewPhone"><span className="label">{L("Phone")}</span><input id="crewPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
        <label className="field" htmlFor="crewDept"><span className="label">{L("Department")}</span><input id="crewDept" placeholder="Camera" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></label>
        <label className="field" htmlFor="crewPos"><span className="label">{L("Position")}</span><input id="crewPos" placeholder="DoP" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
        <label className="field" htmlFor="crewCall"><span className="label">{L("Personal call (optional)")}</span><input id="crewCall" className="mono" placeholder="05:45" value={form.call} onChange={(e) => setForm({ ...form, call: e.target.value })} /></label>
      </div>
      <label className="check"><input id="crewHod" type="checkbox" checked={form.hod} onChange={(e) => setForm({ ...form, hod: e.target.checked })} /> {L("Head of department (shown under \"Who to call\")")}</label>
      <div className="inline">
        <button type="button" id="addCrew" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? L("Save changes") : L("Add to crew")}</button>
        {editing && <button type="button" className="quiet" id="cancelEdit" onClick={cancelEdit}>{L("Cancel")}</button>}
        {!editing && <button type="button" className="quiet" id="pasteCrew" onClick={() => setPasteOpen((o) => !o)}>{pasteOpen ? L("Close the list") : L("Paste a list…")}</button>}
        {!editing && <button type="button" className="quiet" id="copyCrew" onClick={() => void toggleCopyCrew()}>{copyOpen ? L("Close") : L("Copy crew from…")}</button>}
      </div>
      {copyOpen && !editing && (
        <div className="paste-crew" id="copyCrewPanel">
          {otherProductions === null && <p className="hint">{L("Loading your other productions…")}</p>}
          {otherProductions && otherProductions.length === 0 && <p className="hint">{L("No other productions yet — crew from a future one can be copied here.")}</p>}
          {otherProductions && otherProductions.length > 0 && (
            <label className="field" htmlFor="copySource"><span className="label">{L("Copy crew from")}</span>
              <select id="copySource" value={copySourceId} onChange={(e) => void pickCopySource(e.target.value, e.target.selectedOptions[0]?.text ?? "")}>
                <option value="">{L("— pick a production —")}</option>
                {otherProductions.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          )}
          {copyPreview && copyPreview.length === 0 && <p className="hint">{L("That production has no crew yet.")}</p>}
          {copyPreview && copyPreview.length > 0 && (
            <ul className="list preview" id="copyPreview">
              {copyPreview.map((m) => {
                const already = (crew ?? []).some((x) => x.contact_id === m.contact_id);
                return (
                  <li key={m.id} className={`row static${already ? " warn" : ""}`}>
                    <label className="check">
                      <input type="checkbox" checked={copySelected.has(m.id)} disabled={already} onChange={() => toggleCopySelected(m.id)} />
                      {m.contact.name}{m.is_head_of_department && <span className="tag">HoD</span>}
                      <span className="meta"> · {m.department} · {m.position}</span>
                      {already && <span className="meta warn-text"> {L("· already on this crew")}</span>}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {copyPreview && copyPreview.length > 0 && (
            <div className="inline">
              <button type="button" id="copyCrewSubmit" className="secondary" disabled={copySelected.size === 0 || copyBusy} onClick={() => void copySelectedCrew()}>
                {copyBusy ? L("Adding…") : copySelected.size === 1 ? L("Add 1 person") : L("Add {n} people", { n: copySelected.size })}
              </button>
            </div>
          )}
        </div>
      )}
      {pasteOpen && !editing && (
        <div className="paste-crew" id="pasteCrewPanel">
          <p className="hint">{L("One person per line: name, position, phone — or name, department, position, phone. A line like \"Camera:\" sets the department for the lines below. \"HoD\" marks a head of department.")}</p>
          {!fileRows && !pdfRows && <textarea id="pasteCrewText" rows={6} placeholder={"Camera:\nJan Novák, DoP, 777 123 456, HoD\nPetra K., 1st AC\nElectric:\nTomáš Novák, Gaffer"} value={pasteText} onChange={(e) => setPasteText(e.target.value)} disabled={busy} />}
          <div className="inline file-import">
            <label className="quiet-link" htmlFor="crewFile">{fileRows ? L("File: {name}", { name: fileName }) : L("…or import a file (.xlsx, .csv)")}</label>
            <input id="crewFile" type="file" accept=".xlsx,.xls,.csv,.numbers,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" className="visually-hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void readCrewFile(f); }} disabled={busy} />
            {fileRows && <button type="button" className="quiet" onClick={clearFile}>{L("Use paste instead")}</button>}
            <label className="quiet-link" htmlFor="callSheetPdf">{pdfBusy ? L("Reading the PDF…") : pdfRows ? L("PDF: {name}", { name: pdfRows.fileName }) : L("…or an old call sheet PDF")}</label>
            <input id="callSheetPdf" type="file" accept=".pdf,application/pdf" className="visually-hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void readCallSheetPdf(f); }} disabled={busy || pdfBusy} />
            {pdfRows && <button type="button" className="quiet" onClick={() => setPdfRows(null)}>{L("Discard")}</button>}
          </div>
          <p className="hint"><a href="privacy.html" target="_blank" rel="noreferrer" id="privacyLink">{L("What FilmRunner stores about the people you add, where, and who sees it")}</a></p>
          {pdfRows && (
            <p className="hint" id="pdfHint">
              {pdfRows.method === "claude" ? L("Read by Claude from the PDF's text") : L("Read by the plain-text pass")} · {L("{n} people found. Check names and numbers before adding; nothing is created until you do. The PDF is not stored.", { n: pdfRows.rows.length })}
              {pdfRows.warnings.map((w) => <span key={w} className="warn-text"> · {w}</span>)}
            </p>
          )}
          {fileRows && fileMap && (
            <div className="column-map" id="columnMap">
              {(["name", "phone", "department", "position"] as Role[]).map((role) => (
                <label key={role} className="field" htmlFor={`col-${role}`}>
                  <span className="label">{role === "name" ? "Name column" : role === "phone" ? "Phone" : role === "department" ? "Department" : "Position"}{role === "name" ? " *" : ""}</span>
                  <select id={`col-${role}`} value={fileMap.map[role] ?? ""} onChange={(e) => setFileMap({ ...fileMap, map: { ...fileMap.map, [role]: e.target.value === "" ? undefined : Number(e.target.value) } })}>
                    <option value="">—</option>
                    {fileHeaders.map((h, i) => <option key={i} value={i}>{h}</option>)}
                  </select>
                </label>
              ))}
              <p className="hint">{fileMap.map.name === undefined ? L("Which column has the names? Pick it to see the preview.") : L("Header row {row}; {n} rows below it. The file stays on this phone.", { row: fileMap.headerIndex + 1, n: fileRows.length - fileMap.headerIndex - 1 })}</p>
            </div>
          )}
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
              {busy ? L("Adding…") : toImport.length === 1 ? L("Add 1 person") : L("Add {n} people", { n: toImport.length })}
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
  const L = useL();
  const [name, setName] = useState(production.name);
  const [status, setStatus] = useState(production.status);
  const [busy, setBusy] = useState(false);
  const changed = name.trim() !== production.name || status !== production.status;
  async function save() {
    setBusy(true);
    try {
      const updated = await api.updateProduction(conn, production.id, { name: name.trim(), status });
      onUpdated(updated);
      setNotice({ kind: "ok", text: L("Saved. {name} is {status}.", { name: updated.name, status: L(updated.status) }) });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not save the production")));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="block" aria-label={L("Settings")}>
      <h2>{L("Settings")}</h2>
      <div className="grid2">
        <label className="field" htmlFor="productionName"><span className="label">{L("Name")}</span><input id="productionName" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="field" htmlFor="productionStatus"><span className="label">{L("Status")}</span>
          <select id="productionStatus" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="prep">{L("prep")}</option><option value="shooting">{L("shooting")}</option><option value="wrapped">{L("wrapped")}</option>
          </select>
        </label>
      </div>
      <p className="hint">{L("Wrapped productions stay readable; every link keeps working. Days are never deleted — cancel a day from its own screen.")}</p>
      <div className="inline">
        <button type="button" id="saveProduction" className="secondary" disabled={!changed || !name.trim() || busy} onClick={() => void save()}>{L("Save")}</button>
      </div>
    </section>
  );
}

type CastForm = { name: string; phone: string; character: string; pickup: string; contactId: string | null };
const EMPTY_CAST_FORM: CastForm = { name: "", phone: "", character: "", pickup: "", contactId: null };

/** FR-33: the people in front of the camera. Per-day times are set on the day (status, pickup, M/H, on set). */
function Cast({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const L = useL();
  const [cast, setCast] = useState<CastMember[] | null>(null);
  const [form, setForm] = useState<CastForm>(EMPTY_CAST_FORM);
  const [editing, setEditing] = useState<CastMember | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.listCast(conn, productionId).then((c) => { if (!cancelled) setCast(c); }).catch((err) => { if (!cancelled) setNotice(noticeFromError(err, L("Could not load the cast"))); });
    return () => { cancelled = true; };
  }, [conn, productionId, setNotice]);

  function startEdit(a: CastMember) {
    setEditing(a);
    setForm({ name: a.contact.name, phone: a.contact.phone ?? "", character: a.character_name, pickup: a.standard_pickup_time ?? "", contactId: a.contact_id });
  }
  function cancelEdit() { setEditing(null); setForm(EMPTY_CAST_FORM); }

  async function save() {
    setBusy(true);
    try {
      if (editing) {
        const contact = await api.updateContact(conn, editing.contact_id, { name: form.name.trim(), phone: form.phone.trim() || null });
        const actor = await api.updateCastMember(conn, productionId, editing.id, { character_name: form.character.trim(), standard_pickup_time: form.pickup.trim() || null });
        setCast((c) => (c ?? []).map((x) => (x.id === actor.id ? { ...actor, contact } : x)));
        setNotice({ kind: "ok", text: L("{name} updated.", { name: contact.name }) });
        cancelEdit();
      } else {
        const contact = await reuseOrCreateContact(conn, form.contactId, form.name.trim(), form.phone.trim() || null);
        const actor = await api.createCastMember(conn, productionId, { contact_id: contact.id, character_name: form.character.trim(), standard_pickup_time: form.pickup.trim() || null });
        setCast((c) => [...(c ?? []), actor]);
        setForm(EMPTY_CAST_FORM);
        setNotice({ kind: "ok", text: L("{name} added as {character}. Set their times on each day.", { name: contact.name, character: actor.character_name }) });
      }
    } catch (err) {
      setNotice(noticeFromError(err, editing ? L("Could not save the changes") : L("Could not add the cast member")));
    } finally {
      setBusy(false);
    }
  }

  async function remove(a: CastMember) {
    setBusy(true);
    try {
      await api.deleteCastMember(conn, productionId, a.id);
      setCast((c) => (c ?? []).filter((x) => x.id !== a.id));
      setNotice({ kind: "ok", text: L("{name} removed from the cast. Their lines drop from the sheets.", { name: a.contact.name }) });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not remove the cast member")));
    } finally {
      setBusy(false);
    }
  }

  const canSave = form.name.trim() && form.character.trim() && !busy;
  return (
    <section className="block" aria-label={L("Cast")}>
      <h2>{L("Cast")}</h2>
      {cast === null && <p className="hint">{L("Loading…")}</p>}
      {cast && cast.length === 0 && <p className="hint">{L("No cast yet. Add the actors once; each day then gets its own status, pickup, make-up and on-set times.")}</p>}
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
                  <button type="button" className="quiet" onClick={() => startEdit(a)} aria-label={L("Edit {name}", { name: a.contact.name })}>{L("Edit")}</button>
                  <button type="button" className="quiet danger" disabled={busy} onClick={() => void remove(a)} aria-label={L("Remove {name}", { name: a.contact.name })}>{L("Remove")}</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (<>
        <h3 className="subhead" id="castFormTitle">{editing ? L("Editing {name}", { name: editing.contact.name }) : L("Add an actor")}</h3>
        <div className="grid2">
          <label className="field" htmlFor="castName"><span className="label">{L("Name")}</span>
            {editing
              ? <input id="castName" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              : <PersonPicker conn={conn} id="castName" value={form.name} onChange={(name) => setForm({ ...form, name, contactId: null })}
                  onPick={(c) => setForm({ ...form, name: c.name, phone: c.phone ?? "", contactId: c.id })} />}
          </label>
          <label className="field" htmlFor="castCharacter"><span className="label">{L("Character")}</span><input id="castCharacter" placeholder="MARTA" value={form.character} onChange={(e) => setForm({ ...form, character: e.target.value })} /></label>
          <label className="field" htmlFor="castPhone"><span className="label">{L("Phone")}</span><input id="castPhone" className="mono" inputMode="tel" placeholder="+420 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
          <label className="field" htmlFor="castPickup"><span className="label">{L("Usual pickup (optional)")}</span><input id="castPickup" className="mono" placeholder="05:30" value={form.pickup} onChange={(e) => setForm({ ...form, pickup: e.target.value })} /></label>
        </div>
        <div className="inline">
          <button type="button" id="addCast" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? L("Save changes") : L("Add to cast")}</button>
          {editing && <button type="button" className="quiet" onClick={cancelEdit}>{L("Cancel")}</button>}
        </div>
      </>)}
    </section>
  );
}

type LocationForm = { name: string; address: string; parking_notes: string; nearest_hospital: string };
const EMPTY_LOCATION_FORM: LocationForm = { name: "", address: "", parking_notes: "", nearest_hospital: "" };

function Locations({ conn, productionId, canEdit, setNotice }: { conn: Connection; productionId: string; canEdit: boolean; setNotice: (n: Notice) => void }) {
  const L = useL();
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

  async function remove(l: Location) {
    if (!window.confirm(`Remove ${l.name}? Scenes that used it keep their text but lose the link.`)) return;
    try {
      await api.deleteLocation(conn, productionId, l.id);
      setLocations((ls) => (ls ?? []).filter((x) => x.id !== l.id));
      if (editing?.id === l.id) cancelEdit();
      setNotice({ kind: "ok", text: L("{name} removed.", { name: l.name }) });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not remove"));
    }
  }

  async function save() {
    setBusy(true);
    try {
      if (editing) {
        const updated = await api.updateLocation(conn, productionId, editing.id, {
          name: form.name.trim(), address: form.address.trim() || null,
          parking_notes: form.parking_notes.trim() || null, nearest_hospital: form.nearest_hospital.trim() || null,
        } satisfies LocationUpdate);
        setLocations((ls) => (ls ?? []).map((x) => (x.id === updated.id ? updated : x)));
        setNotice({ kind: "ok", text: L("{name} updated.", { name: updated.name }) });
        cancelEdit();
      } else {
        const created = await api.createLocation(conn, productionId, {
          name: form.name.trim(), address: form.address.trim() || null,
          parking_notes: form.parking_notes.trim() || null, nearest_hospital: form.nearest_hospital.trim() || null,
        });
        setLocations((ls) => [...(ls ?? []), created]);
        setForm(EMPTY_LOCATION_FORM);
        setNotice({ kind: "ok", text: !created.address ? L("{name} added.", { name: created.name }) : created.geocoded_display_name ? L("{name} added, resolved to {place}.", { name: created.name, place: created.geocoded_display_name }) : L("{name} added, could not resolve that address — check it.", { name: created.name }) });
      }
    } catch (err) {
      setNotice(noticeFromError(err, editing ? L("Could not save the changes") : L("Could not add the location")));
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
      if (!suggestion) setNotice({ kind: "warn", text: L("No hospital suggestion nearby; enter one by hand.") });
    } catch (err) {
      setNotice(noticeFromError(err, "Could not get a suggestion"));
    } finally {
      setSuggesting(false);
    }
  }

  const canSave = form.name.trim() && !busy;
  return (
    <section className="block" aria-label={L("Locations")}>
      <h2>{L("Locations")}</h2>
      <p className="hint">{L("An address is geocoded on save so a scene can be tied to it for sunrise/sunset and a nearby hospital can be suggested.")}</p>
      {locations === null && <p className="hint">{L("Loading…")}</p>}
      {locations && locations.length === 0 && <p className="hint">{L("No locations yet.")}</p>}
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
                  <button type="button" className="quiet" onClick={() => startEdit(l)} aria-label={L("Edit {name}", { name: l.name })}>{L("Edit")}</button>
                  <button type="button" className="quiet danger" onClick={() => void remove(l)} aria-label={L("Remove {name}", { name: l.name })}>{L("Remove")}</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (<>
      <h3 className="subhead" id="locationFormTitle">{editing ? L("Editing {name}", { name: editing.name }) : L("Add a location")}</h3>
      <div className="grid2">
        <label className="field" htmlFor="locName"><span className="label">{L("Name")}</span><input id="locName" placeholder="Riverbank, Troja" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field" htmlFor="locAddress"><span className="label">{L("Address")}</span><input id="locAddress" placeholder="Nábřeží, Praha" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></label>
      </div>
      {editing?.address === form.address && editing?.geocoded_display_name && (
        <p className="hint">Resolved to: {editing.geocoded_display_name}. Wrong place? Change the address and save again.</p>
      )}
      <label className="field" htmlFor="locParking"><span className="label">{L("Parking notes")}</span><input id="locParking" value={form.parking_notes} onChange={(e) => setForm({ ...form, parking_notes: e.target.value })} /></label>
      <label className="field" htmlFor="locHospital"><span className="label">{L("Nearest hospital")}</span><input id="locHospital" value={form.nearest_hospital} onChange={(e) => setForm({ ...form, nearest_hospital: e.target.value })} /></label>
      {editing && editing.geo_lat != null && (
        <div className="inline">
          <button type="button" className="quiet" disabled={suggesting} onClick={() => void suggestHospital()}>{suggesting ? L("Looking…") : L("Suggest nearest hospital")}</button>
          {hospitalSuggestion && (
            <button type="button" className="quiet" onClick={() => { setForm({ ...form, nearest_hospital: hospitalSuggestion }); setHospitalSuggestion(null); }}>
              Use: {hospitalSuggestion}
            </button>
          )}
        </div>
      )}
      <div className="inline">
        <button type="button" id="addLocation" className="secondary" disabled={!canSave} onClick={() => void save()}>{editing ? L("Save changes") : L("Add location")}</button>
        {editing && <button type="button" className="quiet" id="cancelLocationEdit" onClick={cancelEdit}>{L("Cancel")}</button>}
      </div>
      </>)}
    </section>
  );
}

function Members({ conn, productionId, setNotice }: { conn: Connection; productionId: string; setNotice: (n: Notice) => void }) {
  const L = useL();
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
      setNotice({ kind: "ok", text: L(m.role === "viewer" ? "{email} can now view. They sign in with that email." : m.role === "editor" ? "{email} can now edit and publish. They sign in with that email." : "{email} can now do everything. They sign in with that email.", { email: m.email }) });
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
      setNotice(noticeFromError(err, L("Could not remove the member")));
    }
  }

  return (
    <section className="block" aria-label={L("Members")}>
      <h2>{L("Members")}</h2>
      <p className="hint">{L("Owner: everything, incl. members. Editor: days, crew, publish. Viewer: read only.")}</p>
      {members === null && <p className="hint">{L("Loading…")}</p>}
      {members && members.length > 0 && (
        <ul className="list" id="members">
          {members.map((m) => (
            <li key={m.id} className="row static">
              <span className="name">{m.email}<span className="tag">{m.role}</span>{!m.user_id && <span className="meta"> {L("· not signed in yet")}</span>}</span>
              <button type="button" className="quiet danger" onClick={() => void remove(m)} aria-label={L("Remove {name}", { name: m.email })}>{L("Remove")}</button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid2">
        <label className="field" htmlFor="memberEmail"><span className="label">{L("Email")}</span><input id="memberEmail" type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field" htmlFor="memberRole"><span className="label">{L("Role")}</span>
          <select id="memberRole" value={role} onChange={(e) => setRole(e.target.value as ProductionRole)}>
            <option value="editor">{L("editor")}</option><option value="viewer">{L("viewer")}</option><option value="owner">{L("owner")}</option>
          </select>
        </label>
      </div>
      <button type="button" id="addMember" className="secondary" disabled={!email.includes("@") || busy} onClick={() => void add()}>{L("Invite")}</button>
    </section>
  );
}
