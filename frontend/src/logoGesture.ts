import { useRef } from "react";

const WINDOW_MS = 3000;
// Long enough for a sixth tap to arrive, short enough that five taps still feel immediate.
const SETTLE_MS = 700;

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
