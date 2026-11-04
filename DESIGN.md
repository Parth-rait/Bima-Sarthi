---
name: Bima Sarthi
description: Indigo dusk. Porcelain and lilac-mist surfaces, indigo-night ink for every word, one indigo action that turns saffron under the hand, and a sky-violet light (periwinkle, lavender, violet, saffron ember) that lives behind liquid glass.
colors:
  ivory: "#F8F6F2"
  peach: "#EEEAF4"
  peach-deep: "#E2DCEE"
  paper: "#FDFCFA"
  sky-blue: "#C9D4F2"
  sky-pale: "#E3E8F8"
  lavender: "#E6D9F5"
  dusty-rose: "#C6A3DB"
  apricot: "#E8873A"
  apricot-soft: "#F5C08E"
  gold: "#E0B36A"
  ink: "#1B1A33"
  ink-soft: "#4E4B66"
  ink-raised: "#2C2A52"
  action: "#34318A"
  action-deep: "#26246B"
  on-ink: "#F8F6F2"
  on-ink-soft: "#CFCBE3"
  line: "#E1DDEA"
  line-strong: "#77738F"
  terracotta: "#B5553F"
  terracotta-ink: "#8B3F2C"
  terracotta-wash: "#F6DFD6"
  amber-ink: "#6E4A0C"
  amber-wash: "#F6E4BD"
  sage: "#6F8F76"
  sage-ink: "#35553F"
  sage-wash: "#DDE9DE"
typography:
  display:
    fontFamily: "Fraunces, Noto Serif Devanagari, Georgia, serif"
    fontSize: "clamp(2.25rem, 1.25rem + 3.4vw, 4.25rem)"
    fontWeight: 500
    lineHeight: 1.06
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Fraunces, Noto Serif Devanagari, Georgia, serif"
    fontSize: "clamp(1.625rem, 1.2rem + 1.35vw, 2.375rem)"
    fontWeight: 500
    lineHeight: 1.16
  title:
    fontFamily: "Fraunces, Noto Serif Devanagari, Georgia, serif"
    fontSize: "clamp(1.1875rem, 1.1rem + 0.35vw, 1.4375rem)"
    fontWeight: 500
    lineHeight: 1.25
  body:
    fontFamily: "Source Sans 3, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "clamp(1rem, 0.96rem + 0.18vw, 1.125rem)"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Source Sans 3, Noto Sans Devanagari, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 700
    letterSpacing: "0.07em"
  quote:
    fontFamily: "Newsreader, Noto Serif Devanagari, Georgia, serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
rounded:
  control: "10px"
  card: "16px"
spacing:
  gutter: "16 / 24 / 40 / 64px"
  section: "clamp(4rem, 8vw, 8rem)"
  grid-gap: "clamp(1rem, 2.5vw, 2.5rem)"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.control}"
    padding: "8px 24px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.apricot}"
    textColor: "{colors.ink}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  button-on-ink:
    backgroundColor: "{colors.on-ink}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "44px"
  stamp-challengeable:
    backgroundColor: "{colors.terracotta-wash}"
    textColor: "{colors.terracotta-ink}"
  stamp-needinfo:
    backgroundColor: "{colors.amber-wash}"
    textColor: "{colors.amber-ink}"
  stamp-consistent:
    backgroundColor: "{colors.sage-wash}"
    textColor: "{colors.sage-ink}"
---

# Design System: Bima Sarthi

Source of truth in code: `frontend/src/styles/tokens.css` (a `@theme static` block for Tailwind utilities, layout tokens, temporary aliases, and the legacy variables the claim workflow still reads), `frontend/src/styles/layout.css` (bands, wraps, grid), and `frontend/src/design/atmosphere.ts` (every cloud, sky and lamp colour, in one file). Contrast is checked by `npm run contrast` and `src/test/contrast.test.ts`; the table below is that script's output (phase 3a).

## Indigo dusk (4 Nov 2026): what changed and why

Parth asked for a more dynamic, 3D, Apple-liquid-glass feel in the claim flow, a better logo and better colour combinations, and chose **Indigo dusk** and the **b/s glass monogram** from two short option sets. Token NAMES are unchanged (so every component kept working); their VALUES moved:

| Token | Was (sunset) | Now (indigo dusk) | Role |
|---|---|---|---|
| ivory | #FBF6EE | #F8F6F2 porcelain | the ground |
| peach | #F7E6D6 | #EEEAF4 lilac mist | second surface, header bands |
| ink | #2A2630 | #1B1A33 indigo night | every word, the ink band |
| action (new) | (ink) | #34318A indigo | the ONE primary fill: buttons, pressed toggles, step numbers, progress |
| apricot | #E9A87F | #E8873A saffron | primary hover/press, key highlights, the scan line |
| gold | #D9BE8A | #E0B36A marigold | hairlines and underlines |
| dusty-rose | #D9A9A6 | #C6A3DB violet | emphasis marks, gradients' far end |
| sky-blue / lavender | #BFD3E6 / #D9D2E6 | #C9D4F2 / #E6D9F5 | atmosphere only |

Verdict families (terracotta, amber, sage) are unchanged. The artwork SVGs were recoloured with the same map. The logo (`assets/art/mark.svg`, also the favicon) is a lowercase **b** with an **s** tucked behind it on a glass indigo tile with a saffron ember: original, no wheel or emblem.

