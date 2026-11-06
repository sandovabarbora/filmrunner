/**
 * Network-first load with an honest fallback: on success the payload is
 * cached; on failure the last cached copy is returned and labelled as
 * such, because a crew member on a rural set must know whether what they
 * see could be stale.
 *
 * fetch() resolving is not proof of freshness: the service worker's own
 * NetworkFirst cache (vite.config.ts) can answer a "successful" fetch from
 * its cache when offline or the network times out. Its plugin stamps every
 * response with x-filmrunner-source so this module never has to guess from
 * fetch() success alone.
 */

import { cacheCallSheet, getCachedCallSheet } from "./cache";
import type { CallSheet, CrewNextDay, PersonalSheet } from "./types";

const SOURCE_HEADER = "x-filmrunner-source";
const FETCHED_AT_HEADER = "x-filmrunner-fetched-at";

// A saved copy is worth more than a long wait, so a phone that has one gives up early. A phone with nothing
// saved has nothing better to show, and a cold server with a heavy day has been measured at 7 s.
// The worker's own 5 s NetworkFirst timeout does not undercut this: with nothing in its cache it keeps waiting
// for the network, and with something in its cache it answers with a copy stamped as such.
const TIMEOUT_WITH_COPY_MS = 5_000;
const TIMEOUT_FIRST_LOAD_MS = 15_000;

// no-store: the browser would otherwise hold a retry back behind a request still hanging on the same URL.
function readOptions(hasCopy: boolean): RequestInit {
  return { cache: "no-store", signal: AbortSignal.timeout(hasCopy ? TIMEOUT_WITH_COPY_MS : TIMEOUT_FIRST_LOAD_MS) };
}

export type LoadResult =
  | { kind: "live"; data: CallSheet }
  | { kind: "cached"; data: CallSheet; fetchedAt: string; reason: string }
  | { kind: "unknown"; data: CallSheet }
  | { kind: "not_found" }
  | { kind: "error"; reason: string };

// Storage can refuse (private windows, a full disk). The sheet in hand must still reach the screen.
async function readSavedSheet(id: string) {
  try { return await getCachedCallSheet(id); } catch { return null; }
}

async function saveSheet(id: string, data: CallSheet): Promise<void> {
  try { await cacheCallSheet(id, data); } catch { /* the next open just has no copy */ }
}

export async function loadCallSheet(url: string, id: string): Promise<LoadResult> {
  const saved = await readSavedSheet(id);
  // Read before the request: on a first visit the worker claims the page while the request is in flight.
  // A request sent with no controller goes straight to the network, whoever controls the page by the time it answers.
  const sentThroughWorker = !!navigator.serviceWorker?.controller;
  try {
    const resp = await fetch(url, readOptions(saved !== null));
    if (resp.status === 404) {
      // The server has spoken authoritatively: this id does not exist (the
      // same response the API gives for a sheet that exists but is not
      // public, since it has no separate concept for that yet). Unlike a
      // network failure, no retry or cached copy fixes this, so it must
      // never be shown as "could not be reached, try again".
      return { kind: "not_found" };
    }
    if (!resp.ok) {
      throw new Error(`API returned ${resp.status}`);
    }
    const data = (await resp.json()) as CallSheet;
    const source = resp.headers.get(SOURCE_HEADER);

    if (source === "cache") {
      // Not saved again: that would date an old copy to now, and the banner promises when it was really saved.
      const fetchedAt = resp.headers.get(FETCHED_AT_HEADER) ?? saved?.fetchedAt ?? new Date(0).toISOString();
      return { kind: "cached", data, fetchedAt, reason: "offline: served from the service worker cache" };
    }

    await saveSheet(id, data);

    if (source !== "network" && sentThroughWorker) {
      // A worker answered without the stamp: an older version, from before this
      // marking existed. It could have answered from its own cache, so never claim "live".
      return { kind: "unknown", data };
    }

    return { kind: "live", data };
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    if (saved) {
      return { kind: "cached", data: saved.data, fetchedAt: saved.fetchedAt, reason };
    }
    return { kind: "error", reason };
  }
}

