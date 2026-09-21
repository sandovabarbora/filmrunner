import { useEffect, useRef, useState } from "react";
import { api, ApiError, saveConnection, type Connection } from "./api";
import { API_BASE, connectionFromSession, requestCode, serviceConnection, signInConfigured, signOut, supabase, verifyCode } from "./session";
import { href, navigate, useRoute } from "./route";
import { ProductionsScreen } from "./screens/Productions";
import { ProductionScreen } from "./screens/Production";
import { DayEditor } from "./screens/DayEditor";
import type { Production } from "../types";

export type Notice = { kind: "ok" | "warn" | "error"; text: string } | null;

export function noticeFromError(err: unknown, fallback: string): Notice {
  if (err instanceof ApiError) {
    if (err.status === 0) return { kind: "warn", text: "No connection. Nothing was lost; try again when you are back in signal." };
    if (err.status === 401) return { kind: "error", text: "The token was rejected. Disconnect and connect again." };
    return { kind: "error", text: `${fallback}: ${err.message}` };
  }
  return { kind: "error", text: `${fallback}: ${String(err)}` };
}

/** Five taps on the logo within three seconds open the admin screen (service token entry). */
function useTapGesture(onTrigger: () => void, taps = 5, windowMs = 3000) {
  const stamps = useRef<number[]>([]);
  return () => {
    const now = Date.now();
    stamps.current = [...stamps.current.filter((t) => now - t < windowMs), now];
    if (stamps.current.length >= taps) {
      stamps.current = [];
      onTrigger();
    }
  };
}

export function EditorApp() {
  const [conn, setConn] = useState<Connection | null>(serviceConnection);
  const [authChecked, setAuthChecked] = useState(() => serviceConnection() !== null || !signInConfigured);
  const [adminScreen, setAdminScreen] = useState(false);
  const onLogoTap = useTapGesture(() => setAdminScreen(true));

  // Product path: a Supabase session (persisted by supabase-js) becomes the connection and follows token refreshes.
  useEffect(() => {
    if (serviceConnection() || !signInConfigured) return;
    const sb = supabase();
    sb.auth.getSession().then(({ data }) => { if (data.session) setConn(connectionFromSession(data.session)); setAuthChecked(true); });
    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => { setConn(session ? connectionFromSession(session) : null); });
    return () => sub.subscription.unsubscribe();
  }, []);
  const [productions, setProductions] = useState<Production[] | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const route = useRoute();

  useEffect(() => {
    if (!conn) { setProductions(null); return; }
    api.listProductions(conn).then(setProductions).catch((err: unknown) => { setProductions([]); setNotice(noticeFromError(err, "Cannot load productions")); });
  }, [conn]);

  if (!authChecked) return <div className="wrap"><div className="skeleton" aria-hidden="true"><i /><i /><i /></div></div>;
  if (adminScreen) {
    return (
      <Connect
        admin
        onConnect={(c) => { saveConnection(c); setConn(c); setAdminScreen(false); navigate({ screen: "productions" }); }}
        onCancel={() => setAdminScreen(false)}
      />
    );
  }
  if (!conn) return signInConfigured
    ? <SignIn onSignedIn={() => navigate({ screen: "productions" })} onLogoTap={onLogoTap} />
    : <Connect onConnect={(c) => { saveConnection(c); setConn(c); navigate({ screen: "productions" }); }} onLogoTap={onLogoTap} />;

  async function disconnect() {
    saveConnection(null);
    await signOut();
    setConn(null);
  }

  const production = route.screen !== "productions" ? productions?.find((p) => p.id === route.productionId) ?? null : null;

  return (
    <div className="wrap">
      <header className="masthead">
        <h1 id="logo" onClick={onLogoTap}><a href="#/" className="plain">FilmRunner</a></h1>
        <p className="sub">{serviceConnection() ? "Admin" : "Editor"} · <button className="linklike" onClick={() => void disconnect()}>sign out</button></p>
      </header>

      <nav className="crumbs" aria-label="Breadcrumb">
        <a href={href({ screen: "productions" })}>Productions</a>
        {route.screen !== "productions" && (
          <>
            <span className="sep">/</span>
            <a href={href({ screen: "production", productionId: route.productionId, tab: "days" })}>{production?.name ?? "Production"}</a>
          </>
        )}
        {route.screen === "day" && (<><span className="sep">/</span><span>{route.callSheetId ? "Day" : "New day"}</span></>)}
      </nav>

      {notice && <div id="notice" className={`status ${notice.kind === "ok" ? "online" : notice.kind === "warn" ? "offline" : "error"}`} role="status">{notice.text}</div>}

      {route.screen === "productions" && (
        <ProductionsScreen conn={conn} productions={productions} onCreated={(p) => setProductions((ps) => [...(ps ?? []), p])} setNotice={setNotice} />
      )}
      {route.screen === "production" && (
        <ProductionScreen conn={conn} productionId={route.productionId} production={production} tab={route.tab} setNotice={setNotice}
          onUpdated={(p) => setProductions((ps) => (ps ?? []).map((x) => (x.id === p.id ? p : x)))} />
      )}
      {route.screen === "day" && (
        <DayEditor conn={conn} productionId={route.productionId} productionName={production?.name ?? null} callSheetId={route.callSheetId}
          canPublish={(production?.permissions ?? []).includes("day:publish")} setNotice={setNotice} />
      )}
    </div>
  );
}

