import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api";
import { noticeFromError } from "../EditorApp";
import { setCurrentLang } from "../lang";

const conn = { apiBase: "https://api.test", token: "t" };

function respondWith(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(typeof body === "string" ? body : JSON.stringify(body), { status })));
}

async function failure(): Promise<ApiError> {
  try {
    await api.dashboard(conn);
  } catch (err) {
    return err as ApiError;
  }
  throw new Error("expected the call to fail");
}

afterEach(() => vi.unstubAllGlobals());

describe("request errors", () => {
  it("turns a 422's list of problems into something readable", async () => {
    respondWith(422, { detail: [
      { loc: ["body", "initial_revision", "general_crew_call"], msg: "Value error, must be a time from 00:00 to 23:59, like 06:30", type: "value_error" },
      { loc: ["body", "unit_name"], msg: "String should have at most 100 characters", type: "string_too_long" },
    ] });
    const err = await failure();
    expect(err.status).toBe(422);
    expect(err.message).toBe("general_crew_call: must be a time from 00:00 to 23:59, like 06:30; unit_name: String should have at most 100 characters");
  });

  it("keeps a plain detail as it is", async () => {
    respondWith(409, { detail: "Day 3 already exists" });
    expect((await failure()).message).toBe("Day 3 already exists");
  });
});

describe("what the AD is told", () => {
  it("a server error reads as a server error, in both languages, with no internals", async () => {
    respondWith(500, { detail: "Internal server error" });
    const err = await failure();
    expect(err.status).toBe(500);
    setCurrentLang("en");
    const en = noticeFromError(err, "Publish failed");
    expect(en?.kind).toBe("error");
    expect(en?.text).toContain("The server had a problem");
    expect(en?.text).not.toMatch(/connection\. Nothing|Internal server error/);
    setCurrentLang("cs");
    expect(noticeFromError(err, "Vydání se nezdařilo")?.text).toContain("Problém je na serveru");
  });

  it("a gateway error with no JSON body is a server error too", async () => {
    respondWith(502, "<html>Bad gateway</html>");
    const err = await failure();
    setCurrentLang("en");
    expect(noticeFromError(err, "Publish failed")?.text).toContain("The server had a problem");
  });

  it("only a request that got no answer is no connection", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const err = await failure();
    expect(err.status).toBe(0);
    setCurrentLang("en");
    expect(noticeFromError(err, "Publish failed")?.text).toContain("No connection");
  });
});
