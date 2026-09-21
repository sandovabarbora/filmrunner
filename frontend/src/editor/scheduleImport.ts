/**
 * FR-56: the shooting schedule from a spreadsheet — a plain Excel the AD keeps
 * (day, date, scene, INT/EXT, D/N, set, pages, location, cast) or a Movie Magic
 * Scheduling export (scene rows with "Day 3 — Wed, Sep 23" / "End of Day 3"
 * banner rows). Rows become days with scenes in order. Pure and unit-tested;
 * the file is parsed in the browser and never leaves the phone.
 */

export type ScheduleRole = "day" | "date" | "scene" | "int_ext" | "day_night" | "set" | "pages" | "location" | "cast";
export type ScheduleColumnMap = Partial<Record<ScheduleRole, number>>;

export interface ImportedScene {
  scene_number: string;
  int_ext: "INT" | "EXT";
  day_night: "DAY" | "NIGHT";
  set_description: string;
  page_count_eighths: number;
  location: string | null;
  cast: string[];
}

export interface ImportedDay {
  day_number: number | null;
  shoot_date: string | null;  // ISO
  scenes: ImportedScene[];
  warnings: string[];
}

const SYNONYMS: Record<ScheduleRole, string[]> = {
  day: ["day", "shoot day", "shooting day", "den", "natáčecí den", "natačecí den", "nd", "day #"],
  date: ["date", "datum", "shoot date"],
  scene: ["scene", "sc", "sc.", "scene #", "scéna", "scena", "obraz", "obr", "obr."],
  int_ext: ["int/ext", "i/e", "ie", "int ext", "int./ext.", "interiér/exteriér", "int", "ext"],
  day_night: ["d/n", "day/night", "dn", "den/noc", "time of day"],
  set: ["set", "set name", "set description", "description", "motiv", "prostředí", "prostredi", "místo děje", "synopsis", "slugline"],
  pages: ["pages", "pgs", "page count", "stránky", "stranky", "str.", "str", "rozsah", "eighths"],
  location: ["location", "lokace", "lokalita", "místo", "misto", "location name"],
  cast: ["cast", "cast id", "cast ids", "herci", "obsazení", "obsazeni", "characters"],
};

function norm(cell: unknown): string {
  return String(cell ?? "").trim();
}

function roleOfHeader(h: string): ScheduleRole | null {
  const l = h.trim().toLowerCase().replace(/[:*]/g, "");
  for (const role of Object.keys(SYNONYMS) as ScheduleRole[]) {
    if (SYNONYMS[role].some((syn) => l === syn)) return role;
  }
  for (const role of Object.keys(SYNONYMS) as ScheduleRole[]) {
    if (SYNONYMS[role].some((syn) => syn.length > 2 && (l.startsWith(`${syn} `) || l.endsWith(` ${syn}`)))) return role;
  }
  return null;
}

/** The first row (within the first 15) that names a scene column; its map. */
export function detectScheduleColumns(rows: unknown[][]): { headerIndex: number; map: ScheduleColumnMap } | null {
  for (let i = 0; i < Math.min(rows.length, 15); i++) {
    const map: ScheduleColumnMap = {};
    (rows[i] ?? []).forEach((cell, col) => {
      const role = roleOfHeader(norm(cell));
      if (role && map[role] === undefined) map[role] = col;
    });
    if (map.scene !== undefined) return { headerIndex: i, map };
  }
  return null;
}

/** "2 3/8" → 19, "3/8" → 3, "2" → 16 (whole pages), "1.5" → 12, "19/8" → 19; anything else 0. */
export function parseEighths(raw: unknown): number {
  const s = norm(raw).replace(",", ".");
  if (!s) return 0;
  const mixed = /^(\d+)\s+(\d+)\/8$/.exec(s);
  if (mixed) return Number(mixed[1]) * 8 + Number(mixed[2]);
  const frac = /^(\d+)\/8$/.exec(s);
  if (frac) return Number(frac[1]);
  const num = Number(s);
  if (Number.isFinite(num) && num >= 0) return Math.round(num * 8);
  return 0;
}

