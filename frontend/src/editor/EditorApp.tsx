import { useEffect, useState } from "react";
import { api, ApiError, loadConnection, saveConnection, type Connection } from "./api";
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

export function EditorApp() {
  const [conn, setConn] = useState<Connection | null>(loadConnection);
  const [productions, setProductions] = useState<Production[] | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const route = useRoute();

  useEffect(() => {
    if (!conn) { setProductions(null); return; }
    api.listProductions(conn).then(setProductions).catch((err: unknown) => { setProductions([]); setNotice(noticeFromError(err, "Cannot load productions")); });
  }, [conn]);

  if (!conn) return <Connect onConnect={(c) => { saveConnection(c); setConn(c); navigate({ screen: "productions" }); }} />;

  const production = route.screen !== "productions" ? productions?.find((p) => p.id === route.productionId) ?? null : null;

  return (
    <div className="wrap">
      <header className="masthead">
        <h1><a href="#/" className="plain">FilmRunner</a></h1>
        <p className="sub">Editor · <button className="linklike" onClick={() => { saveConnection(null); setConn(null); }}>disconnect</button></p>
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
        <ProductionScreen conn={conn} productionId={route.productionId} production={production} tab={route.tab} setNotice={setNotice} />
      )}
      {route.screen === "day" && (
        <DayEditor conn={conn} productionId={route.productionId} productionName={production?.name ?? null} callSheetId={route.callSheetId} setNotice={setNotice} />
      )}
    </div>
  );
}

function Connect({ onConnect }: { onConnect: (c: Connection) => void }) {
  const [apiBase, setApiBase] = useState("https://filmrunner-api.fly.dev");
  const [token, setToken] = useState("");
  return (
    <div className="wrap">
      <header className="masthead"><h1>FilmRunner</h1><p className="sub">Editor</p></header>
      <section className="block" aria-label="Connect">
        <h2>Connect</h2>
        <p className="hint">Temporary until sign-in lands: paste the API token once; it stays on this phone.</p>
        <label className="field" htmlFor="apiBase"><span className="label">API</span><input id="apiBase" value={apiBase} onChange={(e) => setApiBase(e.target.value)} /></label>
        <label className="field" htmlFor="token"><span className="label">Token</span><input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
        <button id="connect" disabled={!token.trim() || !apiBase.trim()} onClick={() => onConnect({ apiBase: apiBase.trim(), token: token.trim() })}>Connect</button>
      </section>
    </div>
  );
}
