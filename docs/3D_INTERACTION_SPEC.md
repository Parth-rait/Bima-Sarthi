# 3D interaction spec: AUREL companion (planning only)

Status: PLANNING. Nothing here is built. See `docs/3D_CHARACTER_SPEC.md` for the character.

## The rule
The companion shows what the app is really doing. It has exactly one input, `appActivity`, and exactly one state machine. It never reads app data, and nothing it does changes app behaviour.

## The state interface (already in the code)
`frontend/src/state/activity.ts` exports:

```ts
type AppActivity = "idle" | "reading" | "thinking" | "processing" | "needs_input" | "completed" | "error" | "waiting";
function deriveActivity(i: ActivityInputs): AppActivity;
const SLOW_AFTER_MS = 10_000;
```

`frontend/src/companion/CompanionSlot.tsx` exports `CompanionSlot` (renders `null` today) and `useAppActivity()`. The slot is mounted once in `App.tsx`, outside `<main>`.

### Derivation (priority order)
1. A request is in flight and has run longer than `SLOW_AFTER_MS`: `waiting`.
2. A request is in flight: `reading` (extract, policy extract), `thinking` (explain), `processing` (saving facts, the check, the letter, the gallery, delete, session creation).
3. The last request failed in a way the user did not cause (`network`, `expired`, `reader_unavailable`, `unknown`): `error`. A 409 or 422 that asks the user for more is `needs_input`, not `error`.
4. The Confirm screen is open and something still needs the user (an unconfirmed fact, no insurance type chosen, a 409/422): `needs_input`.
5. The Result screen is open: `completed`.
6. Otherwise: `idle`.

### Event table
| Real event | Before | After |
|---|---|---|
| User presses "Read my documents" | idle | reading |
| Extraction returns | reading | needs_input (facts to confirm) |
| Extraction fails 502/503 | reading | error (until the user chooses manual entry) |
| User presses "Run the check" | needs_input | processing |
| Check returns | processing | thinking (explain) then completed |
| Check returns 409 | processing | needs_input |
| Any request passes 10 s | reading/thinking/processing | waiting |
| Session 404 | any | error |
| "Delete my data now" | completed | processing then idle |

## Companion state machine (later phase)
A single reducer `companionReducer(state, event)` with events `activity(a)`, `drag_start`, `drag_end`, `settle`, `dismiss`, `fallback(reason)`. States: `hidden`, `static`, `live`. Within `live`, the pose is a pure function of `appActivity`, plus a transient `dragged` overlay. Pose changes cross-fade over 250 to 400 ms; a pose never restarts if the same activity is re-reported.

## Physics (Rapier) and animation (skeletal) split
- Rapier: pedestal and statuette as rigid bodies; pointer drag applies a spring toward the pointer; release applies damping and a settle to rest; bounds keep it inside a fixed stage (no movement outside its corner, never over the app's controls); sleeping bodies cost no CPU.
- Skeletal clips: every intentional gesture. Never driven by physics.
- A drag is a play interaction only. It never triggers an app action.

## Accessibility and safety
- `aria-hidden`, no focus stops except the dismiss button, which is a real `<button>` with an accessible name, 44px target, keyboard operable.
- No sound. No autoplay media. No flashing.
- `prefers-reduced-motion: reduce` and low-power: static poster mode (see character spec).
- Never overlaps content: it sits in the bottom-right margin on desktop, is hidden under 640px, and respects `env(safe-area-inset-*)`.
- Print: hidden.
- Privacy: no personal data enters the 3D layer; no telemetry about use is sent.

## Tests to write with the feature
- Unit: `deriveActivity` table (exists), `companionReducer` transitions, fallback triggers.
- DOM: `CompanionSlot` renders nothing when dismissed or in static mode with reduced motion; dismiss button is keyboard operable; no 3D chunk is requested when reduced motion is on.
- Budget: a build-size check that the 3D chunk is not in the entry bundle.

## Not now
No `three`, `@react-three/fiber`, `@react-three/rapier` or model assets until this spec is approved and the motion template has arrived.
