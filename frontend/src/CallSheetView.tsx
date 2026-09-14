import type { CallSheet, ScheduleItem } from "./types";

function pages(eighths: number): string {
  return `${Math.floor(eighths / 8)} ${eighths % 8}/8`.trim();
}

function ScheduleRow({ item }: { item: ScheduleItem }) {
  // React escapes text by construction; never dangerouslySetInnerHTML here.
  return (
    <tr>
      <td>{item.order_index}</td>
      <td>{item.scene_number}</td>
      <td>{item.int_ext}</td>
      <td>{item.day_night}</td>
      <td>{item.set_description}</td>
      <td>{pages(item.page_count_eighths)}</td>
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
  return (
    <div id="sheet" className="sheet visible">
      <div className="sheet-header">
        <div>
          <div className="day" id="dayLabel">
            Day {callSheet.day_number} of {callSheet.day_count} — {callSheet.unit_name}
          </div>
          <div className="sub" id="dateLabel">{callSheet.shoot_date}</div>
        </div>
        <div id="revBadgeWrap">
          {rev && <span className="rev-badge">REV {rev.revision_letter}</span>}
        </div>
      </div>

      <div className="info-grid">
        <Info label="Crew call" id="crewCall" value={rev?.general_crew_call} />
        <Info label="Shooting call" id="shootingCall" value={rev?.shooting_call} />
        <Info label="Sunrise" id="sunrise" value={rev?.sunrise} />
        <Info label="Sunset" id="sunset" value={rev?.sunset} />
        <Info label="Weather" id="weather" value={rev?.weather_forecast} />
      </div>

      {rev?.safety_notes && (
        <div className="safety" id="safetyBox">
          <div className="label">Safety notes</div>
          <div id="safetyText">{rev.safety_notes}</div>
        </div>
      )}

      <table>
        <thead>
          <tr><th>#</th><th>Scene</th><th>Int/Ext</th><th>Day/Night</th><th>Set</th><th>Pages</th></tr>
        </thead>
        <tbody id="scheduleBody">
          {items.map((item) => <ScheduleRow key={item.id ?? item.order_index} item={item} />)}
        </tbody>
      </table>

      <div className="cached-at" id="cachedAt">
        {freshness.fromCache
          ? `Showing cached copy from ${new Date(freshness.fetchedAt).toLocaleString()} — offline.`
          : "Live, fetched just now."}
      </div>

      <div className="actions">
        <button onClick={() => window.print()}>Print</button>
      </div>
    </div>
  );
}

function Info({ label, id, value }: { label: string; id: string; value?: string | null }) {
  return (
    <div className="info-box">
      <div className="label">{label}</div>
      <div className="value" id={id}>{value || "—"}</div>
    </div>
  );
}
