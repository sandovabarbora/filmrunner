import { useState } from "react";
import { api, type Connection } from "../api";
import { href } from "../route";
import { noticeFromError, type Notice } from "../EditorApp";
import type { Production } from "../../types";
import { useL } from "../lang";
import { DashboardPanel } from "./Dashboard";

export function ProductionsScreen({ conn, productions, onCreated, setNotice }: {
  conn: Connection; productions: Production[] | null; onCreated: (p: Production) => void; setNotice: (n: Notice) => void;
}) {
  const L = useL();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      const p = await api.createProduction(conn, name.trim());
      onCreated(p);
      setName("");
      window.location.hash = href({ screen: "production", productionId: p.id, tab: "days" });
    } catch (err) {
      setNotice(noticeFromError(err, L("Could not create the production")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
    {productions && productions.length > 0 && <DashboardPanel conn={conn} />}
    <section className="block" aria-label={L("Productions")}>
      <h2>{L("Productions")}</h2>
      {productions === null && <p className="hint">{L("Loading…")}</p>}
      {productions && productions.length === 0 && (
        <div className="intro" id="intro">
          <p>{L("A production holds its crew and its shoot days. Create one, add the crew once, then publish a call sheet per day; every revision reaches the same link.")}</p>
        </div>
      )}
      {productions && productions.length > 0 && (
        <ul className="list" id="productions">
          {productions.map((p) => (
            <li key={p.id}>
              <a className="row" href={href({ screen: "production", productionId: p.id, tab: "days" })}>
                <span className="name">{p.name}</span>
                {p.status !== "prep" && <span className="meta">{L(p.status)}</span>}
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="inline">
        <input id="newProduction" placeholder={L("New production name")} value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) void create(); }} />
        <button type="button" id="createProduction" className="secondary" disabled={!name.trim() || busy} onClick={() => void create()}>{L("Create")}</button>
      </div>
    </section>
    </>
  );
}
