// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { modeFromLocation } from "../App";

function at(search: string) {
  window.history.pushState({}, "", `/${search}`);
  return modeFromLocation();
}

const OURS = "https%3A%2F%2Ffilmrunner-api.fly.dev";

describe("FR-220: the sheet only trusts an API we run", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("opens a crew link on our API", () => {
    expect(at(`?sheet=s1&api=${OURS}&me=tok`)).toEqual({ kind: "share", api: "https://filmrunner-api.fly.dev", sheet: "s1", me: "tok" });
    expect(at(`?api=${OURS}&me=tok`)).toEqual({ kind: "mine", api: "https://filmrunner-api.fly.dev", me: "tok" });
  });

  it("keeps loopback for development and the e2e tests", () => {
    expect(at("?sheet=s1&api=http://127.0.0.1:8000").kind).toBe("share");
    expect(at("?sheet=s1&api=http://localhost:8000").kind).toBe("share");
  });

  it("trusts the API this build was configured with", () => {
    vi.stubEnv("VITE_API_BASE", "https://api.filmrunner.example");
    expect(at("?sheet=s1&api=https://api.filmrunner.example").kind).toBe("share");
  });

  it.each([
    "https://evil.example",
    "https://filmrunner-api.fly.dev.evil.example",
    "https://filmrunner-api.fly.dev@evil.example",
    "http://filmrunner-api.fly.dev",
    "https://localhost.evil.example",
    "javascript:alert(1)",
    "not a url",
  ])("a crafted link to %s shows no sheet and fetches nothing from it", (api) => {
    const encoded = encodeURIComponent(api);
    expect(at(`?sheet=s1&api=${encoded}`)).toEqual({ kind: "home" });
    expect(at(`?me=tok&api=${encoded}`)).toEqual({ kind: "home" });
  });

  it("leaves the links with no api alone", () => {
    expect(at("?demo=1").kind).toBe("demo");
    expect(at("?dev=1").kind).toBe("dev");
    expect(at("").kind).toBe("home");
  });
});
