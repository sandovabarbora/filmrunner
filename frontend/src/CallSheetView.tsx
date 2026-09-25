import { lazy, Suspense, useState } from "react";
import { Avatar } from "./Avatar";
import { whatsappNumber, whatsappUrl } from "./editor/shareText";
import type { CallSheet, ContactCard, PersonalSheet, ScheduleItem, SheetLocation } from "./types";
import { fmtDate, t, type Lang } from "./i18n";

// FR-84: qrcode-generator (~52 KB minified) is only needed for the print-only
// footer, never for the on-screen sheet crew actually read. Code-split so it
// loads on its own instead of shipping in the shared chunk every sheet view preloads.
const QrCode = lazy(() => import("./editor/screens/QrCode").then((m) => ({ default: m.QrCode })));

/** "06:12" in the phone's own time zone; the raw value if it does not parse. */
function issuedAt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function pages(eighths: number): string {
  const whole = Math.floor(eighths / 8);
  const rest = eighths % 8;
  if (rest === 0) return `${whole}`;
  return whole ? `${whole} ${rest}/8` : `${rest}/8`;
}

/** Apple Maps on iPhone opens this too; coordinates beat the address when the geocoder resolved them. */
function mapsUrl(loc: SheetLocation): string | null {
  if (loc.geo_lat !== null && loc.geo_lng !== null) return `https://maps.google.com/?q=${loc.geo_lat},${loc.geo_lng}`;
  if (loc.address) return `https://maps.google.com/?q=${encodeURIComponent(loc.address)}`;
  return null;
}

function ScheduleRow({ item, locationName }: { item: ScheduleItem; locationName?: string }) {
  // React escapes text by construction; never dangerouslySetInnerHTML here.
  return (
    <tr>
      <td className="n">{item.order_index}</td>
      <td className="scene">{item.scene_number}</td>
      <td className="ie">{item.int_ext}</td>
      <td className="dn">{item.day_night}</td>
      <td className="set">{item.set_description}{locationName && <span className="loc"> · {locationName}</span>}</td>
      <td className="pages">{pages(item.page_count_eighths)}</td>
    </tr>
  );
}

export interface CallSheetViewProps {
  callSheet: CallSheet;
  personal?: PersonalSheet | null;
  freshness: { fromCache: false } | { fromCache: true; fetchedAt: string };
  /** FR-47: the crew link this sheet was opened from, printed with a QR code in the footer so paper leads back to it. */
  shareUrl?: string | null;
  /** FR-48: labels in the crew member's language; user-entered text is never translated. */
  lang?: Lang;
}

