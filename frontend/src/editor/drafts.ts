/**
 * The AD's draft lives on the phone (ADR-003). Saved on every change to
 * IndexedDB so a dropped connection or a closed app loses nothing. The
 * server only ever sees a publish.
 */

import type { CastStatus, ScheduleItemCreate } from "../types";

export interface CastCallDraft { status: CastStatus; pickup: string; call: string; makeup: string; onSet: string }

export interface Draft {
  id: string;
  productionId: string | null;
  productionName: string | null;
  callSheetId: string | null;
  headOfDayId: string | null;
  lastPublishedLetter: string | null;
  publishedAt: string | null;
  dirtySincePublish: boolean;
  shoot_date: string;
  day_number: number;
  day_count: number;
  unit_name: string;
  general_crew_call: string;
  shooting_call: string;
  sunrise: string;
  sunset: string;
  weather_forecast: string;
  safety_notes: string;
  items: ScheduleItemCreate[];
  crewCalls: Record<string, { call: string; pickup: string; note: string }>;
  /** FR-33: cast working today, by cast member id. Absent = not on today's sheet. */
  castCalls: Record<string, CastCallDraft>;
  updatedAt: string;
}

const DB_NAME = "filmrunner-editor";
const STORE = "drafts";
/** Drafts are keyed by day: the call sheet id, or `new:<productionId>` before the first publish. */
export function draftKey(productionId: string, callSheetId: string | null): string {
  return callSheetId ?? `new:${productionId}`;
}

export function emptyDraft(productionId: string, productionName: string | null): Draft {
  return {
    id: draftKey(productionId, null),
    productionId,
    productionName,
    callSheetId: null,
    headOfDayId: null,
    lastPublishedLetter: null,
    publishedAt: null,
    dirtySincePublish: false,
    shoot_date: new Date().toISOString().slice(0, 10),
    day_number: 1,
    day_count: 1,
    unit_name: "Main Unit",
    general_crew_call: "",
    shooting_call: "",
    sunrise: "",
    sunset: "",
    weather_forecast: "",
    safety_notes: "",
    items: [],
    crewCalls: {},
    castCalls: {},
    updatedAt: new Date().toISOString(),
  };
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** ISO date + n days, done in UTC so a DST switch never shifts the calendar day. */
export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/**
 * FR-30: tomorrow starts as today. Date +1, day number +1, the same unit,
 * calls, head of day, safety notes, scenes (locations repeat for days) and
 * personal calls. Weather and sun are left blank: they belong to the date
 * and fill in from the location (FR-27). Nothing here is published.
 */
export function nextDayFrom(d: Draft): Draft {
  const dayNumber = d.day_number + 1;
  return {
    ...emptyDraft(d.productionId ?? "", d.productionName),
    shoot_date: addDays(d.shoot_date, 1),
    day_number: dayNumber,
    day_count: Math.max(d.day_count, dayNumber),
    unit_name: d.unit_name,
    general_crew_call: d.general_crew_call,
    shooting_call: d.shooting_call,
    safety_notes: d.safety_notes,
    headOfDayId: d.headOfDayId,
    items: d.items.map((it) => ({ ...it })),
    crewCalls: Object.fromEntries(Object.entries(d.crewCalls).map(([k, v]) => [k, { ...v }])),
    castCalls: Object.fromEntries(Object.entries(d.castCalls).map(([k, v]) => [k, { ...v }])),
  };
}

/** True when a draft has anything the AD typed that a replacement would lose. */
export function draftHasContent(d: Draft | null): boolean {
  return !!d && (d.general_crew_call.trim() !== "" || d.items.length > 0 || d.shooting_call.trim() !== "" || d.safety_notes.trim() !== "");
}

export async function loadDraft(key: string): Promise<Draft | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).get(key);
    req.onsuccess = () => resolve((req.result as Draft | undefined) ?? null);
    req.onerror = () => reject(req.error);
  });
}

export async function saveDraft(draft: Draft): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ ...draft, updatedAt: new Date().toISOString() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function clearDraft(key: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
