/**
 * FR-58: the editor in Czech. English text is the key; `cs.ts` maps it to
 * Czech. Anything not in the map stays English (never a key). The choice is
 * shared with the crew's sheet (same localStorage key via ../i18n).
 */
import { createContext, useContext } from "react";
import { detectLang, type Lang } from "../i18n";
import { CS } from "./cs";

export type L = (text: string, vars?: Record<string, string | number>) => string;

export function translate(lang: Lang, text: string, vars: Record<string, string | number> = {}): string {
  const raw = lang === "cs" ? (CS[text] ?? text) : text;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) => (vars[name] !== undefined ? String(vars[name]) : `{${name}}`));
}

let current: Lang = detectLang();
/** For plain functions outside React (noticeFromError): the language the provider last set. */
export function currentLang(): Lang { return current; }
export function setCurrentLang(lang: Lang): void { current = lang; }

export const LangContext = createContext<{ lang: Lang; L: L; toggle: () => void }>({ lang: "en", L: (text, vars) => translate("en", text, vars), toggle: () => undefined });

export function useL(): L {
  return useContext(LangContext).L;
}

export function useLang(): Lang {
  return useContext(LangContext).lang;
}
