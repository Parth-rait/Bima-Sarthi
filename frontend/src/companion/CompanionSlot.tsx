/**
 * COMPANION SLOT: reserved for the 3D companion (AUREL), a LATER phase. Renders nothing today.
 *
 * Contract (see docs/3D_INTERACTION_SPEC.md):
 *  - The companion's ONLY input is `appActivity` (src/state/activity.ts), derived from real app events.
 *  - It must never read facts, quotes, documents or results. No personal data crosses this boundary.
 *  - It must be dismissible, must honour prefers-reduced-motion, and must have a static fallback.
 *  - Do NOT add three / react-three-fiber / rapier in this phase.
 *
 * The slot is mounted once, in <App />, as a sibling of <main>. It is aria-hidden when it renders.
 */
import type { AppActivity } from "../state/activity";
import { useSession } from "../state/store";

export interface CompanionSlotProps {
  /** Override for tests/storybook. Normally read from the session via useAppActivity(). */
  activity?: AppActivity;
}

export function useAppActivity(): AppActivity {
  return useSession().activity;
}

export function CompanionSlot({ activity }: CompanionSlotProps) {
  const fromApp = useAppActivity();
  const current = activity ?? fromApp;
  void current; // the future companion renders from `current`; nothing is drawn in this phase
  return null;
}