export function CallSheetView({ callSheet, personal = null, freshness, shareUrl = null, lang = "en" }: CallSheetViewProps) {
  const L = (key: Parameters<typeof t>[1], vars?: Record<string, string | number>) => t(lang, key, vars);
  const rev = callSheet.current_revision;
  const myDept = personal?.department ?? null;
  const heads = callSheet.contacts?.department_heads ?? [];
  const sheetLocations = callSheet.locations ?? [];
  const locationNames = new Map(sheetLocations.map((l) => [l.id, l.name]));
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
            {L("day.of", { n: callSheet.day_number, count: callSheet.day_count })} — {callSheet.unit_name}
            {" "}<span className="date" id="dateLabel">· {fmtDate(lang, callSheet.shoot_date)}</span>
          </p>
        </div>
        <div id="revBadgeWrap">
          {rev && <span className="rev-badge" data-rev={rev.revision_letter}>REV {rev.revision_letter}</span>}
        </div>
      </header>

      {callSheet.status === "cancelled" && (
        <div className="cancelled" id="cancelledBanner" role="alert">
          <strong>{L("cancelled")}</strong> — {L("cancelled.text", { n: callSheet.day_number, date: fmtDate(lang, callSheet.shoot_date) })}
        </div>
      )}

      {rev && rev.revision_letter !== "A" && (
        <div className="rev-replaces" id="revReplaces">
          <p>
            {L("rev.replaces", { rev: rev.revision_letter, prev: callSheet.previous_revision?.revision_letter ?? String.fromCharCode(rev.revision_letter.charCodeAt(0) - 1) })}
            {rev.created_at && L("rev.issued", { time: issuedAt(rev.created_at) })}
          </p>
          {(callSheet.changes ?? []).length > 0 && (
            <ul className="rev-changes" id="revChanges" aria-label={L("rev.changes")}>
              {callSheet.changes!.map((c) => {
                // The server's `label` and the "N changed" summary are English (they also feed the push text);
                // the sheet renders them from the stable `field` key instead, falling back to what came in.
                const key = `change.${c.field}` as Parameters<typeof t>[1];
                const label = t(lang, key) === key ? c.label : L(key);
                const count = c.field === "personal_calls" ? /^(\d+)/.exec(c.after ?? "")?.[1] : undefined;
                const after = count ? L("change.personalCount", { n: count }) : c.after ?? "—";
                return (
                  <li key={c.field} data-field={c.field}>
                    <span className="k">{label}</span>{" "}
                    {c.before !== null ? <><s>{c.before}</s> → <b>{after}</b></> : <b>{after}</b>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {personal && (
        <section className="you" id="you" aria-label={L("you.call")}>
          <div className="you-head">
            <div className="label">{L("you.call")}</div>
            <div className="who"><span className="name">{personal.name}</span><span className="role">{personal.department} · {personal.position}</span></div>
          </div>
          <div className="value" id="yourCall">{personal.personal_call || rev?.general_crew_call || "—"}</div>
          {(personal.pickup_time || personal.note) && (
            <div className="you-extra" id="yourExtra">
              {personal.pickup_time && <span><span className="k">{L("you.pickup")} </span><span className="v">{personal.pickup_time}</span></span>}
              {personal.note && <span className="note">{personal.note}</span>}
            </div>
          )}
        </section>
      )}

      <section className="calls" aria-label="Call times">
        <div className="call crew">
          <div className="label">{L("crewCall")}</div>
          <div className="value" id="crewCall">{rev?.general_crew_call || "—"}</div>
        </div>
        <div className="call shoot">
          <div className="label">{L("shootingCall")}</div>
          <div className="value" id="shootingCall">{rev?.shooting_call || "—"}</div>
        </div>
      </section>

      <section className="meta" aria-label="Light and weather">
        <span><span className="k">{L("sunrise")} </span><span className="v" id="sunrise">{rev?.sunrise || "—"}</span></span>
        <span><span className="k">{L("sunset")} </span><span className="v" id="sunset">{rev?.sunset || "—"}</span></span>
        <span className="weather"><span className="k">{L("weather")} </span><span id="weather">{rev?.weather_forecast || "—"}</span></span>
      </section>

      {rev?.safety_notes && (
        <section className="safety" id="safetyBox" aria-label={L("safety")}>
          <div className="label">{L("safety")}</div>
          <p id="safetyText">{rev.safety_notes}</p>
        </section>
      )}

      {sheetLocations.length > 0 && (
        <section className="locations" id="locations" aria-label={L("where")}>
          <h2>{L("where")}</h2>
          {sheetLocations.map((loc) => {
            const url = mapsUrl(loc);
            return (
              <div className="location" key={loc.id} data-location={loc.id}>
                <div className="location-head">
                  <span className="name">{loc.name}</span>
                  {loc.scene_numbers.length > 0 && <span className="scenes">{L("where.sc")} {loc.scene_numbers.join(", ")}</span>}
                </div>
                {loc.address && <div className="address">{url ? <a href={url} target="_blank" rel="noreferrer">{loc.address}</a> : loc.address}</div>}
                {!loc.address && url && <div className="address"><a href={url} target="_blank" rel="noreferrer">{L("where.maps")}</a></div>}
                {loc.parking_notes && <div className="line"><span className="k">{L("where.parking")} </span>{loc.parking_notes}</div>}
                {loc.nearest_hospital && <div className="line"><span className="k">{L("where.hospital")} </span>{loc.nearest_hospital}</div>}
              </div>
            );
          })}
        </section>
      )}

      <section className="schedule" aria-label="Shooting schedule">
        <h2>{L("schedule")}</h2>
        <table>
          <thead>
            <tr><th>#</th><th>{L("th.scene")}</th><th>{L("th.ie")}</th><th>{L("th.dn")}</th><th>{L("th.set")}</th><th>{L("th.pages")}</th></tr>
          </thead>
          <tbody id="scheduleBody">
            {items.map((item) => <ScheduleRow key={item.id ?? item.order_index} item={item} locationName={locationNames.get(item.location_id ?? "")} />)}
          </tbody>
        </table>
      </section>

      {(callSheet.cast_calls?.length ?? 0) > 0 && (
        <section className="schedule cast" id="castTable" aria-label="Cast">
          <h2>{L("cast")}</h2>
          <table>
            <thead><tr><th>{L("cast")}</th><th>{L("th.character")}</th><th>{L("th.status")}</th><th>{L("th.pickup")}</th><th>{L("th.call")}</th><th>{L("th.mh")}</th><th>{L("th.onSet")}</th></tr></thead>
            <tbody>
              {callSheet.cast_calls!.map((r) => (
                <tr key={r.cast_member_id} data-cast={r.cast_member_id}>
                  <td className="set">{r.name}</td><td>{r.character_name}</td><td className="ie">{r.status_code}</td>
                  <td className="scene">{r.pickup_time ?? ""}</td><td className="scene">{r.call_time ?? ""}</td><td className="scene">{r.makeup_hair_time ?? ""}</td><td className="scene">{r.on_set_time ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {(callSheet.personal_calls?.length ?? 0) > 0 && (
        <section className="pcalls print-only" id="personalCallsTable" aria-label={L("personalCalls")}>
          <h2>{L("personalCalls")}</h2>
          <table>
            <thead><tr><th>{L("th.name")}</th><th>{L("th.department")}</th><th>{L("th.call")}</th><th>{L("th.pickup")}</th><th>{L("th.note")}</th></tr></thead>
            <tbody>
              {callSheet.personal_calls!.map((r) => (
                <tr key={r.crew_member_id}><td>{r.name}</td><td>{r.department} · {r.position}</td><td className="scene">{r.call_time ?? ""}</td><td className="scene">{r.pickup_time ?? ""}</td><td>{r.note ?? ""}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {callSheet.contacts && (callSheet.contacts.head_of_day || callSheet.contacts.department_heads.length > 0 || callSheet.contacts.nearest_hospital) && (
        <section className="contacts" id="contacts" aria-label={L("contacts")}>
          <h2>{L("contacts")}</h2>
          {callSheet.contacts.head_of_day && (
            <div className="hod">
              <div className="label">{L("contacts.headOfDay")}</div>
              <ContactRow c={callSheet.contacts.head_of_day} lang={lang} />
            </div>
          )}
          {mine.length > 0 && (
            <div className="hod mine" id="yourDepartment">
              <div className="label">{L("contacts.yourDept")} · {myDept}</div>
              {mine.map((c) => <ContactRow key={`${c.department}-${c.name}`} c={c} lang={lang} />)}
            </div>
          )}
          {others.length > 0 && (myDept ? (
            <details className="others" id="otherDepartments">
              <summary>{L("contacts.others", { n: others.length })}</summary>
              <ul className="contact-list">
                {others.map((c) => <li key={`${c.department}-${c.name}`}><ContactRow c={c} lang={lang} /></li>)}
              </ul>
            </details>
          ) : (
            <ul className="contact-list">
              {others.map((c) => <li key={`${c.department}-${c.name}`}><ContactRow c={c} lang={lang} /></li>)}
            </ul>
          ))}
          {callSheet.contacts.nearest_hospital && (
            <p className="hospital"><span className="k">{L("contacts.hospital")} </span>{callSheet.contacts.nearest_hospital}</p>
          )}
        </section>
      )}

      {freshness.fromCache && (
        <p className="cached-at" id="cachedAt">
          Copy saved {new Date(freshness.fetchedAt).toLocaleString()}. You are offline; times may have changed since.
        </p>
      )}

      <p className="print-foot" id="printFoot">
        {title} · {L("day.of", { n: callSheet.day_number, count: callSheet.day_count })} · {fmtDate(lang, callSheet.shoot_date)}
        {rev ? ` · REV ${rev.revision_letter}` : ""}
        {rev?.created_at ? ` · ${L("footer.issued")} ${new Date(rev.created_at).toLocaleString()}` : ""}
        {" · FilmRunner"}
      </p>

      {shareUrl && (
        <div className="print-footer-bar" id="printFooterBar" aria-hidden="true">
          <Suspense fallback={null}>
            <QrCode value={shareUrl} size={64} />
          </Suspense>
          <span className="url">{shareUrl}</span>
        </div>
      )}

      <div className="actions">
        <button onClick={() => window.print()}>{L("print")}</button>
        <span className="hint">{L("print.hint")}</span>
      </div>
    </article>
  );
}

function ContactRow({ c, lang = "en" }: { c: ContactCard; lang?: Lang }) {
  const tel = c.phone ? `tel:${c.phone.replace(/[^+\d]/g, "")}` : null;
  const wa = whatsappNumber(c.phone);
  return (
    <div className="contact">
      <div className="who">
        <Avatar name={c.name} photoUrl={c.photo_url} />
        <div className="who-text">
          <span className="name">{c.name}</span>
          <span className="role">{c.department} · {c.position}</span>
        </div>
      </div>
      {tel ? (
        <div className="contact-actions">
          <a className="phone contact-btn" href={tel} aria-label={`${t(lang, "contacts.call")} ${c.name}, ${c.phone}`}>
            <span className="btn-icon" aria-hidden="true">☎</span>{c.phone}
          </a>
          {wa && (
            <a
              className="contact-btn wa"
              href={whatsappUrl(wa, "")}
              target="_blank"
              rel="noreferrer"
              aria-label={`WhatsApp ${c.name}`}
            >
              <span className="btn-icon" aria-hidden="true">💬</span>{t(lang, "contacts.whatsapp")}
            </a>
          )}
          <ContactCopyButton phone={c.phone!} name={c.name} lang={lang} />
        </div>
      ) : (
        <span className="phone none">{t(lang, "contacts.noNumber")}</span>
      )}
    </div>
  );
}

/**
 * A contact's number, copyable without selecting text with a wet thumb; a brief "Copied" confirms it worked.
 * FR-82: the ⧉ icon is a CSS `::before` (see `.contact-btn.copy`), never a text node — a glyph character
 * inside the button's own visible text can never be reflected in `aria-label`, which is what caused axe's
 * label-content-name-mismatch here in the first place.
 */
function ContactCopyButton({ phone, name, lang }: { phone: string; name: string; lang: Lang }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="contact-btn copy"
      onClick={() => {
        void navigator.clipboard?.writeText(phone);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      aria-label={`${t(lang, "contacts.copy")} ${name}`}
    >
      {copied ? t(lang, "contacts.copied") : t(lang, "contacts.copy")}
    </button>
  );
}
