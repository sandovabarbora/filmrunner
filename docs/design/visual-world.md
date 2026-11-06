# Visual world

The root `DESIGN.md` describes the data model, so the visual decisions live here.

**Idea.** A film still with the person's time as its title.

| Element | Rule |
|---|---|
| Ground | `--paper` `#0a0e11`; text `--ink` `#f5f7f7`, secondary `--ink-2`, `--muted` |
| Typeface | Archivo only, self-hosted and cut down to 57 KB. The time uses weight 800 and width 125% |
| Revision colour | Only on the REV label and the confirm action, text always `--on-rev`, and the letter is always written |
| Still | One per day, `frontend/public/stills/`, graded down to the ground. Generated, never presented as a real location |
| Viewfinder corners | Once, around the still on the first screen |
| Below the first screen | Titled sections separated by rules; no boxes |
| Editor | Same ground and colours, no still |
| Print | Black on white, no still, nothing depends on colour |

The landing and privacy pages still use the previous look.

Where a screen needs a decision, the person's own time and place win. See `PRODUCT.md`.

## Rebuilding the font

`frontend/src/fonts/` holds two files made with fontTools from `@fontsource-variable/archivo`: `varLib.instancer` limits `wght` to 400:800 and `wdth` to 100:125, then `subset` keeps Latin-1 and common punctuation in `archivo-latin.woff2`, and the Czech letters in `archivo-czech.woff2`, without hinting. A new weight, width or alphabet needs a rebuild, or the browser falls back to a system font for those characters.
