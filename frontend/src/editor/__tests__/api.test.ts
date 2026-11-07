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
      { loc: ["body", "unit_name"], msg: "String should have at most 100 characters", type: "string_too_long", ctx: { max_length: 100 } },
    ] });
    setCurrentLang("en");
    const err = await failure();
    expect(err.status).toBe(422);
    expect(err.message).toBe("Crew call: write a time from 00:00 to 23:59, like 06:30.; Unit: too long, at most 100 characters.");
  });

  it("says it in Czech when the editor is in Czech, naming the field in words", async () => {
    respondWith(422, { detail: [
      { loc: ["body", "initial_revision", "crew_calls", 0, "pickup_time"], msg: "Value error, must be a time from 00:00 to 23:59, like 06:30", type: "value_error" },
      { loc: ["body", "initial_revision", "safety_notes"], msg: "String should have at most 2000 characters", type: "string_too_long", ctx: { max_length: 2000 } },
      { loc: ["body", "name"], msg: "Value error, must not contain a NUL byte", type: "value_error" },
    ] });
    setCurrentLang("cs");
    expect((await failure()).message).toBe("Vyzvednutí: napiš čas od 00:00 do 23:59, třeba 06:30.; Bezpečnost: příliš dlouhé, nejvýš 2000 znaků.; Jméno: obsahuje znak, který nejde uložit.");
    setCurrentLang("en");
  });

  it("keeps an unknown field and message as the server wrote them", async () => {
    respondWith(422, { detail: [{ loc: ["body", "role"], msg: "Input should be 'viewer'", type: "literal_error" }] });
    setCurrentLang("en");
    expect((await failure()).message).toBe("role: Input should be 'viewer'");
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
