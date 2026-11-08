// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { api, type Connection } from "../../api";
import { LangContext, translate } from "../../lang";
import type { Lang } from "../../../i18n";
import type { Dashboard } from "../../../types";
import { DashboardPanel } from "../Dashboard";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return { ...actual, api: { dashboard: vi.fn() } };
});

const conn: Connection = { apiBase: "https://api.example.test", token: "t" };

const board: Dashboard = {
  on_track: [],
  items: [{
    kind: "no_crew", production_id: "p", production_name: "Voda", call_sheet_id: "s", shoot_date: "2031-03-03", day_number: 4,
    revision_letter: "A", crew_call: "07:00", total: 0, confirmed: 0, not_opened: 0,
  }],
};

function show(lang: Lang) {
  vi.mocked(api.dashboard).mockResolvedValue(board);
  render(
    <LangContext.Provider value={{ lang, L: (text, vars) => translate(lang, text, vars), toggle: () => undefined }}>
      <DashboardPanel conn={conn} />
    </LangContext.Provider>,
  );
}

afterEach(cleanup);

describe("a day with nobody on it", () => {
  it("reads as needing attention in English, not as unpublished", async () => {
    show("en");
    expect(await screen.findByText("Nobody is on this call sheet")).toBeTruthy();
    expect(screen.getByText("Day 4 · Add crew or call cast, or nobody gets this sheet")).toBeTruthy();
    expect(screen.queryByText("Call sheet is not published")).toBeNull();
  });

  it("reads the same in Czech", async () => {
    show("cs");
    expect(await screen.findByText("Na dispozicích nikdo není")).toBeTruthy();
    expect(screen.getByText("4. den · Přidej štáb nebo svolej herce, jinak dispozice nikdo nedostane")).toBeTruthy();
  });
});

describe("today and tomorrow", () => {
  afterEach(() => vi.useRealTimers());

  it("are Prague's, whatever zone the browser is in", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-09T23:30:00Z"));  // 00:30 on the 10th in Prague
    vi.mocked(api.dashboard).mockResolvedValue({ on_track: [], items: [
      { ...board.items[0], call_sheet_id: "a", shoot_date: "2026-11-10", crew_call: "07:00" },
      { ...board.items[0], call_sheet_id: "b", shoot_date: "2026-11-11", crew_call: "08:00" },
    ] });
    render(
      <LangContext.Provider value={{ lang: "en", L: (text, vars) => translate("en", text, vars), toggle: () => undefined }}>
        <DashboardPanel conn={conn} />
      </LangContext.Provider>,
    );
    expect(await screen.findByText("today 07:00")).toBeTruthy();
    expect(screen.getByText("tomorrow 08:00")).toBeTruthy();
  });
});
