import { PERSONA_NAMES } from "./sandbox";

/** Always on screen in the test environment, so nobody mistakes invented data for a real shoot. */
export function SandboxBar({ persona, lang, switchHref, onExit }: { persona: string | null; lang: "cs" | "en"; switchHref: string; onExit: () => void }) {
  const cs = lang === "cs";
  const name = persona ? PERSONA_NAMES[persona]?.[lang] : null;
  return (
    <div className="sandbox-bar" id="sandboxBar" role="status">
      <span><b>{cs ? "Testovací prostředí" : "Test environment"}</b>{name ? ` · ${name}` : ""}</span>
      <span className="sandbox-actions">
        <a href={switchHref} id="sandboxSwitch">{cs ? "Změnit osobu" : "Switch person"}</a>
        <button type="button" className="sandbox-exit" id="sandboxExit" onClick={onExit}>{cs ? "Ukončit" : "Leave"}</button>
      </span>
    </div>
  );
}
