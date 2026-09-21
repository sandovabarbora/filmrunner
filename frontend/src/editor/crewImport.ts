/**
 * FR-31: paste the crew list. ADs already have the crew in a spreadsheet, a
 * WhatsApp message or last production's PDF; typing it in one by one is the
 * moment they give up. This parses the shapes people actually paste:
 *
 *   Camera:                              ← a department header (ends with ":")
 *   Jan Novák, DoP, 777 123 456          ← name, position, phone
 *   Petra K.	1st AC	+420 602 111 222   ← tab-separated (spreadsheet)
 *   Electric
 *   Tomáš Novák; Gaffer; HoD             ← "HoD" anywhere marks a head of department
 *   Eva Malá, Electric, Best boy         ← name, department, position (no header needed)
 *
 * Pure: no React, no network. The preview shows exactly what will be added.
 */

export interface ParsedCrewRow {
  line: number;
  name: string;
  department: string;
  position: string;
  phone: string | null;
  hod: boolean;
  /** Something the AD should glance at before importing; the row still imports. */
  warning: string | null;
}

const PHONE = /^\+?[\d\s().-]{9,}$/;
const HOD = /^(hod|head|vedoucí)$/i;

function splitFields(line: string): string[] {
  const sep = line.includes("\t") ? "\t" : line.includes(";") ? ";" : ",";
  return line.split(sep).map((f) => f.trim()).filter((f) => f !== "");
}

function isPhone(field: string): boolean {
  return PHONE.test(field) && field.replace(/\D/g, "").length >= 9;
}

export function parseCrewList(text: string, knownNames: Iterable<string> = []): ParsedCrewRow[] {
  const known = new Set([...knownNames].map((n) => n.trim().toLowerCase()));
  const rows: ParsedCrewRow[] = [];
  let department = "";
  text.split(/\r?\n/).forEach((raw, i) => {
    const line = raw.trim();
    if (line === "") return;
    const fields = splitFields(line);
    // A department header: one field, no phone, either "Camera:" or a known department word on its own.
    if (fields.length === 1 && !isPhone(fields[0]) && (line.endsWith(":") || looksLikeDepartment(line))) {
      department = line.replace(/:$/, "").trim();
      return;
    }
    const phone = fields.find(isPhone) ?? null;
    const hod = fields.some((f) => HOD.test(f));
    const rest = fields.filter((f) => f !== phone && !HOD.test(f));
    const name = rest[0] ?? "";
    let dept = department;
    let position = "";
    if (rest.length >= 3) { dept = rest[1]; position = rest.slice(2).join(", "); }
    else if (rest.length === 2) position = rest[1];
    const warnings: string[] = [];
    if (!name) return;
    if (known.has(name.toLowerCase())) warnings.push("already on the crew");
    if (!dept) { dept = "General"; warnings.push("no department, using General"); }
    if (!position) { position = "Crew"; warnings.push("no position, using Crew"); }
    rows.push({ line: i + 1, name, department: dept, position, phone, hod, warning: warnings.length ? warnings.join("; ") : null });
  });
  return rows;
}

const DEPARTMENTS = ["camera", "electric", "grip", "sound", "art", "costume", "makeup", "make-up", "hair", "production", "direction", "directing", "locations", "transport", "catering", "stunts", "vfx", "sfx", "script", "editorial", "post", "lighting", "kamera", "osvětlovači", "zvuk", "výprava", "kostýmy", "masky", "produkce", "režie", "lokace", "doprava"];

/** Bare single-word lines like "Camera" or "Electric" are headers; "Jan" between people is not. */
function looksLikeDepartment(line: string): boolean {
  const l = line.replace(/:$/, "").trim().toLowerCase();
  return DEPARTMENTS.includes(l) || DEPARTMENTS.some((d) => l.endsWith(` ${d}`) || l.startsWith(`${d} `));
}

/** Rows that will actually be created: duplicates of people already on the crew are skipped. */
export function importableRows(rows: ParsedCrewRow[]): ParsedCrewRow[] {
  return rows.filter((r) => !r.warning?.includes("already on the crew"));
}
