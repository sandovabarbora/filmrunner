import { describe, expect, it } from "vitest";
import { fmtDate, t } from "../i18n";

describe("t", () => {
  it("fills placeholders in both languages", () => {
    expect(t("en", "day.of", { n: 7, count: 24 })).toBe("Day 7 of 24");
    expect(t("cs", "day.of", { n: 7, count: 24 })).toBe("7. den z 24");
    expect(t("cs", "contacts.others", { n: 3 })).toBe("Ostatní oddělení (3)");
  });
  it("falls back to the English text, never a key, when Czech has no entry", () => {
    // simulate a hole: "th.ie" is identical in both, but a missing key must read as English
    expect(t("cs", "th.ie")).toBe("I/E");
    expect(t("cs", "rev.replaces", { rev: "B", prev: "A" })).toBe("REV B nahrazuje A");
  });
});

describe("fmtDate", () => {
  it("writes Czech and English dates with the weekday", () => {
    expect(fmtDate("cs", "2026-09-23")).toBe("st 23. 9. 2026");
    expect(fmtDate("en", "2026-09-23")).toBe("Wed 23 Sep 2026");
    expect(fmtDate("cs", "tbd")).toBe("tbd");
  });
});
