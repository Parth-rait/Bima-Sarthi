/**
 * appActivity: the ONLY input of the future 3D companion (AUREL, see docs/3D_INTERACTION_SPEC.md).
 *
 * It is derived from real app events (what the app is actually doing right now), never from
 * timers that pretend, never from user mood guesses. One pure function, one place.
 *
 *   idle         nothing in flight, nothing waiting on the user (upload screen, deleted screen, gallery)
 *   reading      documents are being read (extract / policy extract request in flight)
 *   thinking     the written explanation is being produced (explain request in flight)
 *   processing   any other request in flight: saving facts, running the check, fetching the letter or gallery
 *   needs_input  the confirm screen is open and something still needs the user (an unconfirmed fact,
 *                no insurance type chosen, a 409/422 asking for more)
 *   completed    the result is on screen and nothing is in flight
 *   error        the last request failed in a way the user did not cause (offline, expired, reader down)
 *   waiting      a request has been in flight longer than SLOW_AFTER_MS; the server is slow, not stuck
 *
 * Priority when several apply: waiting > (reading | thinking | processing) > error > needs_input > completed > idle.
 */
import type { ApiErrorKind } from "../api/client";

export type AppActivity =
  | "idle"
  | "reading"
  | "thinking"
  | "processing"
  | "needs_input"
  | "completed"
  | "error"
  | "waiting";

export const APP_ACTIVITIES: readonly AppActivity[] = [
  "idle",
  "reading",
  "thinking",
  "processing",
  "needs_input",
  "completed",
  "error",
  "waiting",
];

export type BusyKind =
  | "session"
  | "extract"
  | "policy"
  | "facts"
  | "check"
  | "explain"
  | "letter"
  | "gallery"
  | "delete";

export type ViewName = "upload" | "confirm" | "result" | "gallery" | "deleted";

/** A request that has been in flight this long counts as "waiting". */
export const SLOW_AFTER_MS = 10_000;

export interface ActivityInputs {
  view: ViewName;
  busy: BusyKind | null;
  /** true once the current request has exceeded SLOW_AFTER_MS */
  slow: boolean;
  /** kind of the last failed request, or null if the last request succeeded */
  lastError: ApiErrorKind | null;
  /** facts still marked needs_confirmation (including a missing rejection reason) */
  pendingCount: number;
  /** whether the user has chosen a type of insurance */
  productChosen: boolean;
}

/** Errors that mean "the user has more to do" rather than "something broke". */
const USER_ACTIONABLE: ReadonlySet<ApiErrorKind> = new Set<ApiErrorKind>([
  "needs_confirmation",
  "needs_product_line",
  "validation",
  "conflict",
]);

export function deriveActivity(i: ActivityInputs): AppActivity {
  if (i.busy) {
    if (i.slow) return "waiting";
    if (i.busy === "extract" || i.busy === "policy") return "reading";
    if (i.busy === "explain") return "thinking";
    return "processing";
  }
  if (i.lastError && !USER_ACTIONABLE.has(i.lastError)) return "error";
  if (i.view === "confirm" && (i.pendingCount > 0 || !i.productChosen || (i.lastError && USER_ACTIONABLE.has(i.lastError)))) {
    return "needs_input";
  }
  if (i.view === "result") return "completed";
  return "idle";
}
