import { useEffect, useState } from "react";
import { api, type Connection } from "./api";
import { daysInRange, formatDays } from "./availability";
import { noticeFromError, type Notice } from "./EditorApp";
import { useL, useLang } from "./lang";
import { pragueToday } from "./pragueDate";
import type { CastAgreement, CastAgreementCreate, CastMember } from "../types";

type Form = { from: string; to: string; by: CastAgreementCreate["agreed_by"]; via: CastAgreementCreate["agreed_via"]; on: string; note: string };

/** FR-228: what an actor agreed to, with who, how and when. Withdrawn agreements stay listed, struck through. */
export function AgreedDays({ conn, productionId, actor, canEdit, setNotice }: {
  conn: Connection; productionId: string; actor: CastMember; canEdit: boolean; setNotice: (n: Notice) => void;
}) {
  const L = useL();
  const lang = useLang();
  const [agreements, setAgreements] = useState<CastAgreement[] | null>(null);
  const [form, setForm] = useState<Form>({ from: "", to: "", by: "agent", via: "email", on: pragueToday(), note: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.listAgreements(conn, productionId, actor.id).then((a) => { if (!cancelled) setAgreements(a); })
      .catch((err) => { if (!cancelled) { setAgreements([]); setNotice(noticeFromError(err, L("Could not load the agreed days"))); } });
    return () => { cancelled = true; };
  }, [conn, productionId, actor.id, setNotice]);

  const days = daysInRange(form.from, form.to);
  const by = { actor: L("the actor"), agent: L("the agent"), production: L("production") };
  const via = { email: L("by email"), phone: L("by phone"), in_person: L("in person"), other: L("another way") };
  const active = (agreements ?? []).filter((a) => !a.withdrawn_at);
  const withdrawn = (agreements ?? []).filter((a) => a.withdrawn_at);

  async function add() {
    setBusy(true);
    try {
      const created = await api.createAgreement(conn, productionId, actor.id, { days, agreed_by: form.by, agreed_via: form.via, agreed_on: form.on, note: form.note.trim() || null });
      setAgreements((a) => [created, ...(a ?? [])]);
      setForm({ ...form, from: "", to: "", note: "" });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not save the agreed days")));
    } finally {
      setBusy(false);
    }
  }

  async function withdraw(a: CastAgreement) {
    setBusy(true);
    try {
      const done = await api.withdrawAgreement(conn, productionId, actor.id, a.id);
      setAgreements((all) => (all ?? []).map((x) => (x.id === done.id ? done : x)));
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not withdraw the agreement")));
    } finally {
      setBusy(false);
    }
  }

  const line = (a: CastAgreement) => L("{days} · agreed by {who} {how} on {on}", { days: formatDays(a.days, lang), who: by[a.agreed_by], how: via[a.agreed_via], on: formatDays([a.agreed_on], lang) });

  return (
    <div className="agreed" id={`agreed-${actor.id}`}>
      {agreements === null && <p className="hint">{L("Loading…")}</p>}
      {agreements && active.length === 0 && <p className="hint warn-text">{L("No agreed days entered. Days with {name} will say so instead of looking fine.", { name: actor.contact.name })}</p>}
      {active.length > 0 && (
        <ul className="agreed-list" aria-label={L("Agreed days of {name}", { name: actor.contact.name })}>
          {active.map((a) => (
            <li key={a.id}>
              <span>{line(a)}{a.note ? <span className="meta"> · {a.note}</span> : null}</span>
              {canEdit && <button type="button" className="quiet" disabled={busy} onClick={() => void withdraw(a)}>{L("Withdraw")}</button>}
            </li>
          ))}
        </ul>
      )}
      {withdrawn.length > 0 && (
        <details className="others">
          <summary>{L("Withdrawn ({n})", { n: withdrawn.length })}</summary>
          <ul className="agreed-list">
            {withdrawn.map((a) => <li key={a.id}><s>{line(a)}</s><span className="meta"> · {L("withdrawn {when}", { when: new Date(a.withdrawn_at!).toLocaleDateString() })}{a.withdrawn_by ? ` · ${a.withdrawn_by}` : ""}</span></li>)}
          </ul>
        </details>
      )}
      {canEdit && (<>
        <div className="grid2">
          <label className="field"><span className="label">{L("From")}</span><input type="date" aria-label={L("Agreed from")} value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} /></label>
          <label className="field"><span className="label">{L("To (optional)")}</span><input type="date" aria-label={L("Agreed to")} min={form.from} value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} /></label>
          <label className="field"><span className="label">{L("Who agreed")}</span>
            <select value={form.by} onChange={(e) => setForm({ ...form, by: e.target.value as Form["by"] })}>
              {(Object.keys(by) as Form["by"][]).map((k) => <option key={k} value={k}>{by[k]}</option>)}
            </select>
          </label>
          <label className="field"><span className="label">{L("How")}</span>
            <select value={form.via} onChange={(e) => setForm({ ...form, via: e.target.value as Form["via"] })}>
              {(Object.keys(via) as Form["via"][]).map((k) => <option key={k} value={k}>{via[k]}</option>)}
            </select>
          </label>
          <label className="field"><span className="label">{L("Agreed on")}</span><input type="date" value={form.on} max={pragueToday()} onChange={(e) => setForm({ ...form, on: e.target.value })} /></label>
          <label className="field"><span className="label">{L("Note (optional)")}</span><input maxLength={300} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
        </div>
        {form.from && days.length === 0 && <p className="hint warn-text">{L("That range does not work: the end is before the start, or it is longer than 120 days.")}</p>}
        <button type="button" className="secondary" disabled={busy || days.length === 0 || !form.on} onClick={() => void add()}>
          {days.length ? L("Add {n} agreed days", { n: days.length }) : L("Add agreed days")}
        </button>
      </>)}
    </div>
  );
}
