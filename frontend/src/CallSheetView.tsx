import { lazy, Suspense, useState, type ReactNode } from "react";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { whatsappNumber, whatsappUrl } from "./editor/shareText";
import type { CallSheet, ContactCard, PersonalSheet, RevisionChange, ScheduleItem, SheetLocation } from "./types";
import { fmtDate, t, type Key, type Lang } from "./i18n";

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

/** Values people compare at a glance (times, scene numbers) are set in the data face; prose is not. */
const DATA_FIELDS = new Set(["crew_call", "shooting_call", "scenes_added", "scenes_removed", "scene_order", "sunrise", "sunset"]);

/** True changes, but nobody re-plans their morning around them, and the new values are right below on the sheet: named, not spelled out. */
const MINOR_FIELDS = new Set(["weather", "sunrise", "sunset", "head_of_day"]);

/** On a personal link these stay open: they change when, where or how safely this person works. Everything else waits behind one tap. */
const FIRST_ON_PERSONAL = new Set(["shoot_date", "shooting_call", "location", "safety_notes", "scene_moved_out", "scene_moved_in"]);

/** A bare "Scenes removed / 43" says nothing to someone half awake; these read as a sentence. */
function changeSentence(c: RevisionChange, lang: Lang): string | null {
  const after = c.after ?? "";
  const several = after.includes(",") ? "many" : "one";
  if (c.field === "scenes_removed" || c.field === "scenes_added") return t(lang, `change.${c.field}.${several}` as Key, { n: after });
  if (c.field === "cast_calls") return t(lang, "change.cast_calls.sentence", { names: after });
  return null;
}

function ChangeRow({ c, lang, dayHref }: { c: RevisionChange; lang: Lang; dayHref?: (id: string) => string }) {
  if (c.field === "shoot_date") {
    return (
      <li data-field={c.field}>
        <span className="k">{t(lang, "change.shoot_date")}</span>
        <span className="v">{c.before && <><s>{fmtDate(lang, c.before)}</s><span className="to" aria-hidden="true"> → </span></>}<b>{fmtDate(lang, c.after ?? "")}</b></span>
      </li>
    );
  }
  if ((c.field === "scene_moved_out" || c.field === "scene_moved_in") && c.other_call_sheet_id && c.other_date) {
    const where = `${t(lang, "day.n", { n: c.other_day_number ?? "" })} · ${fmtDate(lang, c.other_date)}`;
    return (
      <li data-field={c.field}>
        <span className="k">{t(lang, `change.${c.field}` as Key)}</span>
        <span className="v"><b>{t(lang, "change.moved", { n: (c.scenes ?? []).join(", ") })} {dayHref ? <a href={dayHref(c.other_call_sheet_id)}>{where}</a> : where}</b></span>
      </li>
    );
  }
  const sentence = changeSentence(c, lang);
  if (sentence) return <li data-field={c.field}><span className="v"><b>{sentence}</b></span></li>;
  // The server's `label` and "N changed" are English (they also feed the push); the sheet renders from `field` and falls back to them.
  const key = `change.${c.field}` as Key;
  const known = t(lang, key) !== key;
  const named = c.field === "location" || c.field === "scene_detail";
  const scenes = c.scenes ?? [];
  const label = !known ? c.label : c.field === "location" ? `${t(lang, key)} · ${t(lang, "where.sc")} ${scenes.join(", ")}` : named ? `${t(lang, key)} ${scenes.join(", ")}` : t(lang, key);
  const count = c.field === "personal_calls" ? /^(\d+)/.exec(c.after ?? "")?.[1] : undefined;
  const after = count ? t(lang, "change.personalCount", { n: count }) : c.after ?? "—";
  // A long note struck through above its replacement is unreadable at 5 am; the old text stays in the AD's history.
  const showBefore = c.before !== null && c.field !== "safety_notes";
  return (
    <li data-field={c.field} className={DATA_FIELDS.has(c.field) ? "data" : undefined}>
      <span className="k">{label}</span>
      <span className="v">{showBefore && <><s>{c.before}</s><span className="to" aria-hidden="true"> → </span></>}<b>{after}</b></span>
    </li>
  );
}