export function publicCallSheetUrl(apiBase: string, id: string): string {
  return `${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${id}`;
}

const PERSONAL_DB = "filmrunner-personal";

export type PersonalResult =
  | { kind: "live"; data: PersonalSheet }
  | { kind: "saved"; data: PersonalSheet; savedAt: string }
  | { kind: "invalid" }
  | { kind: "unreachable" };

type SavedPersonal = { data: PersonalSheet; savedAt: string };

function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function store(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable: fine */ }
}

/** Personal block: network first, last copy second. Only the server's own 404 means the token is unknown; a 500, a 429 or a timeout says nothing about the person. */
export async function loadPersonal(apiBase: string, sheetId: string, token: string): Promise<PersonalResult> {
  const key = `${PERSONAL_DB}:${sheetId}:${token}`;
  const stored = readStored<SavedPersonal>(key);
  const saved = stored?.savedAt ? stored : null;  // a copy from before savedAt existed cannot say how old it is
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${sheetId}/me/${encodeURIComponent(token)}`, readOptions(saved !== null));
    if (resp.status === 404) return { kind: "invalid" };
    if (!resp.ok) throw new Error(`API returned ${resp.status}`);
    const data = (await resp.json()) as PersonalSheet;
    // This route is under the worker's NetworkFirst too, so it can answer from its own cache.
    if (resp.headers.get(SOURCE_HEADER) === "cache") {
      const savedAt = resp.headers.get(FETCHED_AT_HEADER) ?? saved?.savedAt;
      if (savedAt) return { kind: "saved", data, savedAt };
      throw new Error("worker copy with no date");
    }
    store(key, { data, savedAt: new Date().toISOString() } satisfies SavedPersonal);
    return { kind: "live", data };
  } catch {
    return saved ? { kind: "saved", data: saved.data, savedAt: saved.savedAt } : { kind: "unreachable" };
  }
}

const NEXT_DB = "filmrunner-next";

/**
 * FR-32: which day a person's stable link opens. Network first; the last
 * answer is kept per token so the link still opens the right cached sheet
 * with no signal. "invalid" only when the server itself says the token is
 * unknown — never on a network failure.
 */
export async function loadNextDay(apiBase: string, token: string): Promise<CrewNextDay | "invalid" | null> {
  const key = `${NEXT_DB}:${token}`;
  const saved = readStored<CrewNextDay>(key);
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/crew/${encodeURIComponent(token)}/next`, readOptions(saved !== null));
    if (resp.status === 404) return "invalid";
    if (!resp.ok) throw new Error(`API returned ${resp.status}`);
    const data = (await resp.json()) as CrewNextDay;
    store(key, data);
    return data;
  } catch {
    return saved;
  }
}

/** FR-36: tell the AD this personal link opened the sheet live. Fire and forget; never blocks the sheet. */
export function markSeen(apiBase: string, sheetId: string, token: string): void {
  try {
    void fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${sheetId}/seen/${encodeURIComponent(token)}`, { method: "POST", keepalive: true }).catch(() => undefined);
  } catch { /* offline: nothing to report */ }
}

export type ConfirmResult = { kind: "confirmed"; confirmedAt: string } | { kind: "stale" } | { kind: "failed" };

/** FR-202: "I know about REV X". Unlike a read receipt the person is waiting for the answer, so every outcome is reported. */
export async function confirmRevision(apiBase: string, sheetId: string, token: string, letter: string): Promise<ConfirmResult> {
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${sheetId}/confirm/${encodeURIComponent(token)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision_letter: letter }),
    });
    if (resp.status === 409) return { kind: "stale" };
    if (!resp.ok) return { kind: "failed" };
    const data = (await resp.json()) as { confirmed_at: string };
    return { kind: "confirmed", confirmedAt: data.confirmed_at };
  } catch {
    return { kind: "failed" };
  }
}
