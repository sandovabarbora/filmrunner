import type { CallSheet, ScheduleItem } from "./types";

function pages(eighths: number): string {
  const whole = Math.floor(eighths / 8);
  const rest = eighths % 8;
  if (rest === 0) return `${whole}`;
  return whole ? `${whole} ${rest}/8` : `${rest}/8`;
}

function ScheduleRow({ item }: { item: ScheduleItem }) {
  // React escapes text by construction; never dangerouslySetInnerHTML here.
  return (
    <tr>
      <td className="n">{item.order_index}</td>
      <td className="scene">{item.scene_number}</td>
      <td className="ie">{item.int_ext}</td>
      <td className="dn">{item.day_night}</td>
      <td className="set">{item.set_description}</td>
      <td className="pages">{pages(item.page_count_eighths)}</td>
    </tr>
  );
}

export interface CallSheetViewProps {
  callSheet: CallSheet;
  freshness: { fromCache: false } | { fromCache: true; fetchedAt: string };
}

export function CallSheetView({ callSheet, freshness }: CallSheetViewProps) {
  const rev = callSheet.current_revision;
  const items = [...(rev?.schedule_items ?? [])].sort((a, b) => a.order_index - b.order_index);
  const title = callSheet.production_title ?? callSheet.unit_name;
  return (
    <article id="sheet" className="sheet visible" aria-label="Call sheet">
      <header className="sheet-header">
        <div>
          <h2 className="production">{title}</h2>
          <p className="day" id="dayLabel">
            Day {callSheet.day_number} of {callSheet.day_count} — {callSheet.unit_name}
            {" "}<span className="date" id="dateLabel">· {callSheet.shoot_date}</span>
          </p>
        </div>
        <div id="revBadgeWrap">
          {rev && <span className="rev-badge" data-rev={rev.revision_letter}>REV {rev.revision_letter}</span>}
        </div>
      </header>

      <section className="calls" aria-label="Call times">
        <div className="call crew">
          <div className="label">Crew call</div>
          <div className="value" id="crewCall">{rev?.general_crew_call || "—"}</div>
        </div>
        <div className="call shoot">
          <div className="label">Shooting call</div>
          <div className="value" id="shootingCall">{rev?.shooting_call || "—"}</div>
        </div>
      </section>

      <section className="meta" aria-label="Light and weather">
        <span><span className="k">Sunrise </span><span className="v" id="sunrise">{rev?.sunrise || "—"}</span></span>
        <span><span className="k">Sunset </span><span className="v" id="sunset">{rev?.sunset || "—"}</span></span>
        <span className="weather"><span className="k">Weather </span><span id="weather">{rev?.weather_forecast || "—"}</span></span>
      </section>

      {rev?.safety_notes && (
        <section className="safety" id="safetyBox" aria-label="Safety notes">
          <div className="label">Safety</div>
          <p id="safetyText">{rev.safety_notes}</p>
        </section>
      )}

      <section className="schedule" aria-label="Shooting schedule">
        <h2>Schedule</h2>
        <table>
          <thead>
            <tr><th>#</th><th>Scene</th><th>I/E</th><th>D/N</th><th>Set</th><th>Pages</th></tr>
          </thead>
          <tbody id="scheduleBody">
            {items.map((item) => <ScheduleRow key={item.id ?? item.order_index} item={item} />)}
          </tbody>
        </table>
      </section>

      {freshness.fromCache && (
        <p className="cached-at" id="cachedAt">
          Copy saved {new Date(freshness.fetchedAt).toLocaleString()}. You are offline; times may have changed since.
        </p>
      )}

      <div className="actions">
        <button onClick={() => window.print()}>Print</button>
        <span className="hint">Add to home screen to open it with no signal.</span>
      </div>
    </article>
  );
}
