/** FR-226: a removed scene can come back where it was, with every field, until the next removal replaces it. */
import type { Draft } from "./drafts";

export interface RemovedScene {
  item: Draft["items"][number];
  index: number;
  wasDirty: boolean;
  /** The draft right after the removal: if it is still the current one, nothing else changed in between. */
  after: Draft;
}

export function removeScene(draft: Draft, index: number): { draft: Draft; removed: RemovedScene } {
  const next = { ...draft, items: draft.items.filter((_, j) => j !== index), dirtySincePublish: !!draft.callSheetId };
  return { draft: next, removed: { item: draft.items[index], index, wasDirty: draft.dirtySincePublish, after: next } };
}

export function restoreScene(draft: Draft, removed: RemovedScene): Draft {
  const at = Math.min(removed.index, draft.items.length);
  const items = [...draft.items.slice(0, at), removed.item, ...draft.items.slice(at)];
  // Undoing the only change since the last publish leaves nothing to publish.
  const dirtySincePublish = draft === removed.after ? removed.wasDirty : draft.dirtySincePublish;
  return { ...draft, items, dirtySincePublish };
}
