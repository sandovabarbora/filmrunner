const KEY = "filmrunner.sandbox";

export interface SandboxPersona {
  key: string;
  kind: "editor" | "link";
  token: string | null;
  call_sheet_id: string | null;
  personal_token: string | null;
}

export interface SandboxState {
  expires_at: string;
  personas: SandboxPersona[];
  current: string | null;
}

export function loadSandbox(): SandboxState | null {
  try {
    const state = JSON.parse(localStorage.getItem(KEY) ?? "null") as SandboxState | null;
    return state && new Date(state.expires_at).getTime() > Date.now() ? state : null;
  } catch {
    return null;
  }
}

export function saveSandbox(state: SandboxState | null): void {
  try {
    if (state) localStorage.setItem(KEY, JSON.stringify(state));
    else localStorage.removeItem(KEY);
  } catch {
    // Private mode: the test environment still works for this page, it just is not remembered.
  }
}

const CONNECTION_KEY = "filmrunner.editor.connection";

/** Leaves the test world for good, including a persona still signed in to the editor, so a real session is what remains. */
export function leaveSandbox(): void {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null") as SandboxState | null;
    const saved = JSON.parse(localStorage.getItem(CONNECTION_KEY) ?? "null") as { token?: string } | null;
    if (raw && saved && raw.personas.some((p) => p.token === saved.token)) localStorage.removeItem(CONNECTION_KEY);
    localStorage.removeItem(KEY);
  } catch {
    // Nothing stored, or storage is blocked: there is nothing to leave.
  }
}

/** A persona's token has run out: drop it, or the editor would sit on a sign-in that can only answer 401. */
export function dropExpiredPersona(): void {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null") as SandboxState | null;
    if (raw && new Date(raw.expires_at).getTime() <= Date.now()) leaveSandbox();
  } catch {
    // Same as above.
  }
}

/** Labels shared by the editor and the sheet: the persona a tester is looking through. */
export const PERSONA_NAMES: Record<string, { cs: string; en: string }> = {
  produkcni: { cs: "Produkční", en: "Production manager" },
  ad: { cs: "1. asistentka režie", en: "1st AD" },
  producent: { cs: "Producent", en: "Producer" },
  gaffer: { cs: "Hlavní osvětlovač", en: "Gaffer" },
  herecka: { cs: "Herečka", en: "Actress" },
  catering: { cs: "Catering", en: "Catering supplier" },
};