**Where 3D and glass now live (this supersedes "no WebGL on Operate" below):**
- **The work stage** (`components/stage/`): while the claim flow is really waiting on the server (opening a session, reading the documents, saving answers, running the check), a liquid-glass panel shows a React Three Fiber scene of three glass sheets beside the steps of that request in words, the current one marked, and the real seconds elapsed. Reading = a saffron scan line lights each line; saving = the fan closes; checking = a glass lens steps down the lines, turning them indigo. Drag turns the file (fine pointers), the pointer tilts it. The canvas is aria-hidden decoration; the screen's own `role=status` line stays the announcement. three.js is a lazy chunk (about 270 KB gzipped) fetched when a file is chosen or the confirm screen opens; a CSS 3D version shows first and replaces it where WebGL is missing or the device is low-power; reduced motion gets one still frame. Colours and quality knobs: `STAGE` in `design/atmosphere.ts`. Nothing on it estimates progress.
- **The navbar**: a full-width bar at the top of a page; once scrolled it lifts into a floating glass capsule (header height unchanged, `--nav-h`), with a saffron-to-violet scroll hairline. A glass pill glides between links under the pointer (motion `layoutId`), a saffron bead marks the current page, and the mark leans toward the pointer with a band of light crossing it on each page change.
- **The claim page header**: the lilac band carries a slow violet/periwinkle/saffron light and one sheen on arrival.
- The sticky stepper and result summary plates are unchanged.

All new text pairs are in the contrast suite (glass capsule, stage column, header light); `npm run contrast` passes.

**Claim flow surfaces (`styles/claim.css`, loaded after operate.css; remove the import to undo):** the stepper is one glass capsule with an indigo pill that springs to the current step (no folder tabs); the sheet is a single liquid-glass surface over a slow lavender/periwinkle/saffron light (`.desk-light`); the drop area is one well with a 3D stack of pages that fans out on drag and a gradient ring that turns while something is over it; chosen files are chips; fact rows are open rows (hairline, hover wash, amber wash when pending), not cards inside a card. A step change crosses in the direction of travel (forward from the right, back from the left, 44px with an 8px blur; instant under reduced motion).

**Restored from the 4 Nov iteration (backup branch `backup/claude-frontend-2026-11-04`):** the backend (schemes, policy, evidence, corrected real-case winners, nine gallery cases) applied as a patch, and the Schemes ("Find schemes") and Evidence pages as new files, in this look. The rest of that iteration's UI was not brought back.

**Motion that explains (4 Nov, second pass; `styles/route.css`).** Four additions, each still and complete under reduced motion:
- *The deck and the tumble* (`components/flow/Tumble.tsx`): the claim sheet stands in front of two plates (the steps still to come). Going forward, a decorative copy of the outgoing sheet (cloned DOM, aria-hidden, inert, ids and names stripped) tips over its bottom edge and falls flat while the next sheet slides up to the line; going back, the copy recedes and the earlier sheet stands up from the floor. After Parth's "tumble deck" reference, without GSAP. No Web Animations API or reduced motion: no copy.
- *The one noticeable action* (`components/ds/Spark.tsx`): motion-primitives Magnetic + GlowEffect + BorderTrail (vendored in `components/ui/motion-primitives.tsx`, MIT) around the step's single primary button (upload, run the check, the landing CTAs). Glow and trail go dark while the button is disabled or busy. Colours are tokens.
- *The plan as a route* (`components/plan/RouteMap.tsx`): an ink plate over Parth's ring shader (ported to raw WebGL in `components/ui/shader-rings.tsx`, colours in `atmosphere.ts` RINGS) with one stop per plan step, a dashed saffron decision card in front of each step whose title is a condition (Ombudsman, larger claim), counted steps/decisions/quoted rules, and a porcelain marker (layoutId) that both follows the reader's scroll and jumps the page to a step's detail. The detailed steps below are joined by one rail. The map adds no information the plan does not hold.
- *The deadline chart* (`components/charts/DeadlineTimeline.tsx`, restored from the 4 Nov iteration): both windows on one date scale, dates written under each bar, today marked; bars grow in. Only drawn when the user entered their complaint date, like the dates themselves.

## Overview

**Creative North Star: "Late afternoon, with the window open"**

Someone has just read a hard letter at a table by a window. The light is low and warm; there are soft clouds outside. The interface should feel like that light: calm, generous, a little golden, never loud. Ivory and pale peach are the room; deep charcoal ink is the writing; the sky is only ever behind things.

Surfaces keep the phase-2 split (see PRODUCT.md):
- **Persuade** (the landing page): a full-bleed sky hero (the Aceternity CloudShader, or its CSS sunset), then full-width alternating bands. This is where atmosphere, parallax and glass live.
- **Read** (about, how it works, privacy, help): editorial pages, a pale peach-to-sky header, wide two-column compositions, running text capped at 68ch. `/how-it-works` is the one reading page with its own light (the Lamp) and the scroll Timeline.
- **Operate** (check claim, action plan, report): flat surfaces with restrained depth — a lifted sheet, a hairline, a soft shadow, motion that explains a change of state. Ink on ivory/paper, one action colour. No WebGL, no parallax. Glass appears only as a non-textual plate behind solid content (the sticky stepper, the result summary); every word is on an opaque surface.

It never borrows government or insurer identity (no emblem, no tricolour, no lion capital). The gold seal in the artwork is an abstract rosette.