export function parseIntExt(raw: unknown): "INT" | "EXT" {
  const s = norm(raw).toUpperCase();
  return s.startsWith("I") ? "INT" : "EXT";
}

export function parseDayNight(raw: unknown): "DAY" | "NIGHT" {
  const s = norm(raw).toUpperCase();
  return s.startsWith("N") ? "NIGHT" : "DAY";
}

const MONTHS: Record<string, number> = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12,
  led: 1, úno: 2, uno: 2, bře: 3, bre: 3, dub: 4, kvě: 5, kve: 5, čer: 6, cer: 6, čvc: 7, cvc: 7, srp: 8, zář: 9, zar: 9, říj: 10, rij: 10, lis: 11, pro: 12 };

/** ISO date from what spreadsheets and Movie Magic write: 2026-09-23, 23.9.2026, 23/09/2026, Sep 23, 2026, 9/23/2026 (US, from MM). */
export function parseDate(raw: unknown): string | null {
  const s = norm(raw);
  if (!s) return null;
  let m = /(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return iso(Number(m[1]), Number(m[2]), Number(m[3]));
  m = /(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})/.exec(s);
  if (m) return iso(Number(m[3]), Number(m[2]), Number(m[1]));
  m = /(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (m) {
    const a = Number(m[1]), b = Number(m[2]);
    // Movie Magic exports US order (m/d/yyyy); a first number over 12 can only be a day.
    return a > 12 ? iso(Number(m[3]), b, a) : iso(Number(m[3]), a, b);
  }
  m = /([A-Za-zěščřžýáíéúůň]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})/.exec(s);
  if (m && MONTHS[m[1].toLowerCase().slice(0, 4)] !== undefined) return iso(Number(m[3]), MONTHS[m[1].toLowerCase().slice(0, 4)], Number(m[2]));
  if (m && MONTHS[m[1].toLowerCase().slice(0, 3)] !== undefined) return iso(Number(m[3]), MONTHS[m[1].toLowerCase().slice(0, 3)], Number(m[2]));
  m = /(\d{1,2})\.?\s+([A-Za-zěščřžýáíéúůň]{3,})\.?\s+(\d{4})/.exec(s);
  if (m && MONTHS[m[2].toLowerCase().slice(0, 3)] !== undefined) return iso(Number(m[3]), MONTHS[m[2].toLowerCase().slice(0, 3)], Number(m[1]));
  return null;
}

