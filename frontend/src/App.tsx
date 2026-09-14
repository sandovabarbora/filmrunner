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
    if (r.kind === "live") setStatus({ kind: "online", text: "Live data, cached for offline viewing." });
    if (r.kind === "cached") setStatus({ kind: "offline", text: `Network unavailable (${r.reason}). Showing last cached revision.` });
    if (r.kind === "error") setStatus({ kind: "error", text: `Could not reach the server and nothing is cached for this ID yet (${r.reason}).` });
  }

  useEffect(() => {
    if (mode.kind === "demo") void load(DEMO_URL, DEMO_ID);
    if (mode.kind === "share") void load(publicCallSheetUrl(mode.api, mode.sheet), mode.sheet);
  }, [mode]);

  const subtitle =
    mode.kind === "dev"
      ? "Development mode: point at a FilmRunner API and enter a call sheet ID."
      : mode.kind === "share"
        ? "Your call sheet. Add this page to your home screen; it keeps working with no signal."
        : "Demo shoot day. Add this page to your home screen; it keeps working with no signal.";

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
      <h1>FilmRunner · call sheet</h1>
      <div className="sub" id="subtitle">{subtitle}</div>

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

      {result && result.kind !== "error" && (
        <CallSheetView
          callSheet={result.data}
          freshness={result.kind === "cached" ? { fromCache: true, fetchedAt: result.fetchedAt } : { fromCache: false }}
        />
      )}
      {(!result || result.kind === "error") && <div id="sheet" className="sheet" />}
    </div>
  );
}
