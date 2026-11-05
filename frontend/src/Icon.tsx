/**
 * FilmRunner's own icon set, shared by the viewer and the editor. One grid (24), one stroke (1.75, round),
 * drawn in currentColor so an icon always matches the text of the control it sits in. Inline SVG, not a font
 * or emoji: it renders the same on every phone, offline, and prints as a line.
 *
 * Always decorative — the control's own text or aria-label names the action (FR-82), so the icon never
 * becomes part of an accessible name.
 */

const PATHS = {
  phone: <path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />,
  chat: <path d="M20.5 11.5a8.5 8.5 0 0 1-12.4 7.6L3.5 20.5l1.4-4.6a8.5 8.5 0 1 1 15.6-4.4z" />,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" /></>,
  check: <path d="M5 12.5l4.5 4.5L19 7" />,
  todo: <circle cx="12" cy="12" r="7" />,
  bell: <><path d="M6 9.5a6 6 0 0 1 12 0c0 5.5 2.5 7 2.5 7h-17S6 15 6 9.5z" /><path d="M10 20a2 2 0 0 0 4 0" /></>,
  up: <path d="M12 19V5M6 11l6-6 6 6" />,
  down: <path d="M12 5v14M6 13l6 6 6-6" />,
  right: <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  link: <><path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" /><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" /></>,
  print: <><path d="M7 9V3.5h10V9" /><rect x="3" y="9" width="18" height="8" rx="2" /><path d="M7 14h10v6.5H7z" /></>,
  send: <><path d="M20.5 3.5L10 14" /><path d="M20.5 3.5l-6.5 17-4-6.5-6.5-4z" /></>,
} as const;

export type IconName = keyof typeof PATHS;

// Runtime mirror of PATHS' keys, for tests that must cover every icon that actually
// exists rather than a list someone has to remember to update by hand.
export const ICON_NAMES = Object.keys(PATHS) as IconName[];

export function Icon({ name }: { name: IconName }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
