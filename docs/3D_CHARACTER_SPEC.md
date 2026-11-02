# 3D character spec: AUREL (planning only)

Status: PLANNING. Nothing in this spec is built. `three`, `@react-three/fiber` and `@react-three/rapier` are NOT installed. The only code that exists is the empty `CompanionSlot` (`frontend/src/companion/CompanionSlot.tsx`) and the `appActivity` state machine input (`frontend/src/state/activity.ts`).

## Who AUREL is
An original, small classical statuette in the spirit of an Apollo of the Belvedere type figure: contrapposto stance, one arm raised, drapery over one shoulder, standing on a low pedestal. It is a sculpture that animates, not a person, mascot animal or cartoon. Colours come from DESIGN.md: aged tan marble or warm plaster body, antique brass base ring and details, a dark plum pedestal. No text, no logo, no insurer or government emblem, no weapon, no religious symbol, no real person's likeness. The Apollo reference is a general art-historical pose; the model is modelled from scratch, not scanned or copied from a museum asset.

Role: a quiet companion that shows the app's real state. It never gives advice, never reacts to document content, never speaks verdicts, and never implies a prediction. It must not make a CHALLENGEABLE result look like good news or a NEED_INFO result look like failure.

## Inputs
One input only: `appActivity` (`idle | reading | thinking | processing | needs_input | completed | error | waiting`), derived by `deriveActivity()` from real events (see `docs/3D_INTERACTION_SPEC.md`). No facts, quotes, names, amounts, dates or document images ever reach the companion.

## State to pose
| appActivity | Pose and motion (skeletal) | Physics (Rapier) |
|---|---|---|
| idle | Slow breathing, weight shift every 8 to 12 s | Rests on the pedestal |
| reading | Head and eyes track down a page that is not shown; raised hand lowers as if holding a scroll | Rests |
| thinking | Chin hand pose, small head tilt | Rests |
| processing | Working loop: hand moves in a small measured arc | Pedestal vibrates very slightly (impulse, damped) |
| needs_input | Turns toward the form, open palm gesture | Rests |
| completed | Brief nod and relaxed arm; then idle | One settle bounce on the pedestal |
| error | Steps back one pace, hands out, still; no shaking | Small tilt then re-settle |
| waiting | Patient stance, occasional glance toward the user | Rests |

Skeletal animation carries every intentional movement (poses, gestures, gaze). Rapier carries only the physical object behaviour: the pedestal and statuette as rigid bodies that can be dragged, thrown a short way, and settle back without ever leaving the viewport.

## Technical plan (later phase)
- Model: one glTF/GLB, under 1.5 MB, 4k triangles or fewer, one 1k texture, baked ambient occlusion. Rig with about 25 bones. Clips: `idle`, `reading`, `thinking`, `processing`, `needs_input`, `completed`, `error`, `waiting`, plus short transitions.
- Runtime: lazy-loaded chunk, never in the main bundle. Mount only on first idle after the app is interactive.
- Low-power and reduced-motion fallback: a static poster image (an SVG or PNG of the pose per state) swapped on state change with a 150 ms cross-fade; no WebGL context is created.
- Switch to the fallback automatically on: `prefers-reduced-motion: reduce`, `navigator.connection.saveData`, `deviceMemory <= 2`, `hardwareConcurrency <= 2`, a WebGL failure, or a frame time over 24 ms for 2 s.
- Dismissible: a visible close button (44px) that remembers the choice for the session in memory only.
- Decorative: `aria-hidden="true"`. State is already announced by the app's own live regions; the companion adds no announcements.
- Budget: under 150 KB gzip of JS for the 3D runtime chunk if possible, under 1.5 MB of assets, 30 fps cap, pause when the tab is hidden.

## Licensing and provenance
All assets are created for this project and licensed to it (record the author and licence in `docs/` when they exist). Libraries (three, r3f, rapier) are MIT; record exact versions when added.

## Open questions
- Who models and rigs AUREL (owner, contractor or generated then retopologised)?
- Should the companion live in a corner on desktop only, or also on a 375px phone? (Default: desktop and tablet, off on phone width.)
- Does Parth's motion template (see MEMORY: visual design waits for the motion template) change the animation language? If yes, this spec is revised first.
