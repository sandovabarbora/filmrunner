/**
 * Network-first load with an honest fallback: on success the payload is
 * cached; on failure the last cached copy is returned and labelled as
 * such, because a crew member on a rural set must know whether what they
 * see could be stale.
 */

import { cacheCallSheet, getCachedCallSheet } from "./cache";
import type { CallSheet, PersonalSheet } from "./types";

export type LoadResult =
  | { kind: "live"; data: CallSheet }
  | { kind: "cached"; data: CallSheet; fetchedAt: string; reason: string }
  | { kind: "error"; reason: string };

export async function loadCallSheet(url: string, id: string): Promise<LoadResult> {
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      throw new Error(`API returned ${resp.status}`);
    }
    const data = (await resp.json()) as CallSheet;
    await cacheCallSheet(id, data);
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
