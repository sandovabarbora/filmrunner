import { describe, expect, it } from "vitest";
import { detectScheduleColumns, locationNames, parseDate, parseEighths, rowsToSchedule } from "../scheduleImport";

describe("parsers", () => {
  it("pages in every notation", () => {
    expect(["2 3/8", "3/8", "2", "1.5", "19/8", "", "abc"].map(parseEighths)).toEqual([19, 3, 16, 12, 19, 0, 0]);
  });
  it("dates as spreadsheets and Movie Magic write them", () => {
    expect(parseDate("2026-09-23")).toBe("2026-09-23");
    expect(parseDate("23.9.2026")).toBe("2026-09-23");
    expect(parseDate("23. 9. 2026")).toBe("2026-09-23");
    expect(parseDate("9/23/2026")).toBe("2026-09-23");   // US, from Movie Magic
    expect(parseDate("23/09/2026")).toBe("2026-09-23");  // day first when it cannot be a month
    expect(parseDate("Wed, Sep 23, 2026")).toBe("2026-09-23");
    expect(parseDate("23 září 2026")).toBe("2026-09-23");
    expect(parseDate("tbd")).toBeNull();
  });
});

describe("detectScheduleColumns", () => {
  it("reads a Czech AD's sheet and a Movie Magic export", () => {
    expect(detectScheduleColumns([["Harmonogram"], ["Den", "Datum", "Obraz", "Int/Ext", "D/N", "Motiv", "Str.", "Lokace", "Herci"]]))
      .toEqual({ headerIndex: 1, map: { day: 0, date: 1, scene: 2, int_ext: 3, day_night: 4, set: 5, pages: 6, location: 7, cast: 8 } });
    expect(detectScheduleColumns([["Sheet #", "Scene", "INT/EXT", "Set", "D/N", "Pages", "Cast ID", "Location"]]))
      .toEqual({ headerIndex: 0, map: { scene: 1, int_ext: 2, set: 3, day_night: 4, pages: 5, cast: 6, location: 7 } });
    expect(detectScheduleColumns([["Name", "Phone"]])).toBeNull();
  });
});

describe("rowsToSchedule", () => {
  it("groups by a day column, keeps scene order and reads every field", () => {
    const rows = [
      ["Den", "Datum", "Obraz", "Int/Ext", "D/N", "Motiv", "Str.", "Lokace", "Herci"],
      [1, "23.9.2026", "42", "EXT", "DEN", "NÁBŘEŽÍ", "1 6/8", "Troja", "Anna Geislerová, Jiří Mádl"],
      [1, "23.9.2026", "43", "ext", "D", "NÁBŘEŽÍ – loď", "6/8", "Troja", "Jiří Mádl"],
      [2, "24.9.2026", "17", "INT", "NOC", "CHALUPA – kuchyň", "2", "Chalupa Sedlec", ""],
    ];
    const days = rowsToSchedule(rows, 0, detectScheduleColumns(rows)!.map);
    expect(days.map((d) => [d.day_number, d.shoot_date, d.scenes.length])).toEqual([[1, "2026-09-23", 2], [2, "2026-09-24", 1]]);
    expect(days[0].scenes[0]).toEqual({ scene_number: "42", int_ext: "EXT", day_night: "DAY", set_description: "NÁBŘEŽÍ", page_count_eighths: 14, location: "Troja", cast: ["Anna Geislerová", "Jiří Mádl"] });
    expect(days[1].scenes[0].day_night).toBe("NIGHT");
    expect(days[1].scenes[0].page_count_eighths).toBe(16);
    expect(locationNames(days)).toEqual(["Troja", "Chalupa Sedlec"]);
    expect(days.every((d) => d.warnings.length === 0)).toBe(true);
  });

  it("reads Movie Magic banner rows: scenes above an 'End of Day N' belong to it", () => {
    const rows = [
      ["Sheet #", "Scene", "INT/EXT", "Set", "D/N", "Pages", "Cast ID", "Location"],
      [1, "42", "EXT", "RIVERBANK", "Day", "1 6/8", "1, 2", "Troja"],
      [2, "43", "EXT", "RIVERBANK", "Day", "6/8", "2", "Troja"],
      ["End of Day 1 -- Wed, Sep 23, 2026 -- 2 4/8 Total Pages"],
      [3, "17", "INT", "COTTAGE KITCHEN", "Night", "2", "1", "Sedlec"],
      ["End of Day 2 -- Thu, Sep 24, 2026 -- 2 Total Pages"],
    ];
    const days = rowsToSchedule(rows, 0, detectScheduleColumns(rows)!.map);
    expect(days.map((d) => [d.day_number, d.shoot_date, d.scenes.map((s) => s.scene_number)])).toEqual([[1, "2026-09-23", ["42", "43"]], [2, "2026-09-24", ["17"]]]);
  });

  it("groups by date alone, numbering days in date order", () => {
    const rows = [["Date", "Scene", "Set"], ["24.9.2026", "17", "KITCHEN"], ["23.9.2026", "42", "RIVER"], ["23.9.2026", "43", "RIVER"]];
    const days = rowsToSchedule(rows, 0, detectScheduleColumns(rows)!.map);
    expect(days.map((d) => [d.day_number, d.shoot_date, d.scenes.length])).toEqual([[1, "2026-09-23", 2], [2, "2026-09-24", 1]]);
  });

  it("failure case: scenes with no day information become one undated day with a warning", () => {
    const rows = [["Scene", "Set"], ["1", "A"], ["2", "B"]];
    const days = rowsToSchedule(rows, 0, detectScheduleColumns(rows)!.map);
    expect(days).toHaveLength(1);
    expect(days[0]).toMatchObject({ day_number: null, shoot_date: null });
    expect(days[0].scenes).toHaveLength(2);
    expect(days[0].warnings[0]).toContain("Imported schedule");
  });
});
