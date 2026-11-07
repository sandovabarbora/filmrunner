/** FR-226: a long day screen gets a row of links to its blocks that stays under the thumb and says where you are. */
import { useEffect, useRef, useState } from "react";

export interface JumpTarget { id: string; label: string }

const GAP = 8;

function edges(nav: HTMLElement | null): { top: number; line: number; bottom: number } {
  const bar = document.querySelector<HTMLElement>(".sandbox-bar");
  const top = bar ? bar.getBoundingClientRect().height : 0;
  const line = top + (nav?.getBoundingClientRect().height ?? 0) + GAP;
  const bottom = (document.querySelector<HTMLElement>(".publish-bar")?.getBoundingClientRect().height ?? 0) + GAP;
  return { top, line, bottom };
}

export function JumpRow({ targets, label }: { targets: JumpTarget[]; label: string }) {
  const nav = useRef<HTMLElement>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const [top, setTop] = useState(0);
  const ids = targets.map((t) => t.id).join(" ");

  // Headings, anchors and focused fields all land between the row and the publish bar, never under either.
  useEffect(() => {
    const root = document.documentElement;
    let observer: IntersectionObserver | null = null;
    const setup = () => {
      const e = edges(nav.current);
      setTop(e.top);
      root.style.scrollPaddingTop = `${e.line}px`;
      root.style.scrollPaddingBottom = `${e.bottom}px`;
      observer?.disconnect();
      if (typeof IntersectionObserver === "undefined") return;
      // A one-pixel band just under the row: the block crossing it is the one being read.
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) if (entry.isIntersecting) setCurrent(entry.target.id);
      }, { rootMargin: `-${Math.round(e.line)}px 0px -${Math.max(0, window.innerHeight - Math.round(e.line) - 1)}px 0px` });
      for (const id of ids.split(" ")) {
        const el = document.getElementById(id);
        if (el) observer.observe(el);
      }
    };
    setup();
    window.addEventListener("resize", setup);
    return () => {
      window.removeEventListener("resize", setup);
      observer?.disconnect();
      root.style.scrollPaddingTop = "";
      root.style.scrollPaddingBottom = "";
    };
  }, [ids]);

  // On a narrow phone the row scrolls sideways: the current block's link stays in sight.
  useEffect(() => {
    const row = nav.current;
    const link = row?.querySelector<HTMLElement>("[aria-current]");
    if (!row || !link) return;
    if (link.offsetLeft < row.scrollLeft) row.scrollLeft = link.offsetLeft;
    else if (link.offsetLeft + link.offsetWidth > row.scrollLeft + row.clientWidth) row.scrollLeft = link.offsetLeft + link.offsetWidth - row.clientWidth;
  }, [current]);

  const jump = (event: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    // The editor routes on the hash, so the link scrolls instead of navigating.
    event.preventDefault();
    if (el instanceof HTMLDetailsElement) el.open = true;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
    setCurrent(id);
  };

  return (
    <nav className="jump" id="jumpRow" ref={nav} aria-label={label} style={top ? { top } : undefined}>
      {targets.map((t) => (
        <a key={t.id} href={`#${t.id}`} aria-current={current === t.id ? "location" : undefined} onClick={(e) => jump(e, t.id)}>{t.label}</a>
      ))}
    </nav>
  );
}
