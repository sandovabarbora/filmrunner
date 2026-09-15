import type { CallSheet, ContactCard, PersonalSheet, ScheduleItem } from "./types";

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
  personal?: PersonalSheet | null;
  freshness: { fromCache: false } | { fromCache: true; fetchedAt: string };
}

export function CallSheetView({ callSheet, personal = null, freshness }: CallSheetViewProps) {
  const rev = callSheet.current_revision;
  const myDept = personal?.department ?? null;
  const heads = callSheet.contacts?.department_heads ?? [];
  const mine = myDept ? heads.filter((c) => c.department === myDept) : [];
  const others = myDept ? heads.filter((c) => c.department !== myDept) : heads;
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

      {personal && (
        <section className="you" id="you" aria-label="Your call">
          <div className="you-head">
            <div className="label">Your call</div>
            <div className="who"><span className="name">{personal.name}</span><span className="role">{personal.department} · {personal.position}</span></div>
          </div>
          <div className="value" id="yourCall">{personal.personal_call || rev?.general_crew_call || "—"}</div>
        </section>
      )}

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

      {callSheet.contacts && (callSheet.contacts.head_of_day || callSheet.contacts.department_heads.length > 0 || callSheet.contacts.nearest_hospital) && (
        <section className="contacts" id="contacts" aria-label="Who to call">
          <h2>Who to call</h2>
          {callSheet.contacts.head_of_day && (
            <div className="hod">
              <div className="label">Head of day</div>
              <ContactRow c={callSheet.contacts.head_of_day} />
            </div>
          )}
          {mine.length > 0 && (
            <div className="hod mine" id="yourDepartment">
              <div className="label">Your department · {myDept}</div>
              {mine.map((c) => <ContactRow key={`${c.department}-${c.name}`} c={c} />)}
            </div>
          )}
          {others.length > 0 && (myDept ? (
            <details className="others" id="otherDepartments">
              <summary>Other departments ({others.length})</summary>
              <ul className="contact-list">
                {others.map((c) => <li key={`${c.department}-${c.name}`}><ContactRow c={c} /></li>)}
              </ul>
            </details>
          ) : (
            <ul className="contact-list">
              {others.map((c) => <li key={`${c.department}-${c.name}`}><ContactRow c={c} /></li>)}
            </ul>
          ))}
          {callSheet.contacts.nearest_hospital && (
            <p className="hospital"><span className="k">Nearest hospital </span>{callSheet.contacts.nearest_hospital}</p>
          )}
        </section>
      )}

      {freshness.fromCache && (
        <p className="cached-at" id="cachedAt">
          Copy saved {new Date(freshness.fetchedAt).toLocaleString()}. You are offline; times may have changed since.
        </p>
      )}

      <p className="print-foot" id="printFoot">
        {title} · Day {callSheet.day_number} of {callSheet.day_count} · {callSheet.shoot_date}
        {rev ? ` · REV ${rev.revision_letter}` : ""}
        {rev?.created_at ? ` · issued ${new Date(rev.created_at).toLocaleString()}` : ""}
        {" · FilmRunner"}
      </p>

      <div className="actions">
        <button onClick={() => window.print()}>Print / Save PDF</button>
        <span className="hint">Add to home screen to open it with no signal. On iPhone: Share → Print → pinch out for PDF.</span>
      </div>
    </article>
  );
}

function ContactRow({ c }: { c: ContactCard }) {
  const tel = c.phone ? `tel:${c.phone.replace(/[^+\d]/g, "")}` : null;
  return (
    <div className="contact">
      <div className="who">
        <span className="name">{c.name}</span>
        <span className="role">{c.department} · {c.position}</span>
      </div>
      {tel ? <a className="phone" href={tel}>{c.phone}</a> : <span className="phone none">no number on file</span>}
    </div>
  );
}
