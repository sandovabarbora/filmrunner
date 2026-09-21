import { describe, expect, it } from "vitest";
import { addDays, draftHasContent, emptyDraft, nextDayFrom, type Draft } from "../drafts";

describe("addDays", () => {
  it("crosses month ends and DST switches by calendar day", () => {
    expect(addDays("2026-09-30", 1)).toBe("2026-10-01");
    expect(addDays("2026-10-24", 1)).toBe("2026-10-25");  // the night the clocks go back in Prague
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });
  it("passes through what it cannot parse", () => expect(addDays("tbd", 1)).toBe("tbd"));
});

describe("nextDayFrom", () => {
  const today: Draft = {
    ...emptyDraft("p1", "Noc"), callSheetId: "cs-1", lastPublishedLetter: "B", dirtySincePublish: false,
    shoot_date: "2026-09-23", day_number: 3, day_count: 3, unit_name: "2nd Unit",
    general_crew_call: "06:30", shooting_call: "08:00", sunrise: "06:41", sunset: "18:59", weather_forecast: "Rain", safety_notes: "Stairs",
    headOfDayId: "cm-ad",
    items: [{ order_index: 1, scene_number: "7", int_ext: "EXT", day_night: "DAY", set_description: "Courtyard", location_id: "loc-1", page_count_eighths: 8 }],
    crewCalls: { "cm-gaffer": { call: "05:15", pickup: "04:45", note: "" } },
  };
  const tomorrow = nextDayFrom(today);
  it("is an unpublished new day one date on, continuing the numbering", () => {
    expect(tomorrow.callSheetId).toBeNull();
    expect(tomorrow.lastPublishedLetter).toBeNull();
    expect(tomorrow.id).toBe("new:p1");
    expect(tomorrow.shoot_date).toBe("2026-09-24");
    expect(tomorrow.day_number).toBe(4);
    expect(tomorrow.day_count).toBe(4);  // stretched so day 4 of 3 never appears
  });
  it("keeps what repeats and drops what belongs to the date", () => {
    expect(tomorrow.unit_name).toBe("2nd Unit");
    expect(tomorrow.general_crew_call).toBe("06:30");
    expect(tomorrow.headOfDayId).toBe("cm-ad");
    expect(tomorrow.items).toEqual(today.items);
    expect(tomorrow.crewCalls).toEqual(today.crewCalls);
    expect(tomorrow.weather_forecast).toBe("");
    expect(tomorrow.sunrise).toBe("");
  });
  it("copies, not shares, the nested objects", () => {
    tomorrow.items[0].scene_number = "8";
    tomorrow.crewCalls["cm-gaffer"].call = "06:00";
    expect(today.items[0].scene_number).toBe("7");
    expect(today.crewCalls["cm-gaffer"].call).toBe("05:15");
  });
});

describe("draftHasContent", () => {
  it("is false for an untouched draft and true once anything is typed", () => {
    expect(draftHasContent(null)).toBe(false);
    expect(draftHasContent(emptyDraft("p", null))).toBe(false);
    expect(draftHasContent({ ...emptyDraft("p", null), general_crew_call: "06:00" })).toBe(true);
  });
});
