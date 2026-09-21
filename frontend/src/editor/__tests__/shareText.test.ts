import { describe, expect, it } from "vitest";
import { allLinksText, daySummaryText, humanDate, onboardingMessageText, personalCallFor, personalMessageText, whatsappNumber, whatsappUrl, type DayFacts } from "../shareText";
import type { CrewMember, Location } from "../../types";

const day: DayFacts = {
  productionName: "Noc na Karlštejně",
  shoot_date: "2026-09-23",
  day_number: 3,
  day_count: 12,
  unit_name: "Main Unit",
  general_crew_call: "06:00",
  shooting_call: "07:30",
  sunrise: "06:41",
  sunset: "18:59",
  weather_forecast: "14 °C, light rain",
  safety_notes: "Wet cobbles in the courtyard",
  items: [
    { order_index: 2, scene_number: "12A", int_ext: "INT", day_night: "DAY", set_description: "Great hall", location_id: null, page_count_eighths: 8 },
    { order_index: 1, scene_number: "7", int_ext: "EXT", day_night: "DAY", set_description: "Courtyard", location_id: "loc-1", page_count_eighths: 12 },
  ],
  crewCalls: { "cm-gaffer": { call: "05:15", pickup: "04:45", note: "Bring the 4K" } },
  lastPublishedLetter: "B",
};

const locations: Location[] = [
  { id: "loc-1", production_id: "p", name: "Karlštejn Castle", address: "Karlštejn 172", parking_notes: "Lower car park", nearest_hospital: null, geo_lat: null, geo_lng: null, geocoded_display_name: null },
];

function member(id: string, name: string, phone: string | null, standing: string | null = null): CrewMember {
  return {
    id, production_id: "p", contact_id: `c-${id}`, department: "Lighting", position: "Gaffer", standard_call_time: standing, is_head_of_department: false,
    personal_token: `tok-${id}`, contact: { id: `c-${id}`, name, phone, email: null, photo_url: null } as CrewMember["contact"],
  };
}

describe("humanDate", () => {
  it("names the weekday", () => expect(humanDate("2026-09-23")).toBe("Wed 23 Sep 2026"));
  it("passes through what it cannot parse", () => expect(humanDate("soon")).toBe("soon"));
});

describe("daySummaryText", () => {
  const text = daySummaryText(day, locations, "https://x/?sheet=1");
  it("leads with the production, day and revision", () => {
    expect(text.split("\n")[0]).toBe("*Noc na Karlštejně · Day 3 of 12 · REV B*");
    expect(text.split("\n")[1]).toBe("Wed 23 Sep 2026 · Main Unit");
  });
  it("uses the first scheduled location by order, not by array position", () => {
    expect(text).toContain("Location: Karlštejn Castle, Karlštejn 172");
    expect(text).toContain("Parking: Lower car park");
  });
  it("lists the schedule in order and ends with the link", () => {
    expect(text.indexOf("1. Sc 7 EXT/DAY – Courtyard")).toBeLessThan(text.indexOf("2. Sc 12A INT/DAY – Great hall"));
    expect(text.trimEnd().endsWith("https://x/?sheet=1")).toBe(true);
  });
  it("leaves out empty facts instead of printing blanks", () => {
    const bare = daySummaryText({ ...day, weather_forecast: "", sunrise: "", sunset: "", safety_notes: "", items: [] }, [], "https://x/");
    expect(bare).not.toContain("Weather");
    expect(bare).not.toContain("Sun:");
    expect(bare).not.toContain("Schedule");
    expect(bare).not.toContain("Location");
  });
});

describe("personalCallFor", () => {
  it("prefers the day's entry, then the standing time, then the crew call", () => {
    expect(personalCallFor(day, member("cm-gaffer", "Tomáš Novák", null, "05:30")).call).toBe("05:15");
    expect(personalCallFor(day, member("cm-grip", "Eva", null, "05:30")).call).toBe("05:30");
    expect(personalCallFor(day, member("cm-pa", "Jan", null)).call).toBe("06:00");
  });
});

describe("personalMessageText", () => {
  it("greets by first name and carries the day's own call, pickup and note", () => {
    const text = personalMessageText(day, member("cm-gaffer", "Tomáš Novák", "+420 777 123 456"), locations, "https://x/?me=t");
    expect(text.startsWith("Hi Tomáš,")).toBe(true);
    expect(text).toContain("Your call: *05:15*");
    expect(text).toContain("Pickup: 04:45");
    expect(text).toContain("Note: Bring the 4K");
    expect(text.trimEnd().endsWith("https://x/?me=t")).toBe(true);
  });
});

describe("whatsappNumber", () => {
  it("normalises Czech numbers in every way people type them", () => {
    expect(whatsappNumber("+420 777 123 456")).toBe("420777123456");
    expect(whatsappNumber("777 123 456")).toBe("420777123456");
    expect(whatsappNumber("00420777123456")).toBe("420777123456");
    expect(whatsappNumber("(777) 123-456")).toBe("420777123456");
  });
  it("keeps other international numbers", () => expect(whatsappNumber("+49 30 1234567")).toBe("49301234567"));
  it("refuses what cannot be a wa.me number", () => {
    expect(whatsappNumber(null)).toBeNull();
    expect(whatsappNumber("")).toBeNull();
    expect(whatsappNumber("ask Petra")).toBeNull();
    expect(whatsappNumber("12345")).toBeNull();
    expect(whatsappNumber("+420 777 123 456 ext 2")).toBeNull();
  });
});

describe("whatsappUrl", () => {
  it("targets the chat when there is a number and WhatsApp's chooser when there is not", () => {
    expect(whatsappUrl("420777123456", "Hi *there*")).toBe("https://wa.me/420777123456?text=Hi%20*there*");
    expect(whatsappUrl(null, "x")).toBe("https://wa.me/?text=x");
  });
});

describe("onboardingMessageText / allLinksText", () => {
  const m = member("cm-1", "Tomáš Novák", "+420 777 123 456");
  it("greets by first name, names the production and ends with the link", () => {
    const text = onboardingMessageText("Noc na Karlštejně", m, "https://x/?me=t");
    expect(text.startsWith("Hi Tomáš, here is your call sheet link for *Noc na Karlštejně*:\nhttps://x/?me=t")).toBe(true);
    expect(onboardingMessageText(null, m, "https://x/?me=t")).toContain("your call sheet link:\n");
  });
  it("lists one person per line with their department", () => {
    expect(allLinksText([m, member("cm-2", "Eva", null)], (x) => `L-${x.id}`)).toBe("Tomáš Novák · Lighting: L-cm-1\nEva · Lighting: L-cm-2");
  });
});
