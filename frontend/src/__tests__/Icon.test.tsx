import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Icon, ICON_NAMES } from "../Icon";

// Every glyph in the app comes from this one component (FR-82: an icon that leaks into
// a control's accessible name reintroduces the exact label/content mismatch that shift fixed).
// Iterating ICON_NAMES (a runtime mirror of PATHS, not a hand-copied list) means a future
// icon added to PATHS is covered automatically, without anyone having to remember this file.
describe("Icon", () => {
  it("declares at least the icons the app is known to use today", () => {
    expect(ICON_NAMES.length).toBeGreaterThanOrEqual(12);
  });

  it.each(ICON_NAMES)("renders %s as a decorative SVG with no visible text", (name) => {
    const markup = renderToStaticMarkup(<Icon name={name} />);
    expect(markup).toMatch(/^<svg\b/);
    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain('focusable="false"');
    // Strip every tag; anything left over would be a visible text node inside the icon,
    // which axe would count toward the control's accessible name (the FR-82 bug class).
    const textContent = markup.replace(/<[^>]*>/g, "").trim();
    expect(textContent).toBe("");
  });
});
