import { useId, useState, type ReactNode } from "react";

import { Icon } from "../Icon";
import { useL } from "./lang";

/**
 * A section heading whose explanation waits behind an "i". The screen shows state; how the app
 * works is one tap away. The text stays in the page while closed, so find-in-page and tests reach it.
 */
export function SectionHead({ title, about, aboutId, level = "h2" }: { title: ReactNode; about?: ReactNode; aboutId?: string; level?: "h2" | "h3" }) {
  const L = useL();
  const [open, setOpen] = useState(false);
  const generated = useId();
  const id = aboutId ?? generated;
  const Heading = level;
  if (!about) return <Heading>{title}</Heading>;
  return (
    <>
      <div className="section-head">
        <Heading>{title}</Heading>
        <button type="button" className="explain-toggle" aria-expanded={open} aria-controls={id} aria-label={L("How this works")} onClick={() => setOpen(!open)}>
          <Icon name="info" />
        </button>
      </div>
      <p className="hint explain" id={id} hidden={!open}>{about}</p>
    </>
  );
}

/** The same "i" for a place with no heading of its own, such as a folded panel. */
export function Explain({ id, children }: { id?: string; children: ReactNode }) {
  const L = useL();
  const [open, setOpen] = useState(false);
  const generated = useId();
  const target = id ?? generated;
  return (
    <>
      <button type="button" className="explain-toggle inline-explain" aria-expanded={open} aria-controls={target} aria-label={L("How this works")} onClick={() => setOpen(!open)}>
        <Icon name="info" />
      </button>
      <p className="hint explain" id={target} hidden={!open}>{children}</p>
    </>
  );
}
