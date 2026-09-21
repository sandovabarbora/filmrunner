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

export type LoadResult =
  | { kind: "live"; data: CallSheet }
  | { kind: "cached"; data: CallSheet; fetchedAt: string; reason: string }
  | { kind: "unknown"; data: CallSheet }
  | { kind: "not_found" }
  | { kind: "error"; reason: string };

export async function loadCallSheet(url: string, id: string): Promise<LoadResult> {
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
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
      const fetchedAt = resp.headers.get(FETCHED_AT_HEADER) ?? new Date(0).toISOString();
      await cacheCallSheet(id, data);
      return { kind: "cached", data, fetchedAt, reason: "offline: served from the service worker cache" };
    }

    await cacheCallSheet(id, data);

    if (source !== "network" && navigator.serviceWorker?.controller) {
      // A service worker is intercepting this request (so it could have
      // stamped the response) but did not: an older worker version, still
      // active from before this marking existed. We cannot tell whether it
      // answered from the network or its own cache, so never claim "live".
      return { kind: "unknown", data };
    }

    // No header and no controlling worker: the request went straight to
    // the network with nothing in front of it, so it is live by construction.
    return { kind: "live", data };
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    const cached = await getCachedCallSheet(id);
    if (cached) {
      return { kind: "cached", data: cached.data, fetchedAt: cached.fetchedAt, reason };
    }
    return { kind: "error", reason };
  }
}

export function publicCallSheetUrl(apiBase: string, id: string): string {
  return `${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${id}`;
}

const PERSONAL_DB = "filmrunner-personal";

/** Personal block: network first, last copy from localStorage second, "invalid" when the server says the token is unknown. */
export async function loadPersonal(apiBase: string, sheetId: string, token: string): Promise<PersonalSheet | "invalid"> {
  const key = `${PERSONAL_DB}:${sheetId}:${token}`;
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/call-sheets/${sheetId}/me/${encodeURIComponent(token)}`, { signal: AbortSignal.timeout(5000) });
    if (resp.status === 404) return "invalid";
    if (!resp.ok) throw new Error(`API returned ${resp.status}`);
    const data = (await resp.json()) as PersonalSheet;
    try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* storage unavailable: fine */ }
    return data;
  } catch {
    try {
      const raw = localStorage.getItem(key);
      if (raw) return JSON.parse(raw) as PersonalSheet;
    } catch { /* fall through */ }
    return "invalid";
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
  try {
    const resp = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/public/crew/${encodeURIComponent(token)}/next`, { signal: AbortSignal.timeout(5000) });
    if (resp.status === 404) return "invalid";
    if (!resp.ok) throw new Error(`API returned ${resp.status}`);
    const data = (await resp.json()) as CrewNextDay;
    try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* storage unavailable: fine */ }
    return data;
  } catch {
    try {
      const raw = localStorage.getItem(key);
      if (raw) return JSON.parse(raw) as CrewNextDay;
    } catch { /* fall through */ }
    return null;
  }
}
