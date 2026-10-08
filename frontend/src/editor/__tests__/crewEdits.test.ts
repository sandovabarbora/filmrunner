import { describe, expect, it } from "vitest";
import { type CrewEditableFields, diffCrewEditFields, mergeCrewEdit } from "../crewEdits";

const baseline: CrewEditableFields = {
  name: "Jana Novakova", phone: "+420600111222",
  department: "Grip", position: "Key Grip",
  standard_call_time: "06:00", is_head_of_department: true,
};

// Mirrors the backend's PATCH semantics (`exclude_unset=True`): applying a
// patch twice, one after the other, is how two devices sync one after the
// other against the one real server record.
function syncSequence(start: CrewEditableFields, ...patches: Partial<CrewEditableFields>[]): CrewEditableFields {
  return patches.reduce<CrewEditableFields>((state, patch) => mergeCrewEdit(state, patch), start);
}

describe("FR-144: two devices queuing conflicting offline edits to the same crew member", () => {
  it("same field, two different values: the second sync's value wins, not a silent partial merge", () => {
    const deviceA = diffCrewEditFields(baseline, { ...baseline, standard_call_time: "05:30" });
    const deviceB = diffCrewEditFields(baseline, { ...baseline, standard_call_time: "07:00" });
    const result = syncSequence(baseline, deviceA, deviceB);
    expect(result.standard_call_time).toBe("07:00"); // the second (B's) value, not A's, not a blend
    // nothing else on the record moved
    expect(result).toEqual({ ...baseline, standard_call_time: "07:00" });
  });

  it("different fields: the first device's already-synced change survives the second device's later sync (failure case)", () => {
    // Device A, offline, changes only the phone number.
    const deviceA = diffCrewEditFields(baseline, { ...baseline, phone: "+420600999888" });
    // Device B queued its edit from the SAME stale baseline (before A's change ever reached it),
    // and only touched department — its snapshot of phone is still the old one, but diffCrewEditFields
    // means that old phone value is never part of B's patch at all.
    const deviceB = diffCrewEditFields(baseline, { ...baseline, department: "Best Boy Grip" });
    expect(deviceA).toEqual({ phone: "+420600999888" });
    expect(deviceB).toEqual({ department: "Best Boy Grip" });

    const result = syncSequence(baseline, deviceA, deviceB);
    // Both changes land; B syncing second does not revert A's phone update to the stale baseline value,
    // because B's patch never carried a phone field in the first place.
    expect(result.phone).toBe("+420600999888");
    expect(result.department).toBe("Best Boy Grip");
    expect(result.name).toBe(baseline.name);
    expect(result.standard_call_time).toBe(baseline.standard_call_time);
  });

  it("an edit that changes nothing produces an empty patch, so a no-op sync sends nothing and swallows no error", () => {
    expect(diffCrewEditFields(baseline, { ...baseline })).toEqual({});
  });

  it("a second offline edit before the first syncs merges onto the earlier patch instead of replacing it", () => {
    // First offline edit: phone only.
    const first = diffCrewEditFields(baseline, { ...baseline, phone: "+420600999888" });
    // User edits again before reconnecting, this time changing only the department; the app diffs
    // against the server's last-known copy (still `baseline`, since nothing has synced yet) and
    // merges onto the pending patch rather than discarding the phone change.
    const second = diffCrewEditFields(baseline, { ...baseline, department: "Best Boy Grip" });
    const merged = { ...first, ...second };
    expect(merged).toEqual({ phone: "+420600999888", department: "Best Boy Grip" });
  });
});