function iso(y: number, mo: number, d: number): string | null {
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** "Day 3 — Wed, Sep 23, 2026" / "End of Day 3" / "Natáčecí den 3 – 23.9.2026" banner rows. */
function bannerDay(rowText: string): { day: number; date: string | null; end: boolean } | null {
  const m = /(end of\s+)?(?:shoot(?:ing)? )?(?:day|den|natáčecí den|nd)\s*#?\s*(\d+)/i.exec(rowText);
  if (!m) return null;
  return { day: Number(m[2]), date: parseDate(rowText), end: !!m[1] };
}

function splitCast(raw: unknown): string[] {
  return norm(raw).split(/[,;/]+/).map((c) => c.trim()).filter(Boolean);
}

/**
 * Group scene rows into days. Order of precedence: a day column; else banner
 * rows; else a date column (days numbered in date order). None → one day with
 * no date, which the UI names "Imported schedule" instead of guessing.
 */
export function rowsToSchedule(rows: unknown[][], headerIndex: number, map: ScheduleColumnMap): ImportedDay[] {
  const cellAt = (row: unknown[], role: ScheduleRole) => (map[role] === undefined ? "" : norm(row[map[role]!]));
  type Bucket = { key: string; day: ImportedDay };
  const buckets: Bucket[] = [];
  const bucketFor = (key: string, dayNumber: number | null, date: string | null): ImportedDay => {
    let b = buckets.find((x) => x.key === key);
    if (!b) { b = { key, day: { day_number: dayNumber, shoot_date: date, scenes: [], warnings: [] } }; buckets.push(b); }
    if (b.day.day_number === null && dayNumber !== null) b.day.day_number = dayNumber;
    if (b.day.shoot_date === null && date) b.day.shoot_date = date;
    return b.day;
  };

  let current: ImportedDay | null = null;      // from a "Day N" banner above the rows
  let pending: ImportedScene[] = [];            // rows before an "End of Day N" banner
  const useDayCol = map.day !== undefined;
  const useDateCol = !useDayCol && map.date !== undefined;

  for (let i = headerIndex + 1; i < rows.length; i++) {
    const row = rows[i] ?? [];
    const cells = row.map(norm);
    const nonEmpty = cells.filter((c) => c !== "");
    if (nonEmpty.length === 0) continue;
    const scene = cellAt(row, "scene");
    if (!scene) {
      const banner = bannerDay(nonEmpty.join(" "));
      if (banner && banner.end) {
        const day = bucketFor(`day:${banner.day}`, banner.day, banner.date);
        day.scenes.push(...pending); pending = []; current = null;
      } else if (banner) {
        if (pending.length) { const orphan = bucketFor("none", null, null); orphan.scenes.push(...pending); pending = []; }
        current = bucketFor(`day:${banner.day}`, banner.day, banner.date);
      }
      continue;
    }
    const item: ImportedScene = {
      scene_number: scene,
      int_ext: parseIntExt(cellAt(row, "int_ext")),
      day_night: parseDayNight(cellAt(row, "day_night")),
      set_description: cellAt(row, "set"),
      page_count_eighths: parseEighths(cellAt(row, "pages")),
      location: cellAt(row, "location") || null,
      cast: splitCast(cellAt(row, "cast")),
    };
    if (useDayCol) {
      const n = Number(cellAt(row, "day").replace(/\D/g, ""));
      const date = parseDate(cellAt(row, "date"));
      if (Number.isFinite(n) && n > 0) bucketFor(`day:${n}`, n, date).scenes.push(item);
      else bucketFor("none", null, null).scenes.push(item);
    } else if (useDateCol) {
      const date = parseDate(cellAt(row, "date"));
      if (date) bucketFor(`date:${date}`, null, date).scenes.push(item);
      else bucketFor("none", null, null).scenes.push(item);
    } else if (current) {
      current.scenes.push(item);
    } else {
      pending.push(item);
    }
  }
  if (pending.length) bucketFor("none", null, null).scenes.push(...pending);

  const days = buckets.map((b) => b.day);
  // Date-grouped days get numbers in date order; day-numbered days are sorted by number.
  if (useDateCol) {
    days.sort((a, b) => (a.shoot_date ?? "9999").localeCompare(b.shoot_date ?? "9999"));
    days.forEach((d, i) => { if (d.shoot_date) d.day_number = i + 1; });
  } else {
    days.sort((a, b) => (a.day_number ?? 9999) - (b.day_number ?? 9999));
  }
  for (const d of days) {
    if (d.day_number === null && d.shoot_date === null) d.warnings.push("no day or date in the file: will be one unpublished day named Imported schedule");
    else if (d.shoot_date === null) d.warnings.push("no date for this day: pick one before publishing");
    if (d.scenes.some((sc) => !sc.set_description)) d.warnings.push("some scenes have no set description");
  }
  return days;
}

/** The location names an import will need, in first-use order. */
export function locationNames(days: ImportedDay[]): string[] {
  const out: string[] = [];
  for (const d of days) for (const s of d.scenes) if (s.location && !out.some((n) => n.toLowerCase() === s.location!.toLowerCase())) out.push(s.location);
  return out;
}
