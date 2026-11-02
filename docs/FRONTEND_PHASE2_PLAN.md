# Frontend phase 2: plan (audit, components, design system, pages)

Date: 2 Nov 2026. Scope: STAGES 1-6 of the phase-2 brief (audit, install four Aceternity components, design system, landing page, static pages, shell and routing). The claim workflow is only re-hosted and restyled here; porting it into the new design and integration is STAGE 7+ (a later agent). No Python, test under `tests/`, rule card, GROUND_TRUTH value, `main.py` or `sarthi/app/static/index.html` was changed.

Words used for scope: **deviation** = a place where what shipped differs from the brief or from an Aceternity original. Every deviation is listed in section 12.

## 1. Current architecture (before this phase)

- React 19.3.1 + TypeScript 7 + Vite 8, one screen at a time, no router. State: one `SessionProvider` (reducer in `src/state/session.ts`, actions in `src/state/store.tsx`), the view is a field of that state (`upload | confirm | result | gallery | deleted`).
- API client `src/api/client.ts` (typed errors, `ApiError.kind`), all text through `src/i18n` (EN dictionary + draft HI dictionary, helper-mode overrides). Verdict vocabulary is fixed (`CONSISTENT | CHALLENGEABLE | NEED_INFO`).
- Styles: hand-written CSS (`tokens.css`, `base.css`, `components.css`, `print.css`) with global element selectors (`button`, `label`, `h2`, `p`...). Tokens are read by `scripts/contrast-lib.mjs`, which feeds `src/test/contrast.test.ts` and the table in DESIGN.md.
- Tests: 8 files, 140 tests (flow, screens, i18n parity, contrast, static "no innerHTML / no CDN / reduced motion", API, activity).
- Backend (`sarthi/app/main.py`) already serves `frontend/dist/index.html` for `/`, `/about`, `/how-it-works`, `/check-claim`, `/action-plan`, `/cases`, `/privacy`, `/help`, `/dev/components`, `/results/{id}` and `/assets/*`. **It serves no other static path**, so images and any extra file must live under `dist/assets` (see deviation D1). There is no `/404` page route: an unknown path gets the API's own 404, so the in-app 404 page is reached only by client navigation.
- Session facts (verified in `sarthi/app/session.py` and `main.py`): uploads live under the session root (default `/tmp/sarthi`, never `data/`), are deleted after the check (`st["session"].delete()`), or by the sweeper after 1 hour (`SESSION_TTL_S = 3600`, sweep every 300 s). Limits: JPG/PNG/PDF only, 25 MB total, 20 pages total, images up to 40 megapixels. Reader and explain model calls use `cache=False`. Results live only in server memory. There are **no persisted reports**.

## 2. Compatibility of the four components with the current setup

Aceternity components are shadcn registry items: TSX that imports `cn` from `@/lib/utils`, uses Tailwind utility classes, and (carousel, draggable card) `motion/react` and `@tabler/icons-react`.

| Requirement | State before | What changed |
|---|---|---|
| Tailwind CSS v4 | absent | `tailwindcss` + `@tailwindcss/vite` 4.3.3, `@import "tailwindcss"` in `src/styles/index.css` |
| Path alias `@/*` | absent | `vite.config.ts` `resolve.alias`, `tsconfig.json` `paths` |
| shadcn `components.json` | absent | written by hand (`style new-york`, `tailwind.css = src/styles/index.css`, `iconLibrary tabler`, `@aceternity` registry URL). `shadcn init` was not run because it rewrites the CSS file |
| `cn()` | absent | `src/lib/utils.ts` (`clsx` + `tailwind-merge`) |
| `motion/react` | absent | `motion` 14.9.0 (draggable card, and our own drag wrapper) |
| `@tabler/icons-react` | absent | 3.50.0 (carousel arrows) |
| Preflight vs the old CSS | n/a | Tailwind v4 puts preflight in `@layer base`. The old CSS is un-layered, so it would **beat every utility class**. Fix: the old CSS moves into `@layer legacy` (ordered below `utilities`), and its global element selectors are scoped under a `.wf` wrapper so the new pages are not styled by them (section 4) |
| `dangerouslySetInnerHTML` | forbidden by project rule and by `static.test.ts` | the real LiquidGlass source injects its SVG filter with it; replaced with the same SVG rendered as JSX (D3) |
| React 19 types | `useRef<number>()` fails strict mode | one-line fix in carousel (D4) |