/** The changes, most urgent first. Someone who has already confirmed came for a time, not for this list, so it folds away for them. */
function RevChanges({ first, rest, foldAll, lang, dayHref }: { first: RevisionChange[]; rest: RevisionChange[]; foldAll: boolean; lang: Lang; dayHref?: (id: string) => string }) {
  const shown = foldAll ? [] : first;
  const folded = foldAll ? [...first, ...rest] : rest;
  const [open, setOpen] = useState(shown.length === 0 && !foldAll);
  const row = (c: RevisionChange, i: number) => <ChangeRow key={`${c.field}-${i}`} c={c} lang={lang} dayHref={dayHref} />;
  const minor = folded.filter((c) => MINOR_FIELDS.has(c.field));
  const shownMinor = shown.filter((c) => MINOR_FIELDS.has(c.field));
  const also = (list: RevisionChange[]) => list.length > 0 && <li className="also" data-field="also">{t(lang, "rev.also", { list: list.map((c) => t(lang, `change.${c.field}` as Key).toLowerCase()).join(", ") })}</li>;
  return (
    <>
      {shown.length > 0 && (
        <ul className="rev-changes" id="revChanges">
          {shown.filter((c) => !MINOR_FIELDS.has(c.field)).map(row)}
          {also(shownMinor)}
        </ul>
      )}
      {folded.length > 0 && (
        <>
          <button type="button" className="rev-toggle" id="revMoreToggle" aria-expanded={open} aria-controls="revMore" onClick={() => setOpen(!open)}>
            <Icon name={open ? "up" : "down"} />{t(lang, foldAll ? "rev.allChanges" : "rev.more", { n: folded.length })}
          </button>
          <ul className="rev-changes" id="revMore" hidden={!open}>
            {folded.filter((c) => !MINOR_FIELDS.has(c.field)).map(row)}
            {also(minor)}
          </ul>
        </>
      )}
    </>
  );
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

/** A generated mood frame, never a claim about the real location: night for a night start, otherwise the stage. */
export function StillBackground({ name = "hall" }: { name?: "hall" | "night" }) {
  return <div className="hero-bg" aria-hidden="true"><img src={`${import.meta.env.BASE_URL}stills/${name}.webp`} alt="" /></div>;
}

export interface CallSheetViewProps {
  callSheet: CallSheet;
  personal?: PersonalSheet | null;
  freshness: { fromCache: false } | { fromCache: true; fetchedAt: string };
  /** FR-47: the crew link this sheet was opened from, printed with a QR code in the footer so paper leads back to it. */
  shareUrl?: string | null;
  /** FR-48: labels in the crew member's language; user-entered text is never translated. */
  lang?: Lang;
  /** FR-202: the confirm action; it follows the change it confirms, and only a personal link has one. */
  confirm?: ReactNode;
  /** FR-203: the link to another day of this shoot, for a scene moved to or from it. */
  dayHref?: (callSheetId: string) => string;
}

export function CallSheetView({ callSheet, personal = null, freshness, shareUrl = null, lang = "en", confirm = null, dayHref }: CallSheetViewProps) {
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
  // On a personal link the person's own call block answers "did mine move"; a count of other people's says nothing.
  // FR-204: someone who skipped revisions is shown everything since what they last read, not only the newest step.
  // The block and the sheet refresh separately, so catching up only applies to the revision on screen.
  const catchingUp = personal?.changes_since && personal.revision_letter === rev?.revision_letter ? personal : null;
  const allChanges = catchingUp?.changes_since ?? callSheet.changes ?? [];
  const changes = allChanges.filter((c) => !personal || c.field !== "personal_calls");
  const notAboutYou = !!personal && changes.length === 0 && allChanges.length > 0 && !personal.call_before && !personal.pickup_before && !personal.note_changed;
  // The block and the sheet load separately, and the block can come from this phone's copy while the sheet is live. A call time from an
  // older revision under a newer sheet is the one thing this page must never show as if it were current.
  const personalBehind = !!personal?.revision_letter && !!rev && personal.revision_letter !== rev.revision_letter;
  const alreadyConfirmed = !!personal?.confirmed_at && personal.revision_letter === rev?.revision_letter;
  // Where this person is going first: the first scene with a location. The sheet lists the others below.
  const firstScene = items.find((i) => i.location_id && locationNames.has(i.location_id));
  const firstPlace = sheetLocations.find((l) => l.id === firstScene?.location_id) ?? null;
  const placeChange = changes.find((c) => c.field === "location" && firstScene && (c.scenes ?? []).includes(firstScene.scene_number));
  const firstPlaceBefore = placeChange?.before ?? null;
  const firstPlaceUrl = firstPlace ? mapsUrl(firstPlace) : null;
  // On the shared link nothing competes with the list, so nothing folds. A personal link has already said this person's own time and place.
  const showsPlace = !!personal && !!firstPlace && !(personal.is_cast && !personal.works_today);
  const leads = (c: RevisionChange) => FIRST_ON_PERSONAL.has(c.field) && !(showsPlace && c === placeChange);
  const first = personal ? changes.filter(leads) : changes;
  const rest = personal ? changes.filter((c) => !leads(c)) : [];
  const otherPlaces = sheetLocations.length - 1;
  return (
    <article id="sheet" className="sheet visible" aria-label="Call sheet" data-rev={rev?.revision_letter}>
      <div className="hero">
        <StillBackground name={items[0]?.day_night === "NIGHT" ? "night" : "hall"} />
        {personal ? (
          <section className="you" id="you" aria-label={L("you.call")}>
            {/* An actor's day starts at their own pickup; the crew call is never their time, and someone not called has none. */}
            {personalBehind
              ? <p className="you-off" id="yourCallBehind" role="status">{L("you.behind", { rev: rev!.revision_letter })}</p>
              : personal.is_cast && !personal.works_today
              ? <p className="you-off" id="yourCallOff">{L("you.notToday")}</p>
              : <div className="value hero-time" id="yourCall">{personal.personal_call || (personal.is_cast ? personal.pickup_time : rev?.general_crew_call) || "—"}</div>}
            <div className="hero-sub">
              <div className="you-call">
                <span className="label">{L("you.call")}</span>
                {!personalBehind && personal.call_before && <span className="was" id="yourCallWas">{" · "}<span className="k">{L("you.was")}</span> <s>{personal.call_before}</s></span>}
                {!personalBehind && personal.note && <span className="note">{" · "}{personal.note}</span>}
              </div>
              <div id="revBadgeWrap">{rev && <span className="rev-badge" data-rev={rev.revision_letter}>REV {rev.revision_letter}</span>}</div>
            </div>
            <div className="who"><span className="name">{personal.name}</span><span className="role">{" · "}{personal.is_cast ? personal.position : `${personal.department} · ${personal.position}`}</span></div>
            {!personalBehind && (personal.pickup_time || personal.makeup_hair_time || personal.on_set_time) && (
              <div className="you-extra" id="yourExtra">
                {personal.pickup_time && <span><span className="k">{L("you.pickup")} </span><span className="v">{personal.pickup_time}</span>{personal.pickup_before && <> <s className="v">{personal.pickup_before}</s></>}</span>}
                {personal.makeup_hair_time && <span><span className="k">{L("th.mh")} </span><span className="v">{personal.makeup_hair_time}</span></span>}
                {personal.on_set_time && <span><span className="k">{L("th.onSet")} </span><span className="v">{personal.on_set_time}</span></span>}
              </div>
            )}
          </section>
        ) : (
          <section className="you shared" aria-label={L("crewCall")}>
            <div className="value hero-time" id="crewCall">{rev?.general_crew_call || "—"}</div>
            <div className="hero-sub">
              <div className="you-call"><span className="label">{L("crewCall")}</span></div>
              <div id="revBadgeWrap">{rev && <span className="rev-badge" data-rev={rev.revision_letter}>REV {rev.revision_letter}</span>}</div>
            </div>
          </section>
        )}

        <div className="frame" aria-hidden="true"><i /><i /><i /><i /></div>

        <div className="hero-foot">
          <header className="sheet-header">
            <h2 className="production">{title}</h2>
            <p className="day" id="dayLabel">
              {L("day.of", { n: callSheet.day_number, count: callSheet.day_count })} · {callSheet.unit_name}
              {" "}<span className="date" id="dateLabel">{fmtDate(lang, callSheet.shoot_date)}</span>
            </p>
          </header>

          {callSheet.status === "cancelled" && (
            <div className="cancelled" id="cancelledBanner" role="alert">
              <strong>{L("cancelled")}</strong> — {L("cancelled.text", { n: callSheet.day_number, date: fmtDate(lang, callSheet.shoot_date) })}
            </div>
          )}

          {showsPlace && firstPlace && (
            <div className="you-where" id="yourPlace">
              <div className="place">{firstPlace.name}</div>
              {firstPlaceBefore && <div className="was" id="yourPlaceWas">{L("you.was")} <s>{firstPlaceBefore}</s></div>}
              {firstPlace.address && (firstPlaceUrl ? <a className="address-link" href={firstPlaceUrl} target="_blank" rel="noreferrer">{firstPlace.address}</a> : <div>{firstPlace.address}</div>)}
              {otherPlaces > 0 && <div className="more-places">{L("you.morePlaces", { n: otherPlaces })}</div>}
            </div>
          )}

          {rev && rev.revision_letter !== "A" && (
            <section className="rev-block" id="revReplaces" aria-label={L("rev.changes")}>
              <p className="rev-line">
                {L("rev.replaces", { rev: rev.revision_letter, prev: callSheet.previous_revision?.revision_letter ?? String.fromCharCode(rev.revision_letter.charCodeAt(0) - 1) })}
                {rev.created_at && L("rev.issued", { time: issuedAt(rev.created_at) })}
              </p>
              {catchingUp?.since_letter && <p className="rev-since" id="revSince">{L("rev.since", { rev: catchingUp.since_letter })}</p>}
              {changes.length === 0 && allChanges.length === 0 && <p className="rev-same" id="revSame">{L("rev.same")}</p>}
              {notAboutYou && <p className="rev-same" id="revNotYou">{L("rev.notYou")}</p>}
              {changes.length > 0 && <RevChanges key={rev.revision_letter} first={first} rest={rest} foldAll={alreadyConfirmed} lang={lang} dayHref={dayHref} />}
            </section>
          )}
        </div>
      </div>

      {confirm}

      <section className="calls" aria-label="Call times">
        {personal && (
          <div className="call crew">
            <div className="label">{L("crewCall")}</div>
            <div className="value" id="crewCall">{rev?.general_crew_call || "—"}</div>
          </div>
        )}
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
                  <td className="set">{r.name}</td><td className="character">{r.character_name}</td><td className="ie">{r.status_code}</td>
                  <td className="time" data-k={L("you.pickup")}>{r.pickup_time ?? ""}</td><td className="time" data-k={L("th.call")}>{r.call_time ?? ""}</td><td className="time" data-k={L("th.mh")}>{r.makeup_hair_time ?? ""}</td><td className="time" data-k={L("th.onSet")}>{r.on_set_time ?? ""}</td>
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
          {L("cached.note", { time: new Date(freshness.fetchedAt).toLocaleString() })}
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
        <button onClick={() => window.print()}><Icon name="print" />{L("print")}</button>
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
            <Icon name="phone" />{c.phone}
          </a>
          {wa && (
            <a
              className="contact-btn wa"
              href={whatsappUrl(wa, "")}
              target="_blank"
              rel="noreferrer"
              aria-label={`WhatsApp ${c.name}`}
            >
              <Icon name="chat" />{t(lang, "contacts.whatsapp")}
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
 * FR-82: the icon is an aria-hidden SVG, never a text node — a glyph character inside the button's own
 * visible text can never be reflected in `aria-label`, which is what caused axe's label-content-name-mismatch
 * here in the first place. On a phone the word is hidden and the icon alone carries it (see styles.css).
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
      <Icon name={copied ? "check" : "copy"} /><span className="btn-label">{copied ? t(lang, "contacts.copied") : t(lang, "contacts.copy")}</span>
    </button>
  );
}
