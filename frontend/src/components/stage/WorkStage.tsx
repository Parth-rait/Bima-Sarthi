import { Suspense, lazy, useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { hasWebGL } from "@/components/landing/ArtworkImage";
import { Boundary } from "@/components/ds/Boundary";
import { useMediaQuery, usePrefersReducedMotion } from "@/hooks/useMedia";
import { cn } from "@/lib/utils";
import type { Key } from "@/i18n";
import { useSession } from "@/state/store";
import type { SceneMode } from "./ClaimScene";

const loadScene = () => import("./ClaimScene");
const ClaimScene = lazy(loadScene);

/** Start fetching three.js before it is needed (a file was chosen, the confirm screen opened), so the scene is ready when the work starts. */
let prefetched = false;
export function prefetchStage() {
  if (prefetched || !canRender3D()) return;
  prefetched = true;
  void loadScene().catch(() => {
    prefetched = false;
  });
}

/** WebGL exists and the device is not obviously low-power (the same ladder the landing sky uses). */
function canRender3D(): boolean {
  if (!hasWebGL()) return false;
  const nav = typeof navigator !== "undefined" ? (navigator as Navigator & { deviceMemory?: number }) : undefined;
  if (nav?.hardwareConcurrency && nav.hardwareConcurrency <= 2) return false;
  if (nav?.deviceMemory && nav.deviceMemory <= 2) return false;
  return true;
}

export type StageStep = { id: string; label: Key; mode: SceneMode };

/**
 * The working moment of the claim flow, shown only while a request is really in flight.
 * Left: a 3D claim file (glass sheets) whose motion matches the request (decorative, aria-hidden).
 * Right: what is happening, in words: the steps of this request with the current one marked, and the real seconds elapsed.
 * Nothing here estimates progress. The screen's own role="status" line stays the live announcement; this panel is not live,
 * so a screen reader hears each change once.
 */
export function WorkStage({ steps, current, slow }: { steps: StageStep[]; current: string; slow: boolean }) {
  const { t } = useSession();
  const reduce = usePrefersReducedMotion();
  const fine = useMediaQuery("(hover: hover) and (pointer: fine)");
  const root = useRef<HTMLDivElement>(null);
  const [three] = useState(canRender3D);
  const [ready, setReady] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const index = Math.max(0, steps.findIndex((s) => s.id === current));
  const mode = steps[index]?.mode ?? "reading";

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  // bring the panel into view when it appears (the button that started the work may be at the bottom of a long form)
  useEffect(() => {
    const el = root.current;
    if (!el || typeof el.scrollIntoView !== "function") return;
    const r = el.getBoundingClientRect();
    if (r.bottom > window.innerHeight || r.top < 0) el.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [reduce]);

  // the glass catches the light where the pointer is (fine pointers only; a CSS custom property, no re-render)
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!fine || reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    e.currentTarget.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  };

  const fallback = <StageFallback mode={mode} />;

  return (
    <div ref={root} className="stage" data-mode={mode} onPointerMove={onMove}>
      <div className="stage-viz" aria-hidden="true">
        {fallback}
        {three ? (
          <Boundary fallback={null}>
            <Suspense fallback={null}>
              <div className={cn("stage-canvas", ready && "is-ready")}>
                <ClaimScene mode={mode} still={reduce} interactive={fine} eventSource={root} onReady={() => setReady(true)} />
              </div>
            </Suspense>
          </Boundary>
        ) : null}
      </div>

      <div className="stage-copy">
        <p className="stage-now">{t(steps[index].label)}</p>
        <ol className="stage-steps" aria-label={t("stage_label")}>
          {steps.map((s, i) => {
            const state = i < index ? "done" : i === index ? "now" : "next";
            return (
              <li key={s.id} data-state={state} aria-current={state === "now" ? "step" : undefined} style={{ "--i": i } as CSSProperties}>
                <span className="stage-dot" aria-hidden="true">
                  {state === "done" ? (
                    <svg viewBox="0 0 16 16" width="12" height="12">
                      <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : null}
                </span>
                <span className="stage-step-text">{t(s.label)}</span>
                <span className="sr-only">, {t(state === "done" ? "stage_done" : state === "now" ? "stage_now" : "stage_next")}</span>
              </li>
            );
          })}
        </ol>
        <p className="stage-time">
          <span className="stage-secs">{seconds}</span> {t("stage_elapsed")}
        </p>
        {slow ? <p className="stage-slow">{t("slow")}</p> : null}
        {three && fine && !reduce ? <p className="stage-hint">{t("stage_hint")}</p> : null}
      </div>
    </div>
  );
}

/**
 * The same file in CSS 3D: shown while three.js loads, and instead of it where WebGL is missing or the device is low-power.
 * Under reduced motion it holds still (operate.css collapses every animation).
 */
function StageFallback({ mode }: { mode: SceneMode }) {
  return (
    <div className="stage-css" data-mode={mode}>
      {[0, 1, 2].map((i) => (
        <div key={i} className="ghost-sheet" data-sheet={i}>
          {Array.from({ length: i === 2 ? 8 : 5 }, (_, j) => (
            <span key={j} className="ghost-line" style={{ "--j": j } as CSSProperties} />
          ))}
          {i === 2 ? <span className="ghost-scan" /> : null}
          {i === 2 ? <span className="ghost-lens" /> : null}
        </div>
      ))}
    </div>
  );
}