## 3. Dependencies (exact versions, licences)

| Package | Version | Licence | Why |
|---|---|---|---|
| tailwindcss, @tailwindcss/vite | 4.3.3 | MIT | utility CSS, `@theme` tokens |
| motion | 14.9.0 | MIT | draggable card, drag wrapper, reduced-motion hook |
| react-router | 8.5.1 | MIT | routes (`BrowserRouter`, `Routes`, `NavLink`) |
| clsx / tailwind-merge | 2.1.1 / 3.7.0 | MIT | `cn()` |
| class-variance-authority | 0.7.1 | Apache-2.0 | button/badge variants |
| @tabler/icons-react | 3.50.0 | MIT | carousel arrows (the real source imports it) and nav icons |
| @fontsource/fraunces | 5.3.0 | OFL-1.1 | expressive display serif (new) |
| @fontsource/ibm-plex-mono | 5.3.0 | OFL-1.1 | restrained mono for metadata (new) |
| (kept) newsreader, source-sans-3, noto-sans/serif-devanagari | unchanged | OFL-1.1 | quote slips, UI, Hindi |

Aceternity UI components: MIT (author Manu Arora, from the registry JSON). `shadcn` CLI 4.23.0 was run with `npx --yes` and is not a dependency. Add these rows to `LICENSES.md` at the next commit (Parth owns commits).

## 4. Architecture decisions

1. **Two style worlds, one stylesheet.** `src/styles/index.css` declares `@layer theme, base, legacy, components, utilities;`. New code uses Tailwind utilities and the `ds/` components. The workflow screens keep their hand-written CSS in `src/styles/workflow.css`, every selector prefixed with `.wf` and placed in `@layer legacy`, so they render the same inside the new shell and cannot leak into the new pages. Tokens: one `tokens.css` with a `@theme static` block (new palette, fonts, shadows, easing) plus the legacy variable names re-pointed at the deepened palette.
2. **Folder layout.** `src/components/ui/` = the four installed Aceternity files exactly where the registry puts them. `src/components/ds/` = our design system. `src/components/layout/` = Navbar, MobileMenu, Footer. `src/pages/` = one lazy-loaded file per route. `src/app/` = routes, shell, route effects, splash. `src/content/` = editorial copy as typed data. `src/assets/art/` = original SVG artwork.
3. **Routing.** `BrowserRouter` in `main.tsx`; `SessionProvider` sits above it, so the claim session survives navigation between pages (in memory only; a reload starts over, which is also what the privacy page says). Every page is `React.lazy`. A `RouteEffects` component sets the document title, announces the page, moves focus to the page `h1` on navigation (not on first load), restores scroll on back/forward, and scrolls to `#hash` targets.
4. **Report id.** `/results/:id` uses a random client-side `reportId` created when a check completes, **not** the server session id (the session id is a bearer capability and must not sit in URLs or history). The page renders only when `id === state.reportId` and a result exists; otherwise the expired state.
5. **Lazy WebGL / 3D.** `ChromaticImage`, `LiquidGlass`, `Carousel`, `DraggableCard` are imported only through `React.lazy` wrappers with `Suspense` fallbacks that are plain `<img>`/static markup. No WebGL at all on pages that do not use it.
6. **Splash.** A status overlay shown only while the app is really initialising (`document.fonts.load` for the display and UI faces, plus `GET /health`), only if that takes longer than 150 ms, removed the moment both settle. A failed health check does not block: the app opens and `/check-claim` shows a retry notice.
7. **Motion.** One authored moment per surface; everything visible without animation; `prefers-reduced-motion: reduce` disables transitions, parallax, pointer tilt (`ChromaticImage` already does), glass dragging and the carousel's idle loop.

## 5. Sitemap

