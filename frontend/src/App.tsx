import { useEffect, useState } from "react";
import { CallSheetView } from "./CallSheetView";
import { loadCallSheet, publicCallSheetUrl, type LoadResult } from "./loader";

/**
 * The URL decides what the page is:
 *   ?sheet=<id>&api=<base>  a shared call sheet from a FilmRunner API (crew link)
 *   ?dev=1                  the lookup form, for local development
 *   anything else           the bundled demo, so the public URL never shows a form
 */
type Mode =
  | { kind: "share"; api: string; sheet: string }
  | { kind: "dev" }
  | { kind: "demo" };

const DEMO_URL = "demo/call-sheet.json";
const DEMO_ID = "demo";

function modeFromLocation(): Mode {
  const params = new URLSearchParams(window.location.search);
  const sheet = params.get("sheet");
  const api = params.get("api");
  if (sheet && api) return { kind: "share", api, sheet };
  if (params.get("dev") === "1") return { kind: "dev" };
  return { kind: "demo" };
}

type Status = { kind: "" | "online" | "offline" | "error"; text: string };

export function App() {
  const [mode] = useState<Mode>(modeFromLocation);
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [sheetId, setSheetId] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "", text: "" });
  const [result, setResult] = useState<LoadResult | null>(null);

  async function load(url: string, id: string) {
    const r = await loadCallSheet(url, id);
    setResult(r);
    if (r.kind === "live") setStatus({ kind: "online", text: "Live · saved on this phone for offline use." });
    if (r.kind === "cached") setStatus({ kind: "offline", text: `Offline · showing the copy saved ${new Date(r.fetchedAt).toLocaleString()}. Times may have changed since.` });
    if (r.kind === "error") setStatus({ kind: "error", text: `Could not load this call sheet (${r.reason}).` });
  }

  useEffect(() => {
    if (mode.kind === "demo") void load(DEMO_URL, DEMO_ID);
    if (mode.kind === "share") void load(publicCallSheetUrl(mode.api, mode.sheet), mode.sheet);
  }, [mode]);

  const subtitle =
    mode.kind === "dev" ? "Development" : mode.kind === "share" ? "Your call sheet" : "Demo shoot day";
  const loading = result === null && mode.kind !== "dev";

  function onLookup() {
    const id = sheetId.trim();
    if (!id) {
      setStatus({ kind: "error", text: "Enter a call sheet ID." });
      return;
    }
    void load(publicCallSheetUrl(apiBase, id), id);
  }

  return (
    <div className="wrap">
      <header className="masthead">
        <h1>FilmRunner</h1>
        <p className="sub" id="subtitle">{subtitle}</p>
      </header>

      {mode.kind === "dev" && (
        <div className="lookup" id="lookup">
          <input id="apiBase" type="text" value={apiBase} onChange={(e) => setApiBase(e.target.value)}
            placeholder="API base, e.g. http://localhost:8000" />
          <input id="callSheetId" type="text" value={sheetId} onChange={(e) => setSheetId(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onLookup(); }} placeholder="Call sheet ID" />
          <button id="loadBtn" onClick={onLookup}>Load</button>
        </div>
      )}

      <div id="status" className={`status ${status.kind}`}>{status.text}</div>

      {loading && (
        <div className="skeleton" aria-hidden="true"><i /><i /><i /></div>
      )}

      {result && result.kind !== "error" && (
        <CallSheetView
          callSheet={result.data}
          freshness={result.kind === "cached" ? { fromCache: true, fetchedAt: result.fetchedAt } : { fromCache: false }}
        />
      )}
      {result?.kind === "error" && (
        <div className="empty" role="status">
          This call sheet is not on this phone yet and the server could not be reached. Get back in signal and reload; it will be saved for offline use after the first load.
        </div>
      )}
      {(!result || result.kind === "error") && <div id="sheet" className="sheet" />}
    </div>
  );
}
