import { useRef } from "react";

// Seven unhurried taps on a phone take about five seconds.
const WINDOW_MS = 7000;
// Five taps mean admin only once the tapping has clearly stopped; someone on their way to seven must never land there.
const SETTLE_MS = 1500;

/** Seven taps on the logo open the test environment; five, where offered, open admin access. */
export function useLogoGesture(onSeven: () => void, onFive?: () => void): () => void {
  const stamps = useRef<number[]>([]);
  const settling = useRef<ReturnType<typeof setTimeout> | null>(null);
  return () => {
    const now = Date.now();
    stamps.current = [...stamps.current.filter((t) => now - t < WINDOW_MS), now];
    if (settling.current) clearTimeout(settling.current);
    if (stamps.current.length >= 7) {
      stamps.current = [];
      onSeven();
    } else if (stamps.current.length >= 5 && onFive) {
      settling.current = setTimeout(() => { stamps.current = []; onFive(); }, SETTLE_MS);
    }
  };
}