**What was removed in 3a:** the strong burgundy, the dark plum "night" ground, cream-and-yellow brass, the double brass navbar rule, paper grain, the stacked-sheet effect, dashed and double borders, 3px corners. A test fails if any of the old hex values reappear in source or artwork.

## Colors

### Surfaces and text
- **Ivory** `#FBF6EE`: the ground. **Pale peach** `#F7E6D6`: the second surface (alternate bands, quiet panels); **Peach deep** `#F0D8C2` for hover/pressed on peach; **Paper** `#FFFCF7` for inputs and the very few cards.
- **Ink** `#2A2630`: ALL text, the primary action fill, the ink band. **Ink soft** `#5B5560`: secondary text. **On ink** `#FBF6EE` / **on-ink soft** `#D8CFC6`: text on the ink band.
- **Line** `#E2D8CC`: hairlines that separate groups (decorative). **Line strong** `#857A6D`: control borders and anything that carries meaning (3.9:1 or better).

### Atmosphere (backgrounds and hairlines only)
- **Sky blue** `#BFD3E6`, **Sky pale** `#DCE6F0`, **Lavender** `#D9D2E6`: the sky band and the hero. Never controls, never text colour.
- **Dusty rose** `#D9A9A6`: emphasis marks (timeline line, artwork). Never body-sized text.
- **Apricot** `#E9A87F` / **Apricot soft** `#F2C6A0`: the primary action's hover/pressed fill, selection, key highlights (the lamp light). Nothing else.
- **Gold (champagne)** `#D9BE8A`: hairlines and underlines (a 1px rule, the current-page underline, the lamp's thin line). Never a fill.

### State and verdict families (muted, never by colour alone)
- **CHALLENGEABLE**: terracotta family. Mark `#B5553F`, text `#8B3F2C` on wash `#F6DFD6`. Triangle + word + sentence.
- **NEED_INFO**: amber family. Text `#6E4A0C` on wash `#F6E4BD`. Circle-question + word + sentence.
- **CONSISTENT**: sage family. Mark `#6F8F76`, text `#35553F` on wash `#DDE9DE`. Square-tick + word + sentence.
- **Error**: terracotta (border `#B5553F`, text `#8B3F2C`). **Success**: sage. **Warning**: amber.

### Primary action colour: measured choice
Two candidates were measured. **Ink fill with ivory text: 13.76:1**, and a clear 9.6 to 13.8:1 edge against every band (ivory, peach, sky). **Apricot fill with ink text: 7.31:1**, and only 1.9:1 against ivory (the button would rely on its label alone to be found). The ink button wins on contrast and on legibility over atmosphere; apricot becomes its hover/pressed state (ink text on apricot 7.31:1), so the warm colour appears exactly when the visitor is about to act.

### Usage rules (enforced; see tests)
1. **Ivory and pale peach carry about 90% of every page.** The ink band is a single evening moment (the assessment section, the footer, the lamp). The sky band is atmosphere, used at the top and at the close.
2. **Ink for all text.** Secondary text is ink soft. Text on ink is on-ink. Nothing else is a text colour except the verdict/error inks.
3. **One primary action colour:** ink fill, ivory text; hover apricot. Apricot is used for nothing else but key highlights.
4. **Dusty rose** is emphasis and markers only.
5. **Lavender and sky blue** appear only inside atmospheric backgrounds, never on controls.
6. **Champagne gold** is a hairline or underline only.
7. **Verdicts carry shape + word + sentence.** Colour reinforces.
8. **Not:** bright yellow, burgundy-heavy, childish pastel, purple SaaS gradient, neon, green identity.
9. Text over any atmosphere sits on an **ivory scrim** (72% hero, 80% navbar top) and is measured against the darkest pixel the shader can produce.

### Contrast (WCAG 2.x AA, computed)

| Text / element | on | Colours | Ratio | Needs | Result |
|---|---|---|---|---|---|
| Body text and headings on the page (`color-ink`) | `color-ivory` | #1b1a33 on #f8f6f2 | 15.66:1 | 4.5:1 | pass |
| Text on a peach band (`color-ink`) | `color-peach` | #1b1a33 on #eeeaf4 | 14.26:1 | 4.5:1 | pass |
| Text on a card, typed input text (`color-ink`) | `color-paper` | #1b1a33 on #fdfcfa | 16.49:1 | 4.5:1 | pass |
| Hover on peach (accordion header, secondary button) (`color-ink`) | `color-peach-deep` | #1b1a33 on #e2dcee | 12.64:1 | 4.5:1 | pass |
| Text on the sky band (pale blue end) (`color-ink`) | `color-sky-pale` | #1b1a33 on #e3e8f8 | 13.82:1 | 4.5:1 | pass |
| Text on the sky band (deepest blue) (`color-ink`) | `color-sky-blue` | #1b1a33 on #c9d4f2 | 11.42:1 | 4.5:1 | pass |
| Text on the sky band's lavender breath (`color-ink`) | `color-lavender` | #1b1a33 on #e6d9f5 | 12.57:1 | 4.5:1 | pass |
| Primary button on hover (`color-ink`) | `color-apricot` | #1b1a33 on #e8873a | 6.41:1 | 4.5:1 | pass |
| Primary button pressed; selected text (`color-ink`) | `color-apricot-soft` | #1b1a33 on #f5c08e | 10.32:1 | 4.5:1 | pass |
| Button on the ink band (ivory fill) (`color-ink`) | `color-on-ink` | #1b1a33 on #f8f6f2 | 15.66:1 | 4.5:1 | pass |
| Primary button label (porcelain on indigo) (`color-on-ink`) | `color-action` | #f8f6f2 on #34318a | 9.97:1 | 4.5:1 | pass |
| Primary button label on its pressed edge (`color-on-ink`) | `color-action-deep` | #f8f6f2 on #26246b | 12.58:1 | 4.5:1 | pass |
| Secondary text on the page (`color-ink-soft`) | `color-ivory` | #4e4b66 on #f8f6f2 | 7.71:1 | 4.5:1 | pass |
| Secondary text on a peach band (`color-ink-soft`) | `color-peach` | #4e4b66 on #eeeaf4 | 7.02:1 | 4.5:1 | pass |
| Hints, placeholders, captions on a card or field (`color-ink-soft`) | `color-paper` | #4e4b66 on #fdfcfa | 8.12:1 | 4.5:1 | pass |
| Secondary text on the sky band (`color-ink-soft`) | `color-sky-pale` | #4e4b66 on #e3e8f8 | 6.81:1 | 4.5:1 | pass |
| Text on the ink band; primary button label (`color-on-ink`) | `color-ink` | #f8f6f2 on #1b1a33 | 15.66:1 | 4.5:1 | pass |
| Secondary text on the ink band (`color-on-ink-soft`) | `color-ink` | #cfcbe3 on #1b1a33 | 10.71:1 | 4.5:1 | pass |
| Text on a raised ink surface (`color-on-ink`) | `color-ink-raised` | #f8f6f2 on #2c2a52 | 12.47:1 | 4.5:1 | pass |
| Secondary text on a raised ink surface (`color-on-ink-soft`) | `color-ink-raised` | #cfcbe3 on #2c2a52 | 8.53:1 | 4.5:1 | pass |
| Field error text on the page (`color-terracotta-ink`) | `color-ivory` | #8b3f2c on #f8f6f2 | 6.84:1 | 4.5:1 | pass |
| Field error text on a card (`color-terracotta-ink`) | `color-paper` | #8b3f2c on #fdfcfa | 7.20:1 | 4.5:1 | pass |
| Error text on a peach band (`color-terracotta-ink`) | `color-peach` | #8b3f2c on #eeeaf4 | 6.22:1 | 4.5:1 | pass |
| CHALLENGEABLE stamp; error box (`color-terracotta-ink`) | `color-terracotta-wash` | #8b3f2c on #f6dfd6 | 5.78:1 | 4.5:1 | pass |
| NEED_INFO stamp; Please-confirm tag (`color-amber-ink`) | `color-amber-wash` | #6e4a0c on #f6e4bd | 6.33:1 | 4.5:1 | pass |
| Warm tag text on the page (`color-amber-ink`) | `color-ivory` | #6e4a0c on #f8f6f2 | 7.35:1 | 4.5:1 | pass |
| CONSISTENT stamp; the gate when it is clear (`color-sage-ink`) | `color-sage-wash` | #35553f on #dde9de | 6.65:1 | 4.5:1 | pass |
| Gate heading and count on the cleared band (`color-ink`) | `color-sage-wash` | #1b1a33 on #dde9de | 13.51:1 | 4.5:1 | pass |
| Gate caption on the cleared band (`color-ink-soft`) | `color-sage-wash` | #4e4b66 on #dde9de | 6.65:1 | 4.5:1 | pass |
| Body text inside an error box (`color-ink`) | `color-terracotta-wash` | #1b1a33 on #f6dfd6 | 13.24:1 | 4.5:1 | pass |
| Ink on the glass plate over a peach band (`color-ink`) | `color-ivory@0.74` | #1b1a33 on #f5f3f3 | 15.29:1 | 4.5:1 | pass |
| Ink on the glass plate over the paper sheet (`color-ink`) | `color-ivory@0.74` | #1b1a33 on #f9f8f4 | 15.91:1 | 4.5:1 | pass |
| Secondary ink on the glass plate over the paper sheet (`color-ink-soft`) | `color-ivory@0.74` | #4e4b66 on #f9f8f4 | 7.83:1 | 4.5:1 | pass |
| Floating navbar: ink on the capsule over the deepest sky (`color-ink`) | `color-ivory@0.74` | #1b1a33 on #ecedf2 | 14.46:1 | 4.5:1 | pass |
| Floating navbar: ink on the capsule over the ink band (`color-ink`) | `color-ivory@0.74` | #1b1a33 on #bfbdc0 | 9.06:1 | 4.5:1 | pass |
| Work stage: ink on the glass text column over the aurora (`color-ink`) | `color-paper@0.7` | #1b1a33 on #f6f2f9 | 15.29:1 | 4.5:1 | pass |
| Work stage: secondary ink on the glass text column (`color-ink-soft`) | `color-paper@0.7` | #4e4b66 on #f6f2f9 | 7.53:1 | 4.5:1 | pass |
| Work stage: secondary ink over the saffron bloom (`color-ink-soft`) | `color-paper@0.7` | #4e4b66 on #fbeada | 7.09:1 | 4.5:1 | pass |
| Claim page heading over the strongest violet of the header light (`color-ink`) | `color-lavender` | #1b1a33 on #e6d9f5 | 12.57:1 | 4.5:1 | pass |
| Claim page lead over the violet header light (`color-ink-soft`) | `color-lavender` | #4e4b66 on #e6d9f5 | 6.19:1 | 4.5:1 | pass |
| Claim page lead over the periwinkle header light (`color-ink-soft`) | `color-sky-blue@0.8` | #4e4b66 on #d0d8f2 | 5.86:1 | 4.5:1 | pass |
| Control borders on the page (`color-line-strong`) | `color-ivory` | #77738f on #f8f6f2 | 4.20:1 | 3:1 | pass |
| Input borders on a card (`color-line-strong`) | `color-paper` | #77738f on #fdfcfa | 4.42:1 | 3:1 | pass |
| Control borders on a peach band (`color-line-strong`) | `color-peach` | #77738f on #eeeaf4 | 3.82:1 | 3:1 | pass |
| Gate chip borders on the cleared band (`color-line-strong`) | `color-sage-wash` | #77738f on #dde9de | 3.62:1 | 3:1 | pass |
| Focus ring on the page (`color-focus-ring`) | `color-ivory` | #1b1a33 on #f8f6f2 | 15.66:1 | 3:1 | pass |
| Focus ring on a card (`color-focus-ring`) | `color-paper` | #1b1a33 on #fdfcfa | 16.49:1 | 3:1 | pass |
| Focus ring on a peach band (`color-focus-ring`) | `color-peach` | #1b1a33 on #eeeaf4 | 14.26:1 | 3:1 | pass |
| Focus ring on the sky band (`color-focus-ring`) | `color-sky-pale` | #1b1a33 on #e3e8f8 | 13.82:1 | 3:1 | pass |
| Focus ring over the deepest sky blue (`color-focus-ring`) | `color-sky-blue` | #1b1a33 on #c9d4f2 | 11.42:1 | 3:1 | pass |
| Focus ring on the ink band (`color-focus-ring-on-ink`) | `color-ink` | #f8f6f2 on #1b1a33 | 15.66:1 | 3:1 | pass |
| Error border and CHALLENGEABLE mark on the page (`color-terracotta`) | `color-ivory` | #b5553f on #f8f6f2 | 4.49:1 | 3:1 | pass |
| Error border on an input (`color-terracotta`) | `color-paper` | #b5553f on #fdfcfa | 4.72:1 | 3:1 | pass |
| Error border on a peach band (`color-terracotta`) | `color-peach` | #b5553f on #eeeaf4 | 4.08:1 | 3:1 | pass |
| Success mark on the page (`color-sage`) | `color-ivory` | #6f8f76 on #f8f6f2 | 3.32:1 | 3:1 | pass |
| Champagne hairline on the ink band (`color-gold`) | `color-ink` | #e0b36a on #1b1a33 | 8.72:1 | 3:1 | pass |
| Primary button edge on the page (`color-action`) | `color-ivory` | #34318a on #f8f6f2 | 9.97:1 | 3:1 | pass |
| Primary button edge on a mist band (`color-action`) | `color-peach` | #34318a on #eeeaf4 | 9.07:1 | 3:1 | pass |
| Primary button edge on a card (`color-action`) | `color-paper` | #34318a on #fdfcfa | 10.49:1 | 3:1 | pass |
| Primary button edge on the sky band (`color-ink`) | `color-sky-pale` | #1b1a33 on #e3e8f8 | 13.82:1 | 3:1 | pass |
| Primary button edge over the deepest sky blue (`color-ink`) | `color-sky-blue` | #1b1a33 on #c9d4f2 | 11.42:1 | 3:1 | pass |
| Ink directly on the darkest cloud shadow (#abadc1): reference only, the hero never relies on it (`color-ink`) | `#abadc1` | #1b1a33 on #abadc1 | 7.63:1 | 3:1 | pass |
| Hero headline, lead and links: ink on the ivory scrim over the darkest cloud (`color-ink`) | `color-ivory@0.72` | #1b1a33 on #e2e2e4 | 13.07:1 | 4.5:1 | pass |
| Transparent navbar over the sky: ink on the top ivory wash over the darkest cloud (`color-ink`) | `color-ivory@0.8` | #1b1a33 on #e9e7e8 | 13.73:1 | 4.5:1 | pass |
| Dev page captions: ink on an ivory/80 plate over the darkest cloud (`color-ink`) | `color-ivory@0.8` | #1b1a33 on #e9e7e8 | 13.73:1 | 4.5:1 | pass |
| Lamp heading: ivory over the lamp's widest glow at its set opacity (`color-on-ink`) | `#e8873a@0.3` | #f8f6f2 on #593b35 | 9.26:1 | 4.5:1 | pass |
| Lamp lead text: secondary ivory over the lamp's glow (`color-on-ink-soft`) | `#e8873a@0.3` | #cfcbe3 on #593b35 | 6.33:1 | 4.5:1 | pass |
| Glass chip text: ink plate at 90% over the lightest artwork (`color-on-ink`) | `color-ink@0.9` | #f8f6f2 on #313046 | 11.85:1 | 4.5:1 | pass |

## Typography

**Display / headings:** Fraunces 500 and 600 (and 500 italic) with Noto Serif Devanagari for Hindi, then Georgia. **Verbatim quotes:** Newsreader. **UI / body:** Source Sans 3 with Noto Sans Devanagari. **Identifiers:** IBM Plex Mono 400 (rule ids only). Self-hosted through `@fontsource`; nothing is fetched from a CDN.

Headings are no longer oversized: display `clamp(2.25rem, 1.25rem + 3.4vw, 4.25rem)` (landing hero only), H1 `clamp(2rem, 1.25rem + 2.3vw, 3.25rem)`, H2 `clamp(1.625rem, 1.2rem + 1.35vw, 2.375rem)`, H3 `clamp(1.1875rem, 1.1rem + 0.35vw, 1.4375rem)`; lead `clamp(1.0625rem, 1rem + 0.3vw, 1.25rem)`; body `clamp(1rem, 0.96rem + 0.18vw, 1.125rem)` (16 to 18px), 1.6 leading (Hindi 1.8). Running text is capped by `Prose` (68ch); headings are no longer capped at 20ch (26ch on page headers, 16 to 24ch inside columns so the lines balance).

Named rules: **One Voice** (serif for headings and verbatim evidence only), **Identifier** (mono only for rule ids), **No Eyebrow** (no small label above a heading; a step number is a numeral beside or above the heading and a screen-reader prefix inside it).

## Layout (`data-layout` system)

Root cause fixed in 3a: the old `Container` hard-coded `max-w-6xl` (1152px), the navbar did too, the claim sheet sat in a 56rem box, headings were capped at 20ch and paragraphs at 60ch, so a 1440px screen showed a 1152px column. Pages are now stacks of **bands** each holding a **wrap**.

| Primitive | File | Attributes | Meaning |
|---|---|---|---|
| `Band` | `ds/Section.tsx` | `data-layout="band"` `data-tone="ivory\|peach\|sky\|ink"` `data-pad="tight\|none"` | Full-bleed background, vertical rhythm `--section-y` (clamp 4rem, 8vw, 8rem); `tight` uses `--section-y-tight` |
| `Wrap` | `ds/Section.tsx` | `data-layout="wrap"` `data-wrap="wide\|default\|narrow"` | The content well: `width: min(well, 100% - 2 * gutter)` |
| `Prose` | `ds/Section.tsx` | `data-layout="prose"` | Running text, `max-width: 68ch` |
| `Grid12` | `ds/Section.tsx` | `data-layout="grid-12"` | 12 columns, gap `--grid-gap`; children span with `lg:col-span-6`, `lg:col-start-8` |

Tokens (`tokens.css`): `--wrap-wide` 90rem (1440px: navbar, heroes, editorial bands), `--wrap-default` 80rem (1280px: most content; the claim workflow's `.desk` now uses it through `--sheet-w`), `--wrap-narrow` 60rem (960px: forms and prose pages); `--gutter` 1rem / 1.5rem (>=640) / 2.5rem (>=1024) / 4rem (>=1536); `--measure-prose` 68ch; `--nav-h` 4.25rem.

Composition rules: alternate layouts (copy-left/art-right, then flipped); use hairlines (`border-t`) to separate groups instead of boxes; never nest boxes; use `Card` sparingly (one hairline, one soft shadow); no dashed borders; no coloured side borders. The navbar spans the full width (inner wrap `wide`); on the landing page it is transparent over the sky until scroll, with an ivory wash at the top of the hero so ink links stay readable.

Breakpoints: 640 (gutter 24, parallax tiles appear), 768, 1024 (full navbar, hero two columns, gutter 40), 1280 (draggable scenario desk), 1536 (gutter 64). Touch targets are at least 44px.

## Elevation & Depth

Depth is soft and warm: `shadow-sheet` (hairline + 32px blur), `shadow-float` (a plate that hovers over moving content), `shadow-lift`, `shadow-stage`, all in ink at low alpha, always with an offset. Glass is allowed in exactly three places, and only ever as a plate behind a solid surface: the landing hero's lens chip, the claim-flow stepper once it sticks under the navbar, and the result summary rail. Each one sits over a plain ivory or peach band — never over artwork, never over the sky shader — and every word on it is on an opaque paper plate. No paper grain, no stacked sheets.

## Shapes

`rounded-ctl` 10px for controls, `rounded-card` 16px for images and the few cards. Stamps share the control radius with a 2px border. Circles only for the NEED_INFO glyph and timeline nodes.

## Artwork

Original SVG in `frontend/src/assets/art`, recoloured in 3a to the sunset palette: `dossier-hero` (letter, schedule, paperclip, gold seal on a peach-and-sky desk), `scene-letter`, `scene-schedule`, `scene-folder`, `scene-timeline`, and two new motifs, `scene-medical` (a medical record sheet) and `scene-evidence` (a magnifier checking a quoted passage). No photographs, no stock imagery, no external URLs. Each use has alt text. A test fails if an old identity hex reappears in any SVG.

## Components

### Buttons (`ds/Button`)
`rounded-ctl`, 44px minimum, 600 weight. **Primary:** ink fill, on-ink text; hover/pressed apricot with ink text. **Secondary:** transparent, 1px ink border; hover peach-deep. **Quiet:** ink text, champagne underline. **Danger:** terracotta border and ink text (deletion only, behind a confirmation). **On ink / on ink quiet:** ivory fill / outline, for the ink band. States: hover, focus-visible (3px ink ring, ivory on the ink band), pressed (1px down), disabled (peach fill, `ink-soft` text, no shadow, `cursor-not-allowed` — never a hatch, never opacity below the 4.5:1 the contrast suite measures), loading (spinner, `aria-busy`).

### Navbar, mobile menu, footer
Navbar: full width, wrap `wide`, ink links with a champagne underline on the current page (`aria-current="page"`), an Explore disclosure, the language toggle, a primary "Check my claim", and under 1024px a Menu button opening an ivory full-screen modal dialog. Footer: the ink band, 12-column grid, both required notices on every page.

### Form controls, accordion, modal, toast, stepper, loader, states
Paper fill, 1px line-strong border, 44px, label above, hint, error below (terracotta border and ink-coloured text with the word). Accordion headers peach on hover. Dashed drop zones and dashed stepper steps are solid now.

### The gate (confirm screen)
The check refuses to run while facts need an answer; the gate says so before the button is pressed, not after. A sheet in the peach family: the count of answered items over the pending total in `--text-h2` tabular numerals, then one chip per unanswered item — paper fill, line-strong border, the fact's own label and a `→`, each a real `#fact-<key>` link that focuses the row and rings it with `:target`. When nothing is left it becomes the sage family and states that everything has an answer. The count and the run guard read the same predicate (`unresolvedKeys`), so they cannot disagree. A row answered here but not yet sent keeps its pending state and loses the amber: neutral tag "Answered, not saved yet" (`tag-ans`: paper, ink-soft, line-strong).

### The plan rail (`/action-plan`, 64rem and up)
A sticky column of section links, the current one on a solid paper plate with a line-strong edge. It is deliberately **not** glass — the blurred plate is permitted in exactly two places (the sticky stepper, the result summary) and a long report is not a third. Below 64rem it becomes a wrapping chip row above the content. Links are jumps (`#ap-what` … `#ap-not`), each section carries `scroll-margin-block-start` so it lands under the navbar.

### Quote slip and verdict stamp (signature)
Quote slip: pale peach panel, serif text, caption with rule and page. Verdict stamp: shape + word + sentence, 2px border, muted wash (families above).

## Aceternity components (nine installed)

All real registry source (`npx shadcn@latest add @aceternity/<name>`, components alias set to `@/components/ui`), pristine copies and their demos in `frontend/vendor/aceternity-originals/*.tsx.txt`. Every one is lazy-loaded (React.lazy + Suspense + `Boundary` fallback) except the Lamp on `/how-it-works` (the route is already a lazy chunk and the page `<h1>` lives inside the lamp so route focus finds it). Showcase and verification page: `/dev/components`.

| Component | Used on | Deviations from the registry original |
|---|---|---|
| `ParallaxHeroImages` | landing hero | `alts` prop (real alt text; original `alt=""`); `positions` prop (choose slots); pointer parallax disabled on touch/coarse pointers and reduced motion; blur-in skipped under reduced motion; `rounded-lg ring-black/10 dark:` classes use tokens; unused imports removed |
| `FileUpload` (+ `GridPattern`) | dev page now; claim flow in 3b | keyboard operable (`role=button`, `tabIndex 0`, Enter/Space, focus ring), accessible names; English strings are props (`title`, `hint`, `dropLabel`); `accept`, `multiple` forwarded; white/neutral/dark: classes to tokens; dashed sky-blue ghost box to a solid ink hairline; `console.log` on rejection removed; input id via `useId`. API: `<FileUpload onChange={(files: File[]) => ...} />`, `onChange` receives the newly added files |
| `LampContainer` | `/how-it-works` intro | cyan to sunlight: colours from `LAMP` in `atmosphere.ts`; conic gradients written out explicitly (Tailwind v4 has no `bg-gradient-conic`); `LampDemo` (gradient-text example heading) removed; reduced motion shows the final beam widths; layers `aria-hidden` |
| `Timeline` | `/how-it-works` | `heading`/`description` props instead of the hard-coded changelog text; tokens instead of white/neutral/dark:; purple-blue line to apricot-rose (`TIMELINE`); line height re-measured with `ResizeObserver`; reduced motion draws the line full; `number` and `id` entry fields; titles in the display serif. Scroll progress (`useScroll`, offset `["start 10%", "end 50%"]`) unchanged |
| `CloudShader` | landing hero, `/dev/components` | fragment shader byte-identical (a test checks it). Added: `renderScale`, `maxFps`, `maxDpr` (cap 1.5 vs 2), `onUnavailable` (WebGL missing, compile or link failure, context lost); the loop runs only while on screen (`IntersectionObserver`) and while the tab is visible; reduced motion draws one still frame; canvas `aria-hidden` |
| `LiquidGlass`, `ChromaticImage`, `Carousel`, `DraggableCard` | unchanged from phase 2 (see docs/FRONTEND_PHASE2_PLAN.md section 12) | `ChromaticImage` background default is now peach; `ArtworkImage` accepts `plain` to force the still image |

No component contains `innerHTML`/`dangerouslySetInnerHTML` (a test scans all of `src`).

### Atmosphere and performance (tuning knobs: `frontend/src/design/atmosphere.ts`)
- `SKY`: `cloudColor`, `skyTopColor`, `skyBottomColor`, `speed`, `count`, `renderScale` (0.6), `maxFps` (30), `maxDpr` (1.5). `SKY_STATIC`: the CSS fallback (sun, lavender band, cloud banks). `SCRIM`: ivory wash strengths. `LAMP`: background, beam, glow, glowOpacity, core, line. `TIMELINE`: progress line colours.
- The contrast script reads this file, so a tuned colour is re-checked automatically (darkest cloud shadow under the scrim; lamp heading over the glow).
- **Fallback ladder:** no WebGL, shader failure or low-power device (`hardwareConcurrency <= 4` or `deviceMemory <= 4`, unless the visitor opted in) show the static CSS sunset. The "Animate the sky" toggle (`aria-pressed`, EN/HI) persists in `localStorage` key `bimasarthi.sky` (try/catch everywhere; the only thing the app stores; disclosed on the Privacy page). Reduced motion: one still shader frame, no toggle, no parallax, no hero art animation.

## Motion

- **Landing:** the sky drifts (30fps cap, paused off-screen and in hidden tabs); the hero art responds to the pointer on non-touch devices; later sections ease in through pure CSS `animation-timeline: view()` where supported (content is visible without it).
- **How it works:** the lamp beams widen once when the section enters; the timeline line fills with scroll. Both are decoration: all content is visible without them.
- **Operate (the claim flow):** motion marks a change of state and nothing else. The sheet is placed (`sheet-rise`, 380ms); a step replaces a step — the new screen arrives from 18px below while the old one is simply gone, so no two gated steps are ever in the DOM at once; rows settle into reading order (`row-settle`, 240ms, 45ms apart, capped at the eighth row); the verdict stamp is pressed (`stamp-press`); the stepper sticks under the navbar and condenses behind its glass plate; a drop area answers a drag with border, wash and 0.4% scale. Timings are tokens (`--dur-1/2/3`), the easing is `cubic-bezier(.16,1,.3,1)`, and rows take their position from `--i` (`lib/motion.ts`).
- **Feedback:** 140ms colour change, 1px press.
- `prefers-reduced-motion: reduce`: all CSS animation and transition durations collapse to 0.01ms; the flow's step change becomes an instant swap with the focus move intact; no parallax, no blur-in, one still sky frame, static timeline line, beams at full width, chromatic image replaced by the still, no dragging.

## Temporary aliases (for agent 3b to delete)

Old token names still resolve (to new values) so unported pages work. Delete each when `grep -rn "<name>" frontend/src` finds nothing, then delete the block in `tokens.css`.
- Tailwind colours in `@theme`: `night`, `night-soft`, `wine`, `wine-deep`, `cream`, `champagne` (now peach!), `parchment`, `chalk`, `ground`, `slip`, `brass`, `brass-light`, `brass-ink`, `mist`, `ink-body`, `on-night`, `on-night-soft`, `wash-rose`, `wash-brass`, `stamp-challengeable-fg|bg`, `stamp-needinfo-fg|bg`, `stamp-consistent-fg|bg`, `focus-ring-night`.
- Legacy CSS variables in `:root` (read by `workflow.css`, which 3b deletes with the screens): `--plum --oxblood --burgundy --aubergine --lavender-grey --smoky-grey --parchment-antique --parchment-warm --tan --rose --chalk --cream --brass --wine --ground --paper --field --panel --pending --ink --ink-heading --ink-soft --ink-on-dark --ink-on-dark-soft --brass-ink --line-strong --rule --color-panel --color-field --color-pending --color-text --color-text-soft --color-heading --color-primary --color-primary-hover --color-on-primary --color-emphasis --color-error-bg --color-focus --color-focus-on-dark --color-accent --verdict-*-fg|bg --grain --sheet-w`.
- Components: `Container` and `Section` (legacy API of `ds/Section.tsx`; use `Band` + `Wrap`), `Button` variants `onNight` / `onNightQuiet` (use `onInk` / `onInkQuiet`), `Tag tone="brass"` (use `warm`), `Card tone="night"` (use `ink`), `Seg tone="night"` (use `ink`), `.wf .desk`/`.sheet` styles.

## Do's and Don'ts

### Do:
- **Do** keep each verdict as shape + word + sentence, with the rule quote and page directly beneath it.
- **Do** show a date only when the user entered it or the plan returns it.
- **Do** put the independent-project line and the rules-check line in every footer, and "powered by IKanoon" wherever judgment data appears.
- **Do** label every illustrative scenario "Illustrative" and every real case with its citation.
- **Do** give every draggable or hover-revealed thing a non-drag, non-hover equivalent.
- **Do** keep controls at 44px and every text pair at 4.5:1 (re-run `npm run contrast` after any token or atmosphere change).
- **Do** let Hindi take more leading than English, and mark Hindi drafts (Q-007).
- **Do** use bands, columns and hairlines to organise a page; reach for a Card last.

### Don't:
- **Don't** use bright yellow, burgundy, neon, a purple gradient, gradient text, or decorative glass. Glass is structural only: a plate that separates a floating surface from the content moving under it (the three places above), never behind text and never for looks.
- **Don't** use apricot, gold, rose, lavender or sky blue as text or as a control colour (apricot only as the primary hover and key highlight).
- **Don't** put a coloured `border-left`/`border-right` above 1px on any card, callout or list item, or use dashed or double borders.
- **Don't** nest boxes, or build a page from rows of same-sized icon-heading-text cards.
- **Don't** put an eyebrow label above a heading.
- **Don't** use `innerHTML`, `dangerouslySetInnerHTML` or any HTML-string rendering.
- **Don't** add a seal, emblem, tricolour or anything resembling IRDAI, LIC or an insurer.
- **Don't** load fonts, scripts, images or styles from an external host, or use stock photos.
- **Don't** put CloudShader behind forms or dense text, or show fake progress.
- **Don't** let the future companion (AUREL) read facts, quotes or documents, or autoplay anything.
