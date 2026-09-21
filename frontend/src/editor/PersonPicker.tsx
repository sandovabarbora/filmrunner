/**
 * FR-45: a name field that offers people already in FilmRunner (on productions
 * the caller can see) so the same gaffer is one contact across productions.
 * Picking one fills the name and phone and remembers the contact id; typing on
 * clears the id again, so an edited name is a new person, never a silent rename.
 */
import { useEffect, useRef, useState } from "react";
import { api, type Connection } from "./api";
import type { ContactMatch } from "../types";

export function PersonPicker({ conn, id, value, onChange, onPick, disabled }: {
  conn: Connection; id: string; value: string; onChange: (name: string) => void; onPick: (c: ContactMatch) => void; disabled?: boolean;
}) {
  const [matches, setMatches] = useState<ContactMatch[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    const q = value.trim();
    if (q.length < 2 || !open) { setMatches([]); return; }
    timer.current = window.setTimeout(() => {
      api.searchContacts(conn, q).then(setMatches).catch(() => setMatches([]));
    }, 200);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [conn, value, open]);

  return (
    <div className="picker">
      <input id={id} value={value} disabled={disabled} autoComplete="off"
        onChange={(e) => { setOpen(true); onChange(e.target.value); }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)} />
      {open && matches.length > 0 && (
        <ul className="picker-list" role="listbox" aria-label="People already in FilmRunner">
          {matches.map((c) => (
            <li key={c.id} role="option" aria-selected={false}>
              <button type="button" className="picker-item" onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(c); setOpen(false); }}>
                <span className="name">{c.name}</span>
                <span className="meta">{c.phone ?? "no number"}{c.last_production_name ? ` · ${c.last_production_name}` : ""}{c.last_position ? ` · ${c.last_position}` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
