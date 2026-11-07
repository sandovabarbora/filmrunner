import { afterEach, describe, expect, it, vi } from "vitest";
import { emptyDraft } from "../drafts";
import { pragueToday } from "../pragueDate";

afterEach(() => vi.useRealTimers());

describe("pragueToday", () => {
  it("is Prague's date whatever the browser's zone or UTC say", () => {
    expect(pragueToday(new Date("2026-11-09T22:59:00Z"))).toBe("2026-11-09");
    expect(pragueToday(new Date("2026-11-09T23:30:00Z"))).toBe("2026-11-10");  // winter, +1
    expect(pragueToday(new Date("2026-07-01T22:30:00Z"))).toBe("2026-07-02");  // summer, +2
    expect(pragueToday(new Date("2026-07-01T21:30:00Z"))).toBe("2026-07-01");
  });
});

describe("a new day", () => {
  it("defaults to Prague's today just after midnight, when UTC is still on yesterday", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-09T23:30:00Z"));
    expect(emptyDraft("p", null).shoot_date).toBe("2026-11-10");
  });
});
