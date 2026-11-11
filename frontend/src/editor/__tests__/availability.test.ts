import { describe, expect, it } from "vitest";
import { daysInRange, formatDays, splitIssues } from "../availability";

describe("FR-228 agreed days", () => {
  it("expands a range with both ends included, and one day when the end is empty", () => {
    expect(daysInRange("2026-12-30", "2027-01-02")).toEqual(["2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"]);
    expect(daysInRange("2026-12-14", "")).toEqual(["2026-12-14"]);
  });

  it("refuses a reversed or overlong range instead of guessing", () => {
    expect(daysInRange("2026-12-15", "2026-12-14")).toEqual([]);
    expect(daysInRange("2026-01-01", "2026-12-31")).toEqual([]);
    expect(daysInRange("", "2026-12-14")).toEqual([]);
  });

  it("writes days the way a Czech crew says them, and runs of three as a range", () => {
    expect(formatDays(["2026-12-15", "2026-12-14"], "cs")).toBe("14. 12., 15. 12.");
    expect(formatDays(["2026-12-14", "2026-12-15", "2026-12-16", "2026-12-20"], "cs")).toBe("14. 12.–16. 12., 20. 12.");
    expect(formatDays(["2026-12-14"], "en")).toBe("14 Dec");
  });

  it("never lets missing evidence pass for fine", () => {
    const base = { shoot_date: "2026-12-17", name: "Petr", character_name: "OTEC", agreed_days: [] };
    const { outside, notEntered } = splitIssues([{ ...base, cast_member_id: "a", status: "outside" }, { ...base, cast_member_id: "b", status: "not_entered" }]);
    expect(outside.map((i) => i.cast_member_id)).toEqual(["a"]);
    expect(notEntered.map((i) => i.cast_member_id)).toEqual(["b"]);
  });
});
