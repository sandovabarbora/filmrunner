import { describe, expect, it } from "vitest";
import { importableRows, parseCrewList } from "../crewImport";

describe("parseCrewList", () => {
  it("reads department headers, comma rows, tab rows and HoD markers", () => {
    const rows = parseCrewList([
      "Camera:",
      "Jan Novák, DoP, 777 123 456, HoD",
      "Petra K.\t1st AC\t+420 602 111 222",
      "Electric",
      "Tomáš Novák; Gaffer; hod",
      "Eva Malá, Art, Set dresser",
    ].join("\n"));
    expect(rows.map((r) => [r.name, r.department, r.position, r.phone, r.hod])).toEqual([
      ["Jan Novák", "Camera", "DoP", "777 123 456", true],
      ["Petra K.", "Camera", "1st AC", "+420 602 111 222", false],
      ["Tomáš Novák", "Electric", "Gaffer", null, true],
      ["Eva Malá", "Art", "Set dresser", null, false],
    ]);
    expect(rows.every((r) => r.warning === null)).toBe(true);
  });

  it("fills what is missing with a visible warning instead of dropping the person", () => {
    const rows = parseCrewList("Karel Dvořák\nSound:\nLenka, 608 000 111");
    expect(rows[0]).toMatchObject({ name: "Karel Dvořák", department: "General", position: "Crew" });
    expect(rows[0].warning).toContain("no department");
    expect(rows[0].warning).toContain("no position");
    expect(rows[1]).toMatchObject({ name: "Lenka", department: "Sound", position: "Crew", phone: "608 000 111" });
  });

  it("marks people already on the crew and leaves them out of the import", () => {
    const rows = parseCrewList("Camera:\nJan Novák, DoP\nNew Person, Loader", ["jan novák"]);
    expect(rows[0].warning).toBe("already on the crew");
    expect(importableRows(rows).map((r) => r.name)).toEqual(["New Person"]);
  });

  it("ignores blank lines and windows line endings", () => {
    expect(parseCrewList("\r\nGrip:\r\n\r\nOndra, Key grip\r\n")).toHaveLength(1);
  });

  it("does not mistake a lone first name for a department", () => {
    const rows = parseCrewList("Camera:\nJan Novák, DoP\nMarta\nPetr, Loader");
    expect(rows.map((r) => r.name)).toEqual(["Jan Novák", "Marta", "Petr"]);
    expect(rows[2].department).toBe("Camera");
  });
});
