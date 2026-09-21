/**
 * FR-29: the call sheet as a WhatsApp message.
 *
 * Prague crews run on WhatsApp groups, so the AD's real distribution step is
 * "paste it in the group" and "send each person their own link". These are
 * pure builders (no React, no network) so they can be unit-tested and reused
 * from any screen. WhatsApp renders *bold* and _italic_; nothing else.
 */

import type { Draft } from "./drafts";
import type { CastMember, CrewMember, Location } from "../types";

/** Day-level facts the text needs; a subset of Draft so callers can pass a published snapshot. */
export type DayFacts = Pick<
  Draft,
  "productionName" | "shoot_date" | "day_number" | "day_count" | "unit_name" | "general_crew_call" | "shooting_call" | "sunrise" | "sunset" | "weather_forecast" | "safety_notes" | "items" | "crewCalls" | "lastPublishedLetter"
> & Partial<Pick<Draft, "castCalls">>;

/** Cast lines for the group message: who works, status, and the times that exist, in call order. */
function castLines(day: DayFacts, cast: CastMember[]): string[] {
  const entries = Object.entries(day.castCalls ?? {});
  if (entries.length === 0 || cast.length === 0) return [];
  const rows = entries
    .map(([id, v]) => ({ actor: cast.find((a) => a.id === id), v }))
    .filter((r): r is { actor: CastMember; v: NonNullable<typeof r.v> } => !!r.actor)
    .sort((a, b) => (a.v.call || a.v.pickup || "99:99").localeCompare(b.v.call || b.v.pickup || "99:99"));
  return ["", "_Cast_", ...rows.map(({ actor, v }) => {
    const times = [v.pickup && `pickup ${v.pickup}`, v.call && `call ${v.call}`, v.makeup && `M/H ${v.makeup}`, v.onSet && `on set ${v.onSet}`].filter(Boolean).join(", ");
    return `${actor.contact.name} (${actor.character_name}) ${v.status}${times ? ` – ${times}` : ""}`;
  })];
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
// Fixed tables, not toLocaleDateString: ICU versions disagree ("Sep" vs "Sept") and the message must read the same on every phone.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Tue 23 Sep 2026" from an ISO date; the raw string when it does not parse, never a crash. */
export function humanDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  if (Number.isNaN(d.getTime())) return iso;
  return `${WEEKDAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function heading(day: DayFacts): string {
  const rev = day.lastPublishedLetter ? ` · REV ${day.lastPublishedLetter}` : "";
  const name = day.productionName ? `${day.productionName} · ` : "";
  return `*${name}Day ${day.day_number} of ${day.day_count}${rev}*\n${humanDate(day.shoot_date)}${day.unit_name ? ` · ${day.unit_name}` : ""}`;
}

function firstLocation(day: DayFacts, locations: Location[]): Location | null {
  const ordered = [...day.items].sort((a, b) => a.order_index - b.order_index);
  const id = ordered.find((it) => it.location_id)?.location_id ?? null;
  return id ? locations.find((l) => l.id === id) ?? null : null;
}

function locationLines(loc: Location | null): string[] {
  if (!loc) return [];
  const lines = [`Location: ${loc.name}${loc.address ? `, ${loc.address}` : ""}`];
  if (loc.parking_notes) lines.push(`Parking: ${loc.parking_notes}`);
  return lines;
}

/** The whole day for the crew group: calls, where, weather, the schedule, and the crew link last so it is tappable. */
export function daySummaryText(day: DayFacts, locations: Location[], crewLink: string, cast: CastMember[] = []): string {
  const lines: string[] = [heading(day), ""];
  if (day.general_crew_call) lines.push(`Crew call: *${day.general_crew_call}*`);
  if (day.shooting_call) lines.push(`Shooting call: ${day.shooting_call}`);
  lines.push(...locationLines(firstLocation(day, locations)));
  if (day.weather_forecast) lines.push(`Weather: ${day.weather_forecast}`);
  if (day.sunrise || day.sunset) lines.push(`Sun: ${day.sunrise || "?"} – ${day.sunset || "?"}`);
  const items = [...day.items].sort((a, b) => a.order_index - b.order_index);
  if (items.length > 0) {
    lines.push("", "_Schedule_");
    for (const it of items) {
      const tag = [it.int_ext, it.day_night].filter(Boolean).join("/");
      lines.push(`${it.order_index}. Sc ${it.scene_number}${tag ? ` ${tag}` : ""} – ${it.set_description}`);
    }
  }
  lines.push(...castLines(day, cast));
  if (day.safety_notes) lines.push("", `Safety: ${day.safety_notes}`);
  lines.push("", "Live call sheet (updates itself):", crewLink);
  return lines.join("\n");
}

/** Same precedence as the server's personal sheet: today's entry, then the standing time, then the crew call. */
export function personalCallFor(day: DayFacts, member: CrewMember): { call: string; pickup: string; note: string } {
  const entry = day.crewCalls[member.id];
  return {
    call: entry?.call || member.standard_call_time || day.general_crew_call || "",
    pickup: entry?.pickup || "",
    note: entry?.note || "",
  };
}

/** One person's message: their own times first (that is what they scroll for), the personal link last. */
export function personalMessageText(day: DayFacts, member: CrewMember, locations: Location[], personalLink: string): string {
  const firstName = member.contact.name.trim().split(/\s+/)[0] || member.contact.name;
  const me = personalCallFor(day, member);
  const lines: string[] = [`Hi ${firstName},`, heading(day), ""];
  if (me.call) lines.push(`Your call: *${me.call}*`);
  if (me.pickup) lines.push(`Pickup: ${me.pickup}`);
  if (me.note) lines.push(`Note: ${me.note}`);
  lines.push(...locationLines(firstLocation(day, locations)));
  lines.push("", "Your call sheet (updates itself):", personalLink);
  return lines.join("\n");
}

/**
 * wa.me wants digits only, with the country code and no leading zeros or "+".
 * Czech numbers are nine digits; a bare nine-digit number gets 420 because
 * that is where every pilot crew is. Anything else that is not a plausible
 * international number returns null so the UI falls back to copy/share
 * instead of opening a chat with the wrong person.
 */
export function whatsappNumber(phone: string | null | undefined): string | null {
  if (!phone) return null;
  let digits = phone.replace(/[\s().-]/g, "");
  if (digits.startsWith("+")) digits = digits.slice(1);
  else if (digits.startsWith("00")) digits = digits.slice(2);
  if (!/^\d+$/.test(digits)) return null;
  if (digits.length === 9) digits = `420${digits}`;
  if (digits.length < 10 || digits.length > 15) return null;
  return digits;
}

/** A chat with that number when there is one, otherwise WhatsApp's own "pick a chat" entry with the text ready. */
export function whatsappUrl(number: string | null, text: string): string {
  const base = number ? `https://wa.me/${number}` : "https://wa.me/";
  return `${base}?text=${encodeURIComponent(text)}`;
}

export function canWebShare(): boolean {
  return typeof navigator !== "undefined" && typeof navigator.share === "function";
}

/** FR-37: the message that hands a crew member their one link at the start of the shoot. */
export function onboardingMessageText(productionName: string | null, member: CrewMember, personalLink: string): string {
  const firstName = member.contact.name.trim().split(/\s+/)[0] || member.contact.name;
  const prod = productionName ? ` for *${productionName}*` : "";
  return [
    `Hi ${firstName}, here is your call sheet link${prod}:`,
    personalLink,
    "",
    "Keep it: it always opens your next shoot day with your own call time, and it works with no signal once opened. Every revision shows up in it.",
  ].join("\n");
}

/** One line per person, for pasting into a group or a spreadsheet. */
export function allLinksText(members: CrewMember[], linkFor: (m: CrewMember) => string): string {
  return members.map((m) => `${m.contact.name} · ${m.department}: ${linkFor(m)}`).join("\n");
}