function SignIn({ onSignedIn, onLogoTap }: { onSignedIn: () => void; onLogoTap: () => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    setBusy(true); setError(null);
    try { await requestCode(email.trim()); setSent(true); }
    catch (err) { setError(`Could not send the code: ${(err as Error).message}`); }
    finally { setBusy(false); }
  }
  async function verify() {
    setBusy(true); setError(null);
    try { await verifyCode(email.trim(), code); onSignedIn(); }
    catch (err) { setError(`That code did not work: ${(err as Error).message}`); }
    finally { setBusy(false); }
  }

  return (
    <div className="wrap">
      <header className="masthead"><h1 id="logo" onClick={onLogoTap}>FilmRunner</h1><p className="sub">Editor</p></header>
      <section className="block" aria-label="Sign in">
        <h2>Sign in</h2>
        {error && <div id="notice" className="status error" role="status">{error}</div>}
        {!sent ? (
          <>
            <p className="hint">Enter your email. You will get a 6-digit code (and a link) to sign in; no password.</p>
            <label className="field" htmlFor="email"><span className="label">Email</span><input id="email" type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && email.includes("@")) void send(); }} /></label>
            <button id="sendCode" disabled={!email.includes("@") || busy} onClick={() => void send()}>{busy ? "Sending…" : "Send me a code"}</button>
          </>
        ) : (
          <>
            <p className="hint">Check {email}. Type the 6-digit code from the email, or tap the link in it.</p>
            <label className="field" htmlFor="code"><span className="label">Code</span><input id="code" className="mono" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && code.trim().length >= 6) void verify(); }} /></label>
            <button id="verifyCode" disabled={code.trim().length < 6 || busy} onClick={() => void verify()}>{busy ? "Checking…" : "Sign in"}</button>
            <button type="button" className="quiet" onClick={() => { setSent(false); setCode(""); }}>Use a different email</button>
          </>
        )}
      </section>
    </div>
  );
}

function Connect({ onConnect, admin = false, onCancel, onLogoTap }: { onConnect: (c: Connection) => void; admin?: boolean; onCancel?: () => void; onLogoTap?: () => void }) {
  const [apiBase, setApiBase] = useState(API_BASE);
  const [token, setToken] = useState("");
  return (
    <div className="wrap">
      <header className="masthead"><h1 id="logo" onClick={onLogoTap}>FilmRunner</h1><p className="sub">{admin ? "Admin" : "Editor"}</p></header>
      <section className="block" aria-label="Connect" id={admin ? "adminScreen" : "connectScreen"}>
        <h2>{admin ? "Admin access" : "Connect"}</h2>
        <p className="hint">
          {admin
            ? "Paste the service token once; it stays on this phone and bypasses sign-in. Sign out removes it. Nothing here is stored in the app itself."
            : "Development build without sign-in configured: paste the API token once; it stays on this phone."}
        </p>
        <label className="field" htmlFor="apiBase"><span className="label">API</span><input id="apiBase" value={apiBase} onChange={(e) => setApiBase(e.target.value)} /></label>
        <label className="field" htmlFor="token"><span className="label">Token</span><input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
        <button id="connect" disabled={!token.trim() || !apiBase.trim()} onClick={() => onConnect({ apiBase: apiBase.trim(), token: token.trim() })}>Connect</button>
        {onCancel && <button type="button" className="quiet" id="adminCancel" onClick={onCancel}>Back</button>}
      </section>
    </div>
  );
}
