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

// A screenshot that failed to render (missing file, e.g. FR-25's own
// failure case) disappears instead of showing a broken-image icon.
for (const img of document.querySelectorAll<HTMLImageElement>("[data-screenshot]")) {
  img.addEventListener("error", () => {
    img.closest("figure")?.remove();
  });
}
