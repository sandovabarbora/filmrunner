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
import type { CallSheet } from "./types";

const SOURCE_HEADER = "x-filmrunner-source";
const FETCHED_AT_HEADER = "x-filmrunner-fetched-at";

export type LoadResult =
  | { kind: "live"; data: CallSheet }
  | { kind: "cached"; data: CallSheet; fetchedAt: string; reason: string }
  | { kind: "unknown"; data: CallSheet }
  | { kind: "error"; reason: string };

export async function loadCallSheet(url: string, id: string): Promise<LoadResult> {
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
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
