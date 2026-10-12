/**
 * FR-60/FR-61: filtering the crew list, and printing it for the production office.
 *
 * The print opens a plain document in a new window rather than reusing the app's print CSS:
 * the office wants names and numbers on paper, not the editor's chrome, and nothing personal
 * (no links, no tokens, no photos) may travel with it.
 */

import type { CastMember, CrewMember } from "../types";

/** A person matches when every word of the query appears in their name, department, position or phone digits. */
export function matchesCrew(m: CrewMember, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hay = `${m.contact.name} ${m.department} ${m.position}`.toLowerCase();
  const digits = (m.contact.phone ?? "").replace(/\D/g, "");
  return q.split(/\s+/).every((word) => {
    const wordDigits = word.replace(/\D/g, "");
    return hay.includes(word) || (wordDigits.length >= 2 && digits.includes(wordDigits));
  });
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** Crew by department (heads first), then cast; phones as typed, "—" when there is none. */
export function crewPrintHtml(crew: CrewMember[], cast: CastMember[], productionName: string, L: (s: string, v?: Record<string, string | number>) => string): string {
  const byDepartment = new Map<string, CrewMember[]>();
  for (const m of crew) {
    const list = byDepartment.get(m.department) ?? [];
    list.push(m);
    byDepartment.set(m.department, list);
  }
  const departments = [...byDepartment.entries()].sort(([a], [b]) => a.localeCompare(b, "cs"));
  for (const [, list] of departments) {
    list.sort((a, b) => Number(b.is_head_of_department) - Number(a.is_head_of_department) || a.contact.name.localeCompare(b.contact.name, "cs"));
  }
  const row = (cells: string[]) => `<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
  const crewHead = `<thead><tr><th scope="col">${escapeHtml(L("Name"))}</th><th scope="col">${escapeHtml(L("Position"))}</th><th scope="col">${escapeHtml(L("Phone"))}</th></tr></thead>`;
  const crewRows = departments
    .map(([dept, list]) => `<tr class="dept"><th colspan="3" scope="colgroup">${escapeHtml(dept)}</th></tr>` +
      list.map((m) => row([
        escapeHtml(m.contact.name) + (m.is_head_of_department ? ` <span class="hod">${escapeHtml(L("HoD"))}</span>` : ""),
        escapeHtml(m.position),
        m.contact.phone ? escapeHtml(m.contact.phone) : "—",
      ])).join(""))
    .join("");
  const castRows = cast
    .slice()
    .sort((a, b) => a.character_name.localeCompare(b.character_name, "cs"))
    .map((a) => row([escapeHtml(a.contact.name), escapeHtml(a.character_name), a.contact.phone ? escapeHtml(a.contact.phone) : "—"]))
    .join("");
  const title = `${productionName} · ${L("Crew list")}`;
  return `<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  :root { color-scheme: light }
  body { font: 10.5pt/1.25 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #17150f; margin: 16pt; }
  h1 { font-size: 14pt; margin: 0 0 2pt; }
  .meta { color: #55504a; font-size: 9pt; margin: 0 0 10pt; }
  caption.meta { text-align: left; caption-side: top; padding: 0; }
  h2 { font-size: 9pt; letter-spacing: .1em; text-transform: uppercase; color: #55504a; margin: 10pt 0 3pt; }
  table { width: 100%; border-collapse: collapse; }
  td, th { text-align: left; padding: 2pt 4pt; border-bottom: .5pt solid #d8d1c4; vertical-align: top; }
  tr.dept th { background: #efeae1; font-size: 9pt; letter-spacing: .08em; text-transform: uppercase; border-bottom: .8pt solid #17150f; }
  thead th { font-size: 8pt; letter-spacing: .05em; text-transform: uppercase; color: #55504a; border-bottom: .8pt solid #17150f; }
  tr, tr.dept { break-inside: avoid; }
  .hod { font-size: 8pt; border: .5pt solid #17150f; border-radius: 2pt; padding: 0 3pt; }
  td:last-child { white-space: nowrap; font-variant-numeric: tabular-nums; }
  @page { size: A4; margin: 12mm; }
</style></head><body>
<h1>${escapeHtml(productionName)}</h1>
<table><caption class="meta">${escapeHtml(L("Crew list"))} · ${escapeHtml(L("printed {when}", { when: new Date().toLocaleString() }))}</caption>${crewHead}<tbody>${crewRows}</tbody></table>
${cast.length ? `<h2>${escapeHtml(L("Cast"))}</h2><table>${castRows}</table>` : ""}
</body></html>`;
}

/**
 * Opens the print view in a new tab and raises the print dialog once it has rendered.
 * A blob URL rather than `document.write`: the new document then needs no handle back into
 * this one, so the tab can be opened with `noopener` and prints itself from its own onload.
 */
export function crewPrintWindow(crew: CrewMember[], cast: CastMember[], productionName: string, L: (s: string, v?: Record<string, string | number>) => string): Window | null {
  const html = crewPrintHtml(crew, cast, productionName, L).replace("<body>", '<body onload="window.print()">');
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const w = window.open(url, "_blank", "noopener");
  // The blob stays alive for the new document; revoking after a beat keeps this page from leaking it.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return w;
}
