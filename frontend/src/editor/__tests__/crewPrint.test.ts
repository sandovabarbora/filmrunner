import { describe, expect, it } from "vitest";
import { crewPrintHtml, matchesCrew } from "../crewPrint";
import type { CastMember, CrewMember } from "../../types";

const L = (s: string, v: Record<string, string | number> = {}) => s.replace(/\{(\w+)\}/g, (_, k) => String(v[k] ?? ""));

function crew(name: string, department: string, position: string, phone: string | null, hod = false): CrewMember {
  return { id: name, production_id: "p", contact_id: `c-${name}`, department, position, standard_call_time: null, is_head_of_department: hod,
    personal_token: `tok-${name}`, contact: { id: `c-${name}`, name, phone, email: null, photo_url: null } } as CrewMember;
}

describe("matchesCrew", () => {
  const gaffer = crew("Tomáš Novák", "Electric", "Gaffer", "+420 777 123 456");
  it("matches on any field, case-insensitively, all words required", () => {
    expect(matchesCrew(gaffer, "")).toBe(true);
    expect(matchesCrew(gaffer, "nov")).toBe(true);
    expect(matchesCrew(gaffer, "electric")).toBe(true);
    expect(matchesCrew(gaffer, "gaf")).toBe(true);
    expect(matchesCrew(gaffer, "electric gaffer")).toBe(true);
    expect(matchesCrew(gaffer, "electric camera")).toBe(false);
  });
  it("matches phone digits however the number is written", () => {
    expect(matchesCrew(gaffer, "777123")).toBe(true);
    expect(matchesCrew(gaffer, "777 123")).toBe(true);
    expect(matchesCrew(crew("Eva", "Camera", "AC", null), "777")).toBe(false);
  });
});

describe("crewPrintHtml", () => {
  const people = [
    crew("Petra Králová", "Camera", "1st AC", "602 111 222"),
    crew("Marek Sýkora", "Camera", "DoP", "603 555 010", true),
    crew("Bez Čísla", "Electric", "Best boy", null),
  ];
  const cast = [{ id: "a", production_id: "p", contact_id: "ca", character_name: "MARTA", standard_pickup_time: null,
    contact: { id: "ca", name: "Anna Geislerová", phone: "608 000 111", email: null, photo_url: null } } as CastMember];
  const html = crewPrintHtml(people, cast, "Noc na Karlštejně", L);
  it("groups by department with the head first and the cast in its own block", () => {
    expect(html.indexOf("Camera")).toBeLessThan(html.indexOf("Marek Sýkora"));
    expect(html.indexOf("Marek Sýkora")).toBeLessThan(html.indexOf("Petra Králová"));  // HoD first
    expect(html.indexOf("Electric")).toBeLessThan(html.indexOf("Bez Čísla"));
    expect(html).toContain("MARTA");
    expect(html).toContain("Noc na Karlštejně");
  });
  it("prints an em dash for a missing number, never an empty cell", () => {
    expect(html).toContain("<td>—</td>");
  });
  it("carries nothing personal: no links, no tokens, no photos", () => {
    expect(html).not.toContain("tok-");
    expect(html).not.toContain("http");
    expect(html).not.toContain("<img");
  });
  it("escapes what the AD typed", () => {
    const nasty = crewPrintHtml([crew('<script>alert(1)</script>', "Art", "Set", null)], [], "P & Q", L);
    expect(nasty).not.toContain("<script>alert");
    expect(nasty).toContain("&lt;script&gt;");
    expect(nasty).toContain("P &amp; Q");
  });
});
