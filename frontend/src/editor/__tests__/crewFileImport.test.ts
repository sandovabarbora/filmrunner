import { describe, expect, it } from "vitest";
import { columnLetter, detectColumns, rowsToCrew } from "../crewFileImport";

describe("detectColumns", () => {
  it("finds Czech headers in any order, skipping a title row", () => {
    const rows = [["Štáb – Noc na Karlštejně"], [], ["Pozice", "Jméno a příjmení", "Telefon", "Oddělení", "HoD"]];
    expect(detectColumns(rows)).toEqual({ headerIndex: 2, map: { position: 0, name: 1, phone: 2, department: 3 } });
  });
  it("finds English headers and ignores unknown columns", () => {
    expect(detectColumns([["#", "Name", "Dept", "Job title", "Mobile", "Notes"]])).toEqual({ headerIndex: 0, map: { name: 1, department: 2, position: 3, phone: 4 } });
  });
  it("refuses a sheet with no name column", () => {
    expect(detectColumns([["Telefon", "Pozice"], ["777 123 456", "Gaffer"]])).toBeNull();
  });
  it("letters columns for the mapping row", () => {
    expect([0, 1, 25, 26, 27].map(columnLetter)).toEqual(["A", "B", "Z", "AA", "AB"]);
  });
});

describe("rowsToCrew", () => {
  const header = ["Jméno", "Telefon", "Oddělení", "Pozice", "HoD"];
  it("turns rows into people, with a department column and an HoD mark", () => {
    const rows = [header,
      ["Jan Novák", "+420 777 123 456", "Camera", "DoP", "x"],
      ["Petra K.", 602111222, "Camera", "1st AC", ""],
      ["", "", "", "", ""],
      ["Tomáš Novák", "", "Electric", "Gaffer (HoD)", ""],
    ];
    const out = rowsToCrew(rows, 0, detectColumns(rows)!.map);
    expect(out.map((r) => [r.name, r.department, r.position, r.phone, r.hod])).toEqual([
      ["Jan Novák", "Camera", "DoP", "+420 777 123 456", true],
      ["Petra K.", "Camera", "1st AC", "602111222", false],
      ["Tomáš Novák", "Electric", "Gaffer", null, true],
    ]);
    expect(out.every((r) => r.warning === null)).toBe(true);
  });
  it("uses department header rows (name only) when there is no department column", () => {
    const rows = [["Name", "Phone", "Position"], ["Camera:"], ["Jan Novák", "777 123 456", "DoP"], ["Electric"], ["Tomáš Novák", "", "Gaffer"]];
    const out = rowsToCrew(rows, 0, detectColumns(rows)!.map);
    expect(out.map((r) => [r.name, r.department])).toEqual([["Jan Novák", "Camera"], ["Tomáš Novák", "Electric"]]);
  });
  it("warns instead of dropping: missing fields, an odd phone, someone already on the crew", () => {
    const rows = [["Name", "Phone"], ["Karel", "ask Petra"], ["Jan Novák", "777 123 456"]];
    const out = rowsToCrew(rows, 0, detectColumns(rows)!.map, ["jan novák"]);
    expect(out[0]).toMatchObject({ name: "Karel", department: "General", position: "Crew", phone: null });
    expect(out[0].warning).toContain("does not look like a number");
    expect(out[1].warning).toContain("already on the crew");
  });
});