```
/                  Landing (persuade)
/about             What Bima Sarthi is and is not
/how-it-works      Six stages
/check-claim       The working claim flow (upload > confirm > result)   [workflow re-hosted]
/action-plan       Next-steps plan from the current session
/cases             Verified real cases (GET /gallery) + illustrative scenarios
/privacy           What is and is not stored
/help              Accordions, search, terminology
/results/:id       Printable report of the current in-memory session only
/dev/components    Dev-only: each installed component with real content
*                  404
```

## 6. User journeys

1. **Policyholder after a rejection.** Landing "Check my claim" > `/check-claim` upload (preview, remove) > confirm each fact against its source line > result (verdict stamps, deadlines, plan, letter) > "Open action plan" (checklist) > print/PDF from `/results/:id`.
2. **Helper.** Same, with the "Helping someone" toggle in the navbar (third-person wording, printable summary).
3. **Curious reader / judge.** Landing > How it works > Cases (real, cited) > Privacy.
4. **Lost or expired session.** `/action-plan` or `/results/x` with no session shows an empty/expired state with a link to `/check-claim`.
5. **Service down.** Splash ends, a retry notice explains what happened and what to do; reading pages still work.

## 7. Page specs (summary)

- **Landing**: dark plum hero (heading, supporting copy, two buttons, `ChromaticImage` of the dossier artwork, a draggable `LiquidGlass` chip that states "Rules decide. Models only read."), then ivory sections: the problem (31,490 health complaints, CIO annual report 2023-24, secondary source, cited), what we do, how it works (compressed 6 stages), documents required, how the assessment is structured (read > you confirm > rules decide), illustrative scenarios (labelled illustrative), privacy and transparency, FAQ (accordion), final CTA, footer.
- **About / How it works / Privacy / Help**: editorial pages, English-first body copy, bilingual controls (see section 11).
- **Check claim**: stepper + the existing screens in a `.wf` sheet; new `FileUploader` on step 1.
- **Action plan / Results / Cases / 404**: as in the brief; Cases uses `Carousel` and `DraggableCard`, with a plain list that carries the same information.

## 8. Component inventory

Design system (`ds/`): Button, LinkButton, Card, Container/Section, Field + TextInput/Select, Checkbox, FileUploader, ProgressIndicator (determinate/indeterminate, real values only), Stepper, Modal, Accordion, Toast (provider + live region), Loader, ErrorState, EmptyState, StatusBadge (verdict shapes), ReportSection. Layout: Navbar (Explore disclosure, language, helper toggle), MobileMenu (focus trap), Footer. Installed: LiquidGlass, ChromaticImage, Carousel, DraggableCard (+ our wrappers `GlassChip`, `ArtworkImage`).

## 9. Interaction specs

- Navbar: sticky; Explore is a disclosure button (`aria-expanded`, `aria-controls`), closes on Escape (focus returns to the button), outside click and route change; mobile menu is a modal dialog with focus trap, Escape, close button, `aria-modal`, body scroll lock, focus return.
- Accordion: button per header, `aria-expanded`, `aria-controls`, Arrow Up/Down/Home/End move between headers.
- Uploader: click, keyboard (the file input is a real input), drag and drop, camera capture (existing), client validation (type, 25 MB total) with messages that say what/why/what to do, remove and replace per file, image previews through `URL.createObjectURL` (revoked), PDF shown as a file tile. **No upload progress percentage is shown** because the API client uses `fetch` and the server gives none; the busy state is an indeterminate loader with the existing "Reading your documents..." text (no fake progress).
- Cases: the carousel changes slide by arrows or by clicking a slide; every slide's content is also in the list below it. Draggable cards can be dragged, and every card also has a "Read this case" button, so nothing needs a drag.
- Action-plan checklist: checkbox state lives in React state for the session only.

## 10. Responsive layouts

375 px is the floor (16 px gutters). Hero stacks (text, then artwork, glass chip overlapping the artwork bottom). Navbar collapses to wordmark + CTA + menu button under 1024 px. Card grids go 1 > 2 > 3 columns at 640/1024 px. Touch targets >= 44 px. Draggable card stage becomes a vertical list under 768 px (dragging is a desktop enhancement; the list is the primary content on phones).

