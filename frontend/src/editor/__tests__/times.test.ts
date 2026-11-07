import { describe, expect, it } from "vitest";
import { firstBadTime, isClockTime } from "../times";

describe("isClockTime", () => {
  it("accepts what the server accepts", () => {
    for (const ok of ["06:30", "00:00", "23:59", "6:30", "6.30", "6,30", "06,30", " 06:30 ", "", "   "]) expect(isClockTime(ok), ok).toBe(true);
  });
  it("refuses what the server refuses", () => {
    for (const bad of ["25:99", "abc", "24:00", "24,00", "12:60", "6", "06:3", "06:30:00", "06:30 pm", "TBD", "6;30"]) expect(isClockTime(bad), bad).toBe(false);
  });
});

describe("firstBadTime", () => {
  it("names the first field that is not a time, or nothing", () => {
    expect(firstBadTime([["Crew call", "06:30"], ["Sunrise", ""]])).toBeNull();
    expect(firstBadTime([["Crew call", "06:30"], ["Sunrise", "abc"], ["Sunset", "25:99"]])).toEqual({ field: "Sunrise", value: "abc" });
  });
});
