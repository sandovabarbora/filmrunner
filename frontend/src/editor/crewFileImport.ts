/**
 * FR-55: the crew from a spreadsheet. Given the sheet as rows of cells (SheetJS
 * `sheet_to_json(header: 1)`), find the header row and which column is what,
 * in Czech or English, then turn the rows into the same preview rows the paste
 * import (FR-31) uses. Pure; the file itself is parsed in the browser and never
 * leaves the phone.
 */

import type { ParsedCrewRow } from "./crewImport";

export type Role = "name" | "phone" | "department" | "position" | "email";
export type ColumnMap = Partial<Record<Role, number>>;

const SYNONYMS: Record<Role, string[]> = {
  name: ["name", "jméno", "jmeno", "jméno a příjmení", "příjmení", "prijmeni", "full name", "člen", "clen", "osoba", "crew"],
  phone: ["phone", "telefon", "tel", "tel.", "mobil", "mobile", "číslo", "cislo", "kontakt", "gsm"],
  department: ["department", "dept", "oddělení", "oddeleni", "sekce", "úsek", "usek", "profese", "obor"],
  position: ["position", "pozice", "funkce", "role", "job", "title", "job title"],
  email: ["email", "e-mail", "mail"],
};

const HOD_WORDS = /\b(hod|head|vedoucí|vedouci)\b/i;
const PHONE_LIKE = /^\+?[\d\s().-]{9,}$/;

function norm(cell: unknown): string {
  return String(cell ?? "").trim();
}

function roleOfHeader(h: string): Role | null {
  const l = h.trim().toLowerCase().replace(/[:*]/g, "");
  for (const role of Object.keys(SYNONYMS) as Role[]) {
    if (SYNONYMS[role].some((syn) => l === syn || l.startsWith(`${syn} `) || l.endsWith(` ${syn}`))) return role;
  }
  return null;
}

/** The first row (within the first 10) whose cells name at least a name column; its column map. */
export function detectColumns(rows: unknown[][]): { headerIndex: number; map: ColumnMap } | null {
  for (let i = 0; i < Math.min(rows.length, 10); i++) {
    const map: ColumnMap = {};
    rows[i].forEach((cell, col) => {
      const role = roleOfHeader(norm(cell));
      if (role && map[role] === undefined) map[role] = col;
    });
    if (map.name !== undefined) return { headerIndex: i, map };
  }
  return null;
}

/** "A", "B", … for the mapping row when a sheet has no usable header. */
export function columnLetter(i: number): string {
  let s = "";
  for (let n = i; n >= 0; n = Math.floor(n / 26) - 1) s = String.fromCharCode(65 + (n % 26)) + s;
  return s;
}

/**
 * Rows below the header become people. A row with text in the name column only
 * (no phone, no position) is a department header, like "Camera:" in a paste.
 */
export function rowsToCrew(rows: unknown[][], headerIndex: number, map: ColumnMap, knownNames: Iterable<string> = []): ParsedCrewRow[] {
  const known = new Set([...knownNames].map((n) => n.trim().toLowerCase()));
  const out: ParsedCrewRow[] = [];
  let department = "";
  const cellAt = (row: unknown[], role: Role) => (map[role] === undefined ? "" : norm(row[map[role]!]));
  // An optional "HoD" / "vedoucí" column: any mark in it (x, ano, yes, 1) makes a head of department.
  const hodCol = (rows[headerIndex] ?? []).findIndex((h) => HOD_WORDS.test(norm(h)));
  for (let i = headerIndex + 1; i < rows.length; i++) {
    const row = rows[i] ?? [];
    const nonEmpty = row.map(norm).filter((c) => c !== "");
    if (nonEmpty.length === 0) continue;
    const name = cellAt(row, "name");
    const phone = cellAt(row, "phone");
    const dept = cellAt(row, "department");
    const position = cellAt(row, "position");
    if (!name) continue;
    if (nonEmpty.length === 1 && !phone && !position) { department = name.replace(/:$/, "").trim(); continue; }
    const warnings: string[] = [];
    const hod = HOD_WORDS.test(position) || (hodCol >= 0 && /^(hod|x|ano|yes|1|true)$/i.test(norm(row[hodCol])));
    const cleanedPosition = position.replace(/\s*[(\[]?\s*hod\s*[)\]]?\s*$/i, "").trim();
    let finalDept = dept || department;
    let finalPos = cleanedPosition;
    if (known.has(name.toLowerCase())) warnings.push("already on the crew");
    if (!finalDept) { finalDept = "General"; warnings.push("no department, using General"); }
    if (!finalPos) { finalPos = "Crew"; warnings.push("no position, using Crew"); }
    const phoneOk = phone && PHONE_LIKE.test(phone) && phone.replace(/\D/g, "").length >= 9;
    if (phone && !phoneOk) warnings.push(`phone "${phone}" does not look like a number, left out`);
    out.push({ line: i + 1, name, department: finalDept, position: finalPos, phone: phoneOk ? phone : null, hod, warning: warnings.length ? warnings.join("; ") : null });
  }
  return out;
}
