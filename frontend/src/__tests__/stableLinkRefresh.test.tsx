// @vitest-environment jsdom
/**
 * FR-222 review: a refresh still in flight when the page moves to another day must not show the old day,
 * or send its read receipt, after the move.
 */
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CallSheet, CrewNextDay } from "../types";

vi.mock("../loader", async () => {
  const actual = await vi.importActual<typeof import("../loader")>("../loader");
  return { ...actual, loadNextDay: vi.fn(), loadCallSheet: vi.fn(), loadPersonal: vi.fn(), markSeen: vi.fn() };
});

import { App } from "../App";
import { loadCallSheet, loadNextDay, loadPersonal, markSeen, type LoadResult } from "../loader";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

const next = (id: string): CrewNextDay => ({ production_name: "P", crew_member_name: "Jana", call_sheet_id: id, days: [] });
const sheet = (id: string): LoadResult => ({ kind: "live", data: { id, status: "published", day_number: id === "night" ? 1 : 2, day_count: 2, shoot_date: "2099-01-05", unit_name: "Main", current_revision: null } as unknown as CallSheet });
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const refresh = () => act(async () => { document.dispatchEvent(new Event("visibilitychange")); });

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("an open stable link that moves to another day", () => {
  it("drops what an older refresh brings back after the move", async () => {
    window.history.replaceState(null, "", "/?api=http://localhost:8000&me=tok");
    vi.mocked(loadPersonal).mockResolvedValue({ kind: "unreachable" });
    vi.mocked(loadNextDay).mockResolvedValueOnce({ live: true, data: next("night") });
    vi.mocked(loadCallSheet).mockResolvedValueOnce(sheet("night"));
    render(<App />);
    await flush();
    expect(vi.mocked(markSeen).mock.calls.map((c) => c[1])).toEqual(["night"]);

    // Refresh A gets as far as reloading the night's sheet, which is slow to answer.
    const slowNight = deferred<LoadResult>();
    vi.mocked(loadNextDay).mockResolvedValueOnce({ live: true, data: next("night") });
    vi.mocked(loadCallSheet).mockReturnValueOnce(slowNight.promise);
    await refresh();
    await flush();

    // Refresh B hears the server has moved on, and the page moves; the morning's sheet is still loading.
    const slowMorning = deferred<LoadResult>();
    vi.mocked(loadNextDay).mockResolvedValueOnce({ live: true, data: next("morning") });
    vi.mocked(loadCallSheet).mockReturnValueOnce(slowMorning.promise);
    await refresh();
    await flush();

    await act(async () => { slowNight.resolve(sheet("night")); });
    await flush();
    expect(vi.mocked(markSeen).mock.calls.map((c) => c[1])).toEqual(["night"]);

    await act(async () => { slowMorning.resolve(sheet("morning")); });
    await flush();
    expect(vi.mocked(markSeen).mock.calls.map((c) => c[1])).toEqual(["night", "morning"]);
  });
});
