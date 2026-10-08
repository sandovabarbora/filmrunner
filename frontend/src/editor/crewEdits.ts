/**
 * An edit to an existing crew member made while offline (FR-18 failure case).
 * Kept in IndexedDB, separate from the day draft store (drafts.ts), so a
 * dropped connection on the Crew tab loses nothing and the row shows "not
 * saved" until the edit is retried successfully.
 *
 * FR-144: only the fields the user actually changed are stored and later
 * sent (`patch`, built by `diffCrewEditFields`). Two devices queuing
 * offline edits to different fields on the same crew member and syncing
 * one after another must not have the second sync's untouched fields
 * (its own stale snapshot of them) silently revert the first sync's
 * change — which a full-record resend would do, since both the live
 * `save()` and the old offline queue sent every field every time.
 */

export interface CrewEditableFields {
  name: string;
  phone: string;
  department: string;
  position: string;
  standard_call_time: string | null;
  is_head_of_department: boolean;
}

/** Only the keys whose value actually differs between the two snapshots. */
export function diffCrewEditFields(original: CrewEditableFields, edited: CrewEditableFields): Partial<CrewEditableFields> {
  const patch: Partial<CrewEditableFields> = {};
  (Object.keys(edited) as (keyof CrewEditableFields)[]).forEach((key) => {
    if (edited[key] !== original[key]) (patch as Record<string, unknown>)[key] = edited[key];
  });
  return patch;
}

/** Applies a partial patch onto a base record, mirroring the backend's `exclude_unset` partial update: a key absent from `patch` is left untouched. */
export function mergeCrewEdit(base: CrewEditableFields, patch: Partial<CrewEditableFields>): CrewEditableFields {
  return { ...base, ...patch };
}

export interface PendingCrewEdit {
  memberId: string;
  productionId: string;
  contactId: string;
  patch: Partial<CrewEditableFields>;
  savedAt: string;
}

const DB_NAME = "filmrunner-crew-edits";
const STORE = "pending";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "memberId" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function loadAllPendingCrewEdits(productionId: string): Promise<PendingCrewEdit[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
    req.onsuccess = () => resolve((req.result as PendingCrewEdit[]).filter((e) => e.productionId === productionId));
    req.onerror = () => reject(req.error);
  });
}

export async function savePendingCrewEdit(edit: PendingCrewEdit): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(edit);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function clearPendingCrewEdit(memberId: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(memberId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
