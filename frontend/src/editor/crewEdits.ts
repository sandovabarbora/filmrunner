/**
 * An edit to an existing crew member made while offline (FR-18 failure case).
 * Kept in IndexedDB, separate from the day draft store (drafts.ts), so a
 * dropped connection on the Crew tab loses nothing and the row shows "not
 * saved" until the edit is retried successfully.
 */

export interface PendingCrewEdit {
  memberId: string;
  productionId: string;
  contactId: string;
  name: string;
  phone: string;
  department: string;
  position: string;
  standard_call_time: string | null;
  is_head_of_department: boolean;
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
