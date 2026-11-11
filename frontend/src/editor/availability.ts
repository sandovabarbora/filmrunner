import { addDays } from "./drafts";
import type { AvailabilityIssue } from "../types";

/** Every date from `from` to `to`, both included; one day when `to` is empty. Empty when the range is reversed or too long. */
export function daysInRange(from: string, to: string, max = 120): string[] {
  if (!from) return [];
  const last = to || from;
  if (last < from) return [];
  const days: string[] = [];
  for (let d = from; d <= last; d = addDays(d, 1)) {
    days.push(d);
    if (days.length > max) return [];
  }
  return days;
}

/** "14. 12., 15. 12." in Czech, "14 Dec, 15 Dec" in English; a run of three or more reads as a range. */
export function formatDays(days: string[], lang: "cs" | "en"): string {
  const one = (iso: string) => {
    const [, m, d] = iso.split("-").map(Number);
    return lang === "cs" ? `${d}. ${m}.` : new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  };
  const sorted = [...new Set(days)].sort();
  const runs: string[][] = [];
  for (const d of sorted) {
    const run = runs.at(-1);
    if (run && addDays(run.at(-1)!, 1) === d) run.push(d); else runs.push([d]);
  }
  return runs.map((r) => (r.length >= 3 ? `${one(r[0])}–${one(r.at(-1)!)}` : r.map(one).join(", "))).join(", ");
}

/** Issues split the way every screen shows them: the actors outside their days by name, the rest as one quiet line. */
export function splitIssues(issues: AvailabilityIssue[]) {
  return { outside: issues.filter((i) => i.status === "outside"), notEntered: issues.filter((i) => i.status === "not_entered") };
}
