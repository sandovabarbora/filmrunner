// Language toggle for landing.html: both languages are static markup in the
// DOM (see landing.css [data-lang] rules); this only flips which one shows.
// No framework, no build step needed beyond what Vite already does for a
// plain script entry.

type Lang = "cs" | "en";

const STORAGE_KEY = "filmrunner-landing-lang";

function detectDefault(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "cs" || saved === "en") return saved;
  } catch {
    // localStorage can throw in a locked-down browser; fall through to detection.
  }
  return navigator.language?.toLowerCase().startsWith("en") ? "en" : "cs";
}

function setLang(lang: Lang) {
  document.body.dataset.lang = lang;
  document.documentElement.lang = lang;
  for (const btn of document.querySelectorAll<HTMLButtonElement>(".langToggle button")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.lang === lang));
  }
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // best-effort only
  }
}

setLang(detectDefault());

for (const btn of document.querySelectorAll<HTMLButtonElement>(".langToggle button")) {
  btn.addEventListener("click", () => setLang(btn.dataset.lang as Lang));
}

// FR-25/FR-62 failure case: a screenshot that failed to render (missing file) hides its own <img>,
// so the visitor sees the other language's shot or nothing — never a broken-image icon.
function dropShot(img: HTMLImageElement): void {
  // Each figure holds one shot per language (FR-62): drop only the one that failed,
  // and the whole figure only when nothing is left to show.
  const figure = img.closest("figure");
  img.remove();
  if (figure && figure.querySelectorAll("[data-screenshot]").length === 0) figure.remove();
}

for (const img of document.querySelectorAll<HTMLImageElement>("[data-screenshot]")) {
  // This module is deferred, so an image can already have failed before the listener exists;
  // `complete` with no intrinsic width is exactly that case.
  if (img.complete && img.naturalWidth === 0) dropShot(img);
  else img.addEventListener("error", () => dropShot(img));
}
