import { describe, expect, it } from "vitest";
import { nextRevisionLetter } from "../revisions";

describe("nextRevisionLetter", () => {
  it("steps through the alphabet", () => {
    expect(nextRevisionLetter("A")).toBe("B");
    expect(nextRevisionLetter("Y")).toBe("Z");
  });
  it("has nothing after Z rather than the character that follows it", () => {
    expect(nextRevisionLetter("Z")).toBeNull();
  });
});
