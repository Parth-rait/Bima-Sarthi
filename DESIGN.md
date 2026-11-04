---
name: Bima Sarthi
description: Late-afternoon sky with sunlight through soft clouds. Warm ivory and pale peach carry the page, deep charcoal ink carries every word, one calm action colour, and the atmosphere (sky blue, lavender, dusty rose, apricot, champagne) lives in backgrounds and hairlines only.
colors:
  ivory: "#FBF6EE"
  peach: "#F7E6D6"
  peach-deep: "#F0D8C2"
  paper: "#FFFCF7"
  sky-blue: "#BFD3E6"
  sky-pale: "#DCE6F0"
  lavender: "#D9D2E6"
  dusty-rose: "#D9A9A6"
  apricot: "#E9A87F"
  apricot-soft: "#F2C6A0"
  gold: "#D9BE8A"
  ink: "#2A2630"
  ink-soft: "#5B5560"
  ink-raised: "#3A3541"
  on-ink: "#FBF6EE"
  on-ink-soft: "#D8CFC6"
  line: "#E2D8CC"
  line-strong: "#857A6D"
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
    backgroundColor: "{colors.ink}"
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
| Body text and headings on the page (`color-ink`) | `color-ivory` | #2a2630 on #fbf6ee | 13.76:1 | 4.5:1 | pass |
| Text on a peach band (`color-ink`) | `color-peach` | #2a2630 on #f7e6d6 | 12.16:1 | 4.5:1 | pass |
| Text on a card, typed input text (`color-ink`) | `color-paper` | #2a2630 on #fffcf7 | 14.47:1 | 4.5:1 | pass |
| Hover on peach (accordion header, secondary button) (`color-ink`) | `color-peach-deep` | #2a2630 on #f0d8c2 | 10.79:1 | 4.5:1 | pass |
| Text on the sky band (pale blue end) (`color-ink`) | `color-sky-pale` | #2a2630 on #dce6f0 | 11.72:1 | 4.5:1 | pass |
| Text on the sky band (deepest blue) (`color-ink`) | `color-sky-blue` | #2a2630 on #bfd3e6 | 9.64:1 | 4.5:1 | pass |
| Text on the sky band's lavender breath (`color-ink`) | `color-lavender` | #2a2630 on #d9d2e6 | 10.09:1 | 4.5:1 | pass |
| Primary button on hover (`color-ink`) | `color-apricot` | #2a2630 on #e9a87f | 7.31:1 | 4.5:1 | pass |
| Primary button pressed; selected text (`color-ink`) | `color-apricot-soft` | #2a2630 on #f2c6a0 | 9.42:1 | 4.5:1 | pass |
| Button on the ink band (ivory fill) (`color-ink`) | `color-on-ink` | #2a2630 on #fbf6ee | 13.76:1 | 4.5:1 | pass |
| Secondary text on the page (`color-ink-soft`) | `color-ivory` | #5b5560 on #fbf6ee | 6.70:1 | 4.5:1 | pass |
| Secondary text on a peach band (`color-ink-soft`) | `color-peach` | #5b5560 on #f7e6d6 | 5.92:1 | 4.5:1 | pass |
| Hints, placeholders, captions on a card or field (`color-ink-soft`) | `color-paper` | #5b5560 on #fffcf7 | 7.04:1 | 4.5:1 | pass |
| Secondary text on the sky band (`color-ink-soft`) | `color-sky-pale` | #5b5560 on #dce6f0 | 5.71:1 | 4.5:1 | pass |
| Text on the ink band; primary button label (`color-on-ink`) | `color-ink` | #fbf6ee on #2a2630 | 13.76:1 | 4.5:1 | pass |
| Secondary text on the ink band (`color-on-ink-soft`) | `color-ink` | #d8cfc6 on #2a2630 | 9.63:1 | 4.5:1 | pass |
| Text on a raised ink surface (`color-on-ink`) | `color-ink-raised` | #fbf6ee on #3a3541 | 11.06:1 | 4.5:1 | pass |
| Secondary text on a raised ink surface (`color-on-ink-soft`) | `color-ink-raised` | #d8cfc6 on #3a3541 | 7.74:1 | 4.5:1 | pass |
| Field error text on the page (`color-terracotta-ink`) | `color-ivory` | #8b3f2c on #fbf6ee | 6.86:1 | 4.5:1 | pass |
| Field error text on a card (`color-terracotta-ink`) | `color-paper` | #8b3f2c on #fffcf7 | 7.21:1 | 4.5:1 | pass |
| Error text on a peach band (`color-terracotta-ink`) | `color-peach` | #8b3f2c on #f7e6d6 | 6.06:1 | 4.5:1 | pass |
| CHALLENGEABLE stamp; error box (`color-terracotta-ink`) | `color-terracotta-wash` | #8b3f2c on #f6dfd6 | 5.78:1 | 4.5:1 | pass |
| NEED_INFO stamp; Please-confirm tag (`color-amber-ink`) | `color-amber-wash` | #6e4a0c on #f6e4bd | 6.33:1 | 4.5:1 | pass |
| Warm tag text on the page (`color-amber-ink`) | `color-ivory` | #6e4a0c on #fbf6ee | 7.37:1 | 4.5:1 | pass |
| CONSISTENT stamp (`color-sage-ink`) | `color-sage-wash` | #35553f on #dde9de | 6.65:1 | 4.5:1 | pass |
| Body text inside an error box (`color-ink`) | `color-terracotta-wash` | #2a2630 on #f6dfd6 | 11.59:1 | 4.5:1 | pass |
| Control borders on the page (`color-line-strong`) | `color-ivory` | #857a6d on #fbf6ee | 3.90:1 | 3:1 | pass |
| Input borders on a card (`color-line-strong`) | `color-paper` | #857a6d on #fffcf7 | 4.10:1 | 3:1 | pass |
| Control borders on a peach band (`color-line-strong`) | `color-peach` | #857a6d on #f7e6d6 | 3.45:1 | 3:1 | pass |
| Focus ring on the page (`color-focus-ring`) | `color-ivory` | #2a2630 on #fbf6ee | 13.76:1 | 3:1 | pass |
| Focus ring on a card (`color-focus-ring`) | `color-paper` | #2a2630 on #fffcf7 | 14.47:1 | 3:1 | pass |
| Focus ring on a peach band (`color-focus-ring`) | `color-peach` | #2a2630 on #f7e6d6 | 12.16:1 | 3:1 | pass |
| Focus ring on the sky band (`color-focus-ring`) | `color-sky-pale` | #2a2630 on #dce6f0 | 11.72:1 | 3:1 | pass |
| Focus ring over the deepest sky blue (`color-focus-ring`) | `color-sky-blue` | #2a2630 on #bfd3e6 | 9.64:1 | 3:1 | pass |
| Focus ring on the ink band (`color-focus-ring-on-ink`) | `color-ink` | #fbf6ee on #2a2630 | 13.76:1 | 3:1 | pass |
| Error border and CHALLENGEABLE mark on the page (`color-terracotta`) | `color-ivory` | #b5553f on #fbf6ee | 4.50:1 | 3:1 | pass |
| Error border on an input (`color-terracotta`) | `color-paper` | #b5553f on #fffcf7 | 4.73:1 | 3:1 | pass |
| Error border on a peach band (`color-terracotta`) | `color-peach` | #b5553f on #f7e6d6 | 3.98:1 | 3:1 | pass |
| Success mark on the page (`color-sage`) | `color-ivory` | #6f8f76 on #fbf6ee | 3.33:1 | 3:1 | pass |
| Champagne hairline on the ink band (`color-gold`) | `color-ink` | #d9be8a on #2a2630 | 8.24:1 | 3:1 | pass |
| Primary button edge on the sky band (`color-ink`) | `color-sky-pale` | #2a2630 on #dce6f0 | 11.72:1 | 3:1 | pass |
| Primary button edge over the deepest sky blue (`color-ink`) | `color-sky-blue` | #2a2630 on #bfd3e6 | 9.64:1 | 3:1 | pass |
| Ink directly on the darkest cloud shadow (#b0aaa9): reference only, the hero never relies on it (`color-ink`) | `#b0aaa9` | #2a2630 on #b0aaa9 | 6.46:1 | 3:1 | pass |
| Hero headline, lead and links: ink on the ivory scrim over the darkest cloud (`color-ink`) | `color-ivory@0.72` | #2a2630 on #e6e1db | 11.39:1 | 4.5:1 | pass |
| Transparent navbar over the sky: ink on the top ivory wash over the darkest cloud (`color-ink`) | `color-ivory@0.8` | #2a2630 on #ece7e0 | 12.04:1 | 4.5:1 | pass |
| Dev page captions: ink on an ivory/80 plate over the darkest cloud (`color-ink`) | `color-ivory@0.8` | #2a2630 on #ece7e0 | 12.04:1 | 4.5:1 | pass |
| Lamp heading: ivory over the lamp's widest glow at its set opacity (`color-on-ink`) | `#e9a87f@0.35` | #fbf6ee on #6d544c | 6.46:1 | 4.5:1 | pass |
| Lamp lead text: secondary ivory over the lamp's glow (`color-on-ink-soft`) | `#e9a87f@0.35` | #d8cfc6 on #6d544c | 4.52:1 | 4.5:1 | pass |
| Glass chip text: ink plate at 90% over the lightest artwork (`color-on-ink`) | `color-ink@0.9` | #fbf6ee on #3f3b43 | 10.18:1 | 4.5:1 | pass |

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
`rounded-ctl`, 44px minimum, 600 weight. **Primary:** ink fill, on-ink text; hover/pressed apricot with ink text. **Secondary:** transparent, 1px ink border; hover peach-deep. **Quiet:** ink text, champagne underline. **Danger:** terracotta border and ink text (deletion only, behind a confirmation). **On ink / on ink quiet:** ivory fill / outline, for the ink band. States: hover, focus-visible (3px ink ring, ivory on the ink band), pressed (1px down), disabled (dimmed and hatched), loading (spinner, `aria-busy`).

### Navbar, mobile menu, footer
Navbar: full width, wrap `wide`, ink links with a champagne underline on the current page (`aria-current="page"`), an Explore disclosure, the language toggle, a primary "Check my claim", and under 1024px a Menu button opening an ivory full-screen modal dialog. Footer: the ink band, 12-column grid, both required notices on every page.

### Form controls, accordion, modal, toast, stepper, loader, states
Paper fill, 1px line-strong border, 44px, label above, hint, error below (terracotta border and ink-coloured text with the word). Accordion headers peach on hover. Dashed drop zones and dashed stepper steps are solid now.

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
