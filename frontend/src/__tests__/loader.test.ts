// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cacheCallSheet, getCachedCallSheet } from "../cache";
import { loadCallSheet, loadNextDay, loadPersonal } from "../loader";
import type { CallSheet, PersonalSheet } from "../types";

vi.mock("../cache", () => ({ cacheCallSheet: vi.fn(), getCachedCallSheet: vi.fn() }));

const SHEET = { unit_name: "U", current_revision: { revision_letter: "B" } } as CallSheet;
const PERSON = { name: "Petr", department: "Electric", position: "Best boy" } as PersonalSheet;
const SAVED_AT = "2026-11-05T18:00:00.000Z";

function answer(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers }));
}

function controlledBy(worker: object | null) {
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { controller: worker } });
}

beforeEach(() => {
  localStorage.clear();
  controlledBy(null);
  vi.mocked(getCachedCallSheet).mockReset().mockResolvedValue(null);
  vi.mocked(cacheCallSheet).mockReset().mockResolvedValue();
});

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("loadCallSheet freshness", () => {
  it("counts an unstamped answer as live when no worker controlled the page as it was sent, even if one does by the answer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => {
      controlledBy({});
      return new Response(JSON.stringify(SHEET));
    }));
    expect((await loadCallSheet("u", "id")).kind).toBe("live");
  });

  it("stays unknown when a worker controlled the page as it was sent and left no stamp", async () => {
    controlledBy({});
    vi.stubGlobal("fetch", answer(SHEET));
    expect((await loadCallSheet("u", "id")).kind).toBe("unknown");
  });

  it("does not re-date a copy the worker answered from its cache", async () => {
    controlledBy({});
    vi.stubGlobal("fetch", answer(SHEET, 200, { "x-filmrunner-source": "cache", "x-filmrunner-fetched-at": SAVED_AT }));
    expect(await loadCallSheet("u", "id")).toMatchObject({ kind: "cached", fetchedAt: SAVED_AT });
    expect(cacheCallSheet).not.toHaveBeenCalled();
  });

  it("still shows the sheet when the phone's storage refuses", async () => {
    vi.mocked(getCachedCallSheet).mockRejectedValue(new Error("blocked"));
    vi.mocked(cacheCallSheet).mockRejectedValue(new Error("blocked"));
    vi.stubGlobal("fetch", answer(SHEET));
    expect((await loadCallSheet("u", "id")).kind).toBe("live");
  });

  it("ends in an error rather than hanging when the request fails and storage refuses", async () => {
    vi.mocked(getCachedCallSheet).mockRejectedValue(new Error("blocked"));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect((await loadCallSheet("u", "id")).kind).toBe("error");
  });
});

describe("how long a load waits", () => {
  it("waits 15 s with no copy and 5 s with one, for all three reads", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(SHEET))));

    await loadCallSheet("u", "id");
    await loadPersonal("http://a", "id", "tok");
    await loadNextDay("http://a", "tok");
    expect(timeout.mock.calls.map(([ms]) => ms)).toEqual([15_000, 15_000, 15_000]);

    timeout.mockClear();
    vi.mocked(getCachedCallSheet).mockResolvedValue({ id: "id", data: SHEET, fetchedAt: SAVED_AT });
    await loadCallSheet("u", "id");
    await loadPersonal("http://a", "id", "tok");
    await loadNextDay("http://a", "tok");
    expect(timeout.mock.calls.map(([ms]) => ms)).toEqual([5_000, 5_000, 5_000]);
  });
});

describe("loadPersonal", () => {
  it.each([500, 429, 503])("a %i with nothing saved is unreachable, not invalid", async (status) => {
    vi.stubGlobal("fetch", answer({}, status));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "unreachable" });
  });

  it("a timeout with nothing saved is unreachable, not invalid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "unreachable" });
  });

  it("a page that is not JSON, such as a captive portal, is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>")));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "unreachable" });
  });

  it("only a 404 is invalid, even with a saved copy", async () => {
    vi.stubGlobal("fetch", answer(PERSON));
    await loadPersonal("http://a", "id", "tok");
    vi.stubGlobal("fetch", answer({}, 404));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "invalid" });
  });

  it("a failure after a good read returns the copy with the time it was saved", async () => {
    vi.stubGlobal("fetch", answer(PERSON));
    expect((await loadPersonal("http://a", "id", "tok")).kind).toBe("live");
    vi.stubGlobal("fetch", answer({}, 500));
    const again = await loadPersonal("http://a", "id", "tok");
    expect(again).toMatchObject({ kind: "saved", data: PERSON });
    expect(again.kind === "saved" && !Number.isNaN(Date.parse(again.savedAt))).toBe(true);
  });

  it("does not present the worker's cached copy as live, or re-date it", async () => {
    vi.stubGlobal("fetch", answer(PERSON, 200, { "x-filmrunner-source": "cache", "x-filmrunner-fetched-at": SAVED_AT }));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "saved", data: PERSON, savedAt: SAVED_AT });
    expect(localStorage.length).toBe(0);
  });

  it("ignores a copy that cannot say how old it is", async () => {
    localStorage.setItem("filmrunner-personal:id:tok", JSON.stringify(PERSON));
    vi.stubGlobal("fetch", answer({}, 500));
    expect(await loadPersonal("http://a", "id", "tok")).toEqual({ kind: "unreachable" });
  });
});
