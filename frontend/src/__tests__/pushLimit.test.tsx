// @vitest-environment jsdom
/** FR-220: a member at the device limit gets a reason in their language, and confirming is never held up by it. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmRevision } from "../ConfirmRevision";
import { NotificationToggle } from "../NotificationToggle";
import { PushLimitError, subscribe } from "../push";
import type { Lang } from "../i18n";

vi.mock("../loader", () => ({ confirmRevision: vi.fn().mockResolvedValue({ kind: "confirmed", confirmedAt: "2026-11-06T10:00:00Z" }) }));

const API = "http://localhost:8000";
const unsubscribeBrowser = vi.fn().mockResolvedValue(true);

function stubBrowser() {
  const subscription = { endpoint: "https://fcm.googleapis.com/fcm/send/x", unsubscribe: unsubscribeBrowser, toJSON: () => ({ endpoint: "https://fcm.googleapis.com/fcm/send/x", keys: { p256dh: "p", auth: "a" } }) };
  vi.stubGlobal("Notification", Object.assign(vi.fn(), { permission: "default", requestPermission: vi.fn().mockResolvedValue("granted") }));
  vi.stubGlobal("PushManager", vi.fn());
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { ready: Promise.resolve({ pushManager: { getSubscription: vi.fn().mockResolvedValue(null), subscribe: vi.fn().mockResolvedValue(subscription) } }) } });
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/vapid-key")) return new Response(JSON.stringify({ public_key: "AAAA" }), { status: 200 });
    return new Response(JSON.stringify({ detail: "limit" }), { status: 409 });
  }));
}

const LIMIT_TEXT: Record<Lang, RegExp> = { en: /5 devices/, cs: /5 zařízení/ };

describe("FR-220: the device limit", () => {
  beforeEach(stubBrowser);
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

  it("subscribe reports the limit as its own error and drops the browser subscription nobody will use", async () => {
    await expect(subscribe(API, "tok", "AAAA")).rejects.toBeInstanceOf(PushLimitError);
    expect(unsubscribeBrowser).toHaveBeenCalled();
  });

  it.each<Lang>(["en", "cs"])("the toggle explains it in %s, without the HTTP status", async (lang) => {
    const user = userEvent.setup();
    render(<NotificationToggle apiBase={API} token="tok" lang={lang} />);
    await user.click(await screen.findByRole("button"));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(LIMIT_TEXT[lang]);
    expect(status).not.toHaveTextContent("409");
  });

  it.each<Lang>(["en", "cs"])("confirming still counts in %s, says why notifications are off and offers no pointless retry", async (lang) => {
    const user = userEvent.setup();
    render(<ConfirmRevision apiBase={API} sheetId="s1" token="tok" letter="A" confirmedAt={null} waitingFor={null} lang={lang} onStale={vi.fn()} pushable changed={false} />);
    await waitFor(() => expect(document.querySelector("#confirmPushNote")).not.toBeNull());
    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(document.querySelector("#confirmDone")).not.toBeNull());
    await waitFor(() => expect(document.querySelector("#confirmPushLimit")?.textContent).toMatch(LIMIT_TEXT[lang]));
    expect(document.querySelector("#confirmPushEnable")).toBeNull();
  });
});
