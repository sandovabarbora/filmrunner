import { describe, expect, it } from "vitest";
import { emptyDraft, type Draft } from "../drafts";
import { removeScene, restoreScene } from "../sceneUndo";

const scene = (n: string, i: number) => ({ order_index: i, scene_number: n, int_ext: "EXT" as const, day_night: "NIGHT" as const, set_description: `Set ${n}`, location_id: `loc-${n}`, page_count_eighths: 3 + i });
const published: Draft = { ...emptyDraft("p1", "Noc"), callSheetId: "cs-1", lastPublishedLetter: "A", dirtySincePublish: false, items: [scene("41", 1), scene("42", 2), scene("43", 3)] };

describe("removeScene and restoreScene", () => {
  it("puts the scene back at the same index with every field", () => {
    const { draft, removed } = removeScene(published, 1);
    expect(draft.items.map((it) => it.scene_number)).toEqual(["41", "43"]);
    expect(restoreScene(draft, removed).items).toEqual(published.items);
  });

  it("restores the first and the last scene in place", () => {
    for (const index of [0, 2]) {
      const { draft, removed } = removeScene(published, index);
      expect(restoreScene(draft, removed).items).toEqual(published.items);
    }
  });

  it("goes last when the list got shorter in between", () => {
    const { draft, removed } = removeScene(published, 2);
    const shorter = { ...draft, items: draft.items.slice(0, 1) };
    expect(restoreScene(shorter, removed).items.map((it) => it.scene_number)).toEqual(["41", "43"]);
  });

  it("leaves nothing to publish when the removal was the only change", () => {
    const { draft, removed } = removeScene(published, 0);
    expect(draft.dirtySincePublish).toBe(true);
    expect(restoreScene(draft, removed).dirtySincePublish).toBe(false);
  });

  it("keeps other edits made after the removal unpublished", () => {
    const { draft, removed } = removeScene(published, 0);
    const edited = { ...draft, safety_notes: "Ice" };
    const back = restoreScene(edited, removed);
    expect(back.dirtySincePublish).toBe(true);
    expect(back.safety_notes).toBe("Ice");
  });

  it("does not touch the draft it was given", () => {
    const { draft, removed } = removeScene(published, 1);
    restoreScene(draft, removed);
    expect(published.items).toHaveLength(3);
    expect(draft.items).toHaveLength(2);
  });
});
