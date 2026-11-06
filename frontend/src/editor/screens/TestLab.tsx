import { useContext, useEffect, useState } from "react";
import { StillBackground } from "../../CallSheetView";
import { loadSandbox, PERSONA_NAMES, saveSandbox, type SandboxPersona, type SandboxState } from "../../sandbox";
import { saveConnection } from "../api";
import { LangContext } from "../lang";
import { API_BASE } from "../session";

const ABOUT: Record<string, { cs: string; en: string }> = {
  produkcni: { cs: "Čtyři filmy najednou, přehled co hoří", en: "Four films at once, and what is on fire" },
  ad: { cs: "Jeden film, změna plánu, kdo ještě neví", en: "One film, a plan change, who does not know yet" },
  producent: { cs: "Dva filmy, jen čtení", en: "Two films, read only" },
  gaffer: { cs: "Odkaz bez přihlášení: sraz o dvě hodiny dřív", en: "Link with no sign-in: call two hours earlier" },
  herecka: { cs: "Odkaz bez přihlášení: nové vyzvednutí", en: "Link with no sign-in: a new pickup" },
  catering: { cs: "Odkaz bez přihlášení: změna místa", en: "Link with no sign-in: a new place" },
};

async function startSession(): Promise<SandboxState> {
  const response = await fetch(`${API_BASE}/api/v1/public/sandbox/sessions`, { method: "POST" });
  if (!response.ok) throw new Error(String(response.status));
  return { ...(await response.json()), current: null } as SandboxState;
}

/** Seven taps on the logo land here. Each visitor gets a private world of invented films, deleted after a day. */
export function TestLab() {
  const { lang, L } = useContext(LangContext);
  const [state, setState] = useState<SandboxState | null>(loadSandbox);
  const [failed, setFailed] = useState<string | null>(null);

  async function fresh() {
    setFailed(null);
    setState(null);
    try {
      const next = await startSession();
      saveSandbox(next);
      setState(next);
    } catch (err) {
      setFailed(err instanceof Error ? err.message : "error");
    }
  }

  useEffect(() => { if (!loadSandbox()) void fresh(); }, []);

  function enter(persona: SandboxPersona) {
    if (!state) return;
    saveSandbox({ ...state, current: persona.key });
    if (persona.kind === "editor") {
      saveConnection({ apiBase: API_BASE, token: persona.token! });
      window.location.hash = "#/";
      window.location.reload();
    } else {
      window.location.href = `index.html?sheet=${persona.call_sheet_id}&api=${encodeURIComponent(API_BASE)}&me=${encodeURIComponent(persona.personal_token!)}&sandbox=1`;
    }
  }

  return (
    <div className="wrap">
      <StillBackground />
      <header className="masthead"><h1>FilmRunner</h1></header>
      <main className="test-lab" id="testLab">
        <h2>{L("Test environment")}</h2>
        <p className="test-lab-note">{L("Invented films, only for you, deleted after a day. Nothing here touches a real shoot.")}</p>
        {failed && <p className="status error" id="testLabFailed" role="alert">{failed === "429" || failed === "503" ? L("Too many test sessions right now. Try again in a minute.") : L("Could not start the test environment. Check your connection and try again.")}</p>}
        {!state && !failed && <p className="hint" id="testLabLoading">{L("Preparing test films…")}</p>}
        {state && (
          <ul className="test-personas" id="testPersonas">
            {state.personas.map((p) => (
              <li key={p.key}>
                <button type="button" data-persona={p.key} onClick={() => enter(p)}>
                  <b>{PERSONA_NAMES[p.key]?.[lang] ?? p.key}</b>
                  <span>{ABOUT[p.key]?.[lang]}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="inline">
          {state && <button type="button" className="quiet" id="testLabReset" onClick={() => void fresh()}>{L("Start over with fresh data")}</button>}
          <a className="quiet-link" id="testLabBack" href="#/">{L("Back")}</a>
        </div>
      </main>
    </div>
  );
}
