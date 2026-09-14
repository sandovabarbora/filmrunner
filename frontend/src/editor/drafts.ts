/**
 * The AD's draft lives on the phone (ADR-003). Saved on every change to
 * IndexedDB so a dropped connection or a closed app loses nothing. The
 * server only ever sees a publish.
 */

import type { ScheduleItemCreate } from "../types";

export interface Draft {
  id: string;
  productionId: string | null;
  productionName: string | null;
  callSheetId: string | null;
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
  updatedAt: string;
}

const DB_NAME = "filmrunner-editor";
const STORE = "drafts";
export const CURRENT_DRAFT_ID = "current";

export function emptyDraft(): Draft {
  return {
    id: CURRENT_DRAFT_ID,
    productionId: null,
    productionName: null,
    callSheetId: null,
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

export async function loadDraft(): Promise<Draft | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).get(CURRENT_DRAFT_ID);
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

export async function clearDraft(): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(CURRENT_DRAFT_ID);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
