import { useContext, useEffect, useState } from "react";
import { StillBackground } from "../../CallSheetView";
import { fmtDate } from "../../i18n";
import type { Dashboard, DashboardItem } from "../../types";
import { api, type Connection } from "../api";
import { LangContext, type L } from "../lang";
import { href } from "../route";

/** Czech needs three forms; English text is the key, so each form has its own English wording. */
function byCount(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  return n >= 2 && n <= 4 ? few : many;
}

function localIso(d: Date): string {
  const pad = (v: number) => String(v).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function DayWhen({ date, call }: { date: string; call: string | null | undefined }) {
  const { lang, L } = useContext(LangContext);
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  const day = date === localIso(today) ? L("today") : date === localIso(tomorrow) ? L("tomorrow") : fmtDate(lang, date);
  return <span className="dash-when">{day}{call ? ` ${call}` : ""}</span>;
}

function Item({ item, L }: { item: DashboardItem; L: L }) {
  const missing = item.total - item.confirmed;
  return (
    <li>
      <a className="dash-item" data-kind={item.kind} href={href({ screen: "day", productionId: item.production_id, callSheetId: item.call_sheet_id })}>
        <span className="dash-film">
          <b>{item.production_name}</b>
          {item.revision_letter && <span className="rev-badge small" data-rev={item.revision_letter}>REV {item.revision_letter}</span>}
          <DayWhen date={item.shoot_date} call={item.crew_call} />
        </span>
        {item.kind === "unconfirmed" ? (
          <>
            <span className="dash-what">{L(byCount(missing, "{n} person has not confirmed", "{n} people have not confirmed", "{n} people still have not confirmed"), { n: missing })}</span>
            <span className="dash-detail">{L("{c} of {t} confirmed", { c: item.confirmed, t: item.total })}{item.not_opened > 0 ? ` · ${L("Not opened: {n}", { n: item.not_opened })}` : ""}</span>
          </>
        ) : (
          <>
            <span className="dash-what">{L("Call sheet is not published")}</span>
            <span className="dash-detail">{L("Day {n}", { n: item.day_number })}</span>
          </>
        )}
      </a>
    </li>
  );
}

/** The first thing after signing in: what needs this person now, across all their films, soonest first. */
export function DashboardPanel({ conn }: { conn: Connection }) {
  const { lang, L } = useContext(LangContext);
  const [board, setBoard] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.dashboard(conn).then((b) => { if (!cancelled) setBoard(b); }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [conn]);

  // The list of films below still works, so a failed summary must not take the screen with it.
  if (failed) return <p className="hint" id="dashboardFailed">{L("Could not load the overview. Your films are below.")}</p>;
  if (!board) return <StillBackground />;

  const count = board.items.length;
  return (
    <section className="dash" id="dashboard" aria-label={L("What needs you now")}>
      <StillBackground />
      {count > 0 ? (
        <>
          <p className="dash-count" id="dashCount">{count}</p>
          <h2>{L(byCount(count, "thing is waiting on you", "things are waiting on you", "things wait on you"))}</h2>
          <ul className="dash-items" id="dashItems">{board.items.map((i) => <Item key={`${i.kind}-${i.call_sheet_id}`} item={i} L={L} />)}</ul>
        </>
      ) : (
        <h2 className="dash-clear" id="dashClear">{L("Everything is on track")}</h2>
      )}
      {board.on_track.length > 0 && (
        <>
          <p className="dash-label">{L("On track")}</p>
          <ul className="dash-ontrack" id="dashOnTrack">
            {board.on_track.map((p) => (
              <li key={p.production_id}>
                <a href={href({ screen: "production", productionId: p.production_id, tab: "days" })}>
                  <b>{p.production_name}</b>
                  <span>{p.next_shoot_date ? `${fmtDate(lang, p.next_shoot_date)}${p.crew_call ? ` · ${p.crew_call}` : ""}` : L("No days ahead")}</span>
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
