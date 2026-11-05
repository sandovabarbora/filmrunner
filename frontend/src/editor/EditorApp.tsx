import { useContext, useEffect, useRef, useState } from "react";
import { StillBackground } from "../CallSheetView";
import { api, ApiError, saveConnection, type Connection } from "./api";
import { API_BASE, connectionFromSession, requestCode, serviceConnection, signInConfigured, signOut, supabase, verifyCode } from "./session";
import { href, navigate, useRoute } from "./route";
import { ProductionsScreen } from "./screens/Productions";
import { ProductionScreen } from "./screens/Production";
import { DayEditor } from "./screens/DayEditor";
import type { Production } from "../types";
import { LangContext, currentLang, setCurrentLang, translate, useL } from "./lang";
import { detectLang, rememberLang, type Lang } from "../i18n";

export type Notice = { kind: "ok" | "warn" | "error"; text: string } | null;

export function noticeFromError(err: unknown, fallback: string): Notice {
  if (err instanceof ApiError) {
    const T = (text: string) => translate(currentLang(), text);
    if (err.status === 0) return { kind: "warn", text: T("No connection. Nothing was lost; try again when you are back in signal.") };
    if (err.status === 401) return { kind: "error", text: T("The token was rejected. Disconnect and connect again.") };
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

function EditorAppInner() {
  const L = useL();
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
    api.listProductions(conn).then(setProductions).catch((err: unknown) => { setProductions([]); setNotice(noticeFromError(err, L("Cannot load productions"))); });
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
        <p className="sub">{serviceConnection() ? "Admin" : L("Editor")} · <button className="linklike" onClick={() => void disconnect()}>{L("sign out")}</button> · <LangToggle /></p>
      </header>

      <nav className="crumbs" aria-label={L("Breadcrumb")}>
        <a href={href({ screen: "productions" })}>{L("Productions")}</a>
        {route.screen !== "productions" && (
          <>
            <span className="sep">/</span>
            <a href={href({ screen: "production", productionId: route.productionId, tab: "days" })}>{production?.name ?? "Production"}</a>
          </>
        )}
        {route.screen === "day" && (<><span className="sep">/</span><span>{route.callSheetId ? L("Day") : L("New day")}</span></>)}
      </nav>

      {notice && <div id="notice" className={`status ${notice.kind === "ok" ? "online" : notice.kind === "warn" ? "offline" : "error"}`} role="status">{notice.text}</div>}
      <main id="main">

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
      </main>
    </div>
  );
}

/** FR-58: the editor's language, shared with the crew's sheet (same storage key); the toggle lives in every masthead. */
export function EditorApp() {
  const [lang, setLang] = useState<Lang>(detectLang);
  setCurrentLang(lang);
  const L = (text: string, vars?: Record<string, string | number>) => translate(lang, text, vars);
  const value = { lang, L, toggle: () => { const next: Lang = lang === "cs" ? "en" : "cs"; rememberLang(next); setCurrentLang(next); setLang(next); } };
  return <LangContext.Provider value={value}><EditorAppInner /></LangContext.Provider>;
}

function LangToggle() {
  const { lang, toggle } = useContext(LangContext);
  // FR-82: no aria-label — the printed target-language name is the accessible name too, so it can't drift from what's on screen.
  return <button type="button" className="linklike" id="langToggle" onClick={toggle} title={lang === "cs" ? "Switch to English" : "Přepnout do češtiny"}>{lang === "cs" ? "English" : "Čeština"}</button>;
}

function SignIn({ onSignedIn, onLogoTap }: { onSignedIn: () => void; onLogoTap: () => void }) {
  const L = useL();
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
      <header className="masthead"><h1 id="logo" onClick={onLogoTap}>FilmRunner</h1><p className="sub">{L("Editor")} · <LangToggle /></p></header>
      <StillBackground />
      <main className="block sign-in" id="main" aria-label={L("Sign in")}>
        <h2>{L("Sign in")}</h2>
        {error && <div id="notice" className="status error" role="status">{error}</div>}
        {!sent ? (
          <>
            <p className="hint">{L("Enter your email. You will get a 6-digit code (and a link) to sign in; no password.")}</p>
            <label className="field" htmlFor="email"><span className="label">{L("Email")}</span><input id="email" type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && email.includes("@")) void send(); }} /></label>
            <button id="sendCode" disabled={!email.includes("@") || busy} onClick={() => void send()}>{busy ? L("Sending…") : L("Send me a code")}</button>
          </>
        ) : (
          <>
            <p className="hint">Check {email}. Type the 6-digit code from the email, or tap the link in it.</p>
            <label className="field" htmlFor="code"><span className="label">{L("Code")}</span><input id="code" className="mono" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && code.trim().length >= 6) void verify(); }} /></label>
            <button id="verifyCode" disabled={code.trim().length < 6 || busy} onClick={() => void verify()}>{busy ? L("Checking…") : L("Sign in")}</button>
            <button type="button" className="quiet" onClick={() => { setSent(false); setCode(""); }}>{L("Use a different email")}</button>
          </>
        )}
      </main>
    </div>
  );
}

function Connect({ onConnect, admin = false, onCancel, onLogoTap }: { onConnect: (c: Connection) => void; admin?: boolean; onCancel?: () => void; onLogoTap?: () => void }) {
  const L = useL();
  const [apiBase, setApiBase] = useState(API_BASE);
  const [token, setToken] = useState("");
  return (
    <div className="wrap">
      <header className="masthead"><h1 id="logo" onClick={onLogoTap}>FilmRunner</h1><p className="sub">{admin ? "Admin" : "Editor"}</p></header>
      <main className="block" id={admin ? "adminScreen" : "connectScreen"} aria-label={L("Connect")}>
        <h2>{admin ? "Admin access" : "Connect"}</h2>
        <p className="hint">
          {admin
            ? "Paste the service token once; it stays on this phone and bypasses sign-in. Sign out removes it. Nothing here is stored in the app itself."
            : "Development build without sign-in configured: paste the API token once; it stays on this phone."}
        </p>
        <label className="field" htmlFor="apiBase"><span className="label">API</span><input id="apiBase" value={apiBase} onChange={(e) => setApiBase(e.target.value)} /></label>
        <label className="field" htmlFor="token"><span className="label">{L("Token")}</span><input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
        <button id="connect" disabled={!token.trim() || !apiBase.trim()} onClick={() => onConnect({ apiBase: apiBase.trim(), token: token.trim() })}>{L("Connect")}</button>
        {onCancel && <button type="button" className="quiet" id="adminCancel" onClick={onCancel}>{L("Back")}</button>}
      </main>
    </div>
  );
}