## 11. API integration map

| Page | Calls |
|---|---|
| Landing | `GET /health` (splash only) |
| Check claim | existing: `POST /session`, `POST .../extract`, `PUT .../facts`, `POST .../check`, `POST .../explain`, policy routes, `GET .../letter.pdf`, `DELETE /session/{sid}` |
| Action plan, Results | none; read `state.result` (from `/check` and `/explain`) |
| Cases | `GET /gallery`, `GET /gallery/{case_id}` (empty in the current checkout: shows the illustrative scenarios, labelled) |
| About, How it works, Privacy, Help | none |

i18n policy: every interactive control, status and error is bilingual with draft-Hindi markers (Q-007, same mechanism as before). Long editorial copy is English-first; when Hindi is selected each editorial page shows a bilingual notice saying so.

## 12. Deviations (from the brief and from the Aceternity originals)

- **D1 Artwork location.** Brief: `frontend/public/art/`. Shipped: `frontend/src/assets/art/*.svg`, imported as hashed URLs. Reason: FastAPI serves only `/assets/*` (and we may not edit `main.py`); files in `public/` would 404 in production. Dev and tests are unaffected.
- **D2 No demo imagery.** The registry demo files (`carousel-demo`, `draggable-card-demo-2`) point at Unsplash URLs and were not kept in `src/`. Pristine copies of all registry output are in `frontend/vendor/aceternity-originals/` (not compiled). Demo content uses our own SVGs.
- **D3 LiquidGlass: `dangerouslySetInnerHTML` removed.** The original renders its SVG filter with `dangerouslySetInnerHTML` (a string built from numbers and a blob URL, no user data). The project forbids the API, so the same filter is rendered as JSX (`<svg><filter>...`). Behaviour identical. Also: the real component honours `prefers-reduced-transparency` (not reduced motion) and has **no `draggable` prop**; dragging is done by wrapping it in a `motion.div` (our `GlassChip`), which honours reduced motion.
- **D4 Carousel** (`src/components/ui/carousel.tsx`). Original source and classes kept. Changes, each marked `DEVIATION D4` in the file: React 19 `useRef` typing; the idle `requestAnimationFrame` parallax loop is skipped under `prefers-reduced-motion`; `type="button"` and `aria-label` on the arrows, arrows are 44 px (`w-11 h-11`, was `w-10 h-10`) with a palette focus ring instead of `#6D64F7`; the slide button runs `slide.onSelect` and is **not rendered** when there is none (the original button was dead); inactive slides are `aria-hidden` and their image alt is empty; the region has `role="region"`, `aria-roledescription="carousel"`, an `aria-label` prop and a polite live line "n / total: title" (the original `aria-labelledby` pointed at an id that did not exist); `SlideData` is exported and gains optional `alt` and `onSelect`; a text shadow on the slide title for legibility. **Not changed (known gap):** the original markup puts a `div` inside the `ul` around each `li`; left as generated.
- **D5 DraggableCard** (`src/components/ui/draggable-card.tsx`). Original source kept; changes marked `DEVIATION D5`: an unused-parameter fix, and under `prefers-reduced-motion` the card is static (no drag, no pointer tilt, no hover scale). Our wrapper `DraggableScenarios` lays the cards side by side at rest so all text is readable without dragging, renders only at 1024 px and wider, and a "Put the cards back" button resets positions.
- **D6 ChromaticImage** (`src/components/ui/chromatic-image.tsx`). Source **unchanged**. Our wrapper `ArtworkImage` mounts it only through `React.lazy` when a WebGL context can exist and reduced motion is off (the original only zeroes the effect under reduced motion), and falls back to a plain `<img>` with the same alt text while the chunk loads, if it fails to load, without WebGL, and under reduced motion.
- **D7 Fonts.** Display serif is Fraunces (new); Newsreader stays for quote slips only.
- **D8 `/404`.** The server has no client 404 route, so the 404 page is client-side only.
- **D9 Gallery view removed from the workflow.** `/cases` replaces the old in-flow gallery screen; the `#gallery` hash is gone. (`GalleryScreen.tsx` and the old `Chrome.tsx` masthead were retired; the reducer still has the `gallery` view value for type compatibility, and `/check-claim` ignores it.)
- **D10 Role toggle placement.** The "My claim / Helping someone" switch is on `/check-claim` and in the mobile menu, not in the desktop navbar (the navbar already carries the language toggle and the call to action). It still sets the wording app-wide.
- **D11 Delete confirmation.** "Delete my data now" on the result screen now opens a confirmation dialog (HCI: confirm before destructive actions). Phase 1 deleted immediately. The test was updated to match.
- **D12 Uploader.** The upload step uses the new `FileUploader` (validation, previews, replace/remove, allowance meter); the older `FilePicker` remains only for the optional policy upload inside the confirm screen, until STAGE 7.
- **D13 Splash.** It is not shown at all unless initialisation exceeds 150 ms; a normal fast load never shows it.
- **D14 Figures.** The brief says 52,575 is in GROUND_TRUTH; it is only in PRODUCT.md. Only 31,490 (GROUND_TRUTH row "CIO 2023-24 health complaints", confirmed 27 Oct 2026, source CIO Annual Report 2023-24, secondary) is used.

