/**
 * IndexedDB store for call sheets, keyed by id, with the time it was
 * fetched. Same database and store names as the original vanilla viewer so
 * phones that already cached a sheet keep it across the React migration.
 *
 * Reference: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB
 */

import type { CallSheet } from "./types";

const DB_NAME = "filmrunner-callsheets";
const STORE_NAME = "callsheets";

export interface CachedCallSheet {
  id: string;
  data: CallSheet;
  fetchedAt: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE_NAME, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function cacheCallSheet(id: string, data: CallSheet): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const entry: CachedCallSheet = { id, data, fetchedAt: new Date().toISOString() };
    tx.objectStore(STORE_NAME).put(entry);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getCachedCallSheet(id: string): Promise<CachedCallSheet | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).get(id);
    req.onsuccess = () => resolve((req.result as CachedCallSheet | undefined) ?? null);
    req.onerror = () => reject(req.error);
  });
}