## 13. Implementation sequence

1. Infra (Tailwind, alias, router, tokens, layers); old screens verified. 2. Install the four components; fix typing. 3. Artwork. 4. Design system and layout. 5. Shell, routes, effects, splash. 6. Pages. 7. Re-host workflow, update tests. 8. `impeccable detect`, contrast, DESIGN.md, build, report.

## 14. Risks

1. **No browser QA by the agent.** WebGL, glass refraction (Chromium only; Safari/Firefox get frosted glass by the component's own fallback), layout at 375 px and fonts are verified only by typecheck, build, DOM tests and code reading. The controller must look at them (list in the report).
2. **SVG as WebGL texture.** Browsers differ on SVG intrinsic size; the artwork carries explicit `width`/`height`/`viewBox`.
3. **Bundle size.** `motion` is ~tens of kB gz; it loads only with `/cases` and `/dev/components` and the draggable chip chunk.
4. **Hindi drafts** (Q-007) for ~60 new strings need human review.
5. **Dev-only route in production.** `/dev/components` is registered in the server's route list, so it is reachable in production. It is labelled dev-only and contains no user data.
6. **Gallery empty.** `GET /gallery` returns no cases in this checkout, so Cases shows only illustrative scenarios until cases are published.
7. **Figures.** Only 31,490 (health complaints, CIO 2023-24) is in GROUND_TRUTH. The brief also mentions 52,575; that figure is in PRODUCT.md only, not in GROUND_TRUTH, so it is not used.


## 15. Outcome (as built, 2 Nov 2026)

All four Aceternity components installed from the real registry (`npx --yes shadcn@latest add @aceternity/<name> -y`, registry `https://ui.aceternity.com/registry/{name}.json`, namespace `@aceternity` configured in `components.json`):

| Command | Result | Files created |
|---|---|---|
| `add @aceternity/liquid-glass` | worked | `src/components/ui/liquid-glass.tsx` |
| `add @aceternity/chromatic-image` | worked | `src/components/ui/chromatic-image.tsx` |
| `add @aceternity/carousel-demo` | worked (no fallback name needed) | `src/components/ui/carousel.tsx`, `src/components/carousel-demo.tsx` (demo moved out of `src`, D2) |
| `add @aceternity/draggable-card-demo-2` | worked (no fallback name needed) | `src/components/ui/draggable-card.tsx`, `src/components/draggable-card-demo-2.tsx` (demo moved out of `src`, D2) |

Real-source facts that differ from the brief's description of the demos (verified by reading the generated files): LiquidGlass has no `draggable` prop and honours `prefers-reduced-transparency`, not reduced motion; ChromaticImage props are `src, alt, children, className, backgroundColor, zoom, displacement, chromaticShift, tilt`; Carousel is the default export `Carousel` with `slides` (`title, button, src`); DraggableCard exports `DraggableCardContainer` and `DraggableCardBody`.

Tests: 10 files, 253 tests (phase 1 had 8 files, 140 tests). Contrast: 73 pairs, all pass.
