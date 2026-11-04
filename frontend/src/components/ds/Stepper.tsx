import { useEffect, useRef, useState } from "react";

/**
 * Progress through a fixed sequence. The claim flow is gated, so a step you have not earned cannot be opened; a step you
 * have already reached can (pass `reachable` and `onGo`): it becomes a button, so you can trace back to Upload or
 * Confirm from the result and return to the result without running the check again.
 * The current step is aria-current="step"; finished steps carry a tick glyph and a distinct outline (never colour alone).
 *
 * It sticks under the navbar while you work. Once it is stuck it condenses — shorter tabs, a progress line — because a
 * step tracker you have already read should not keep costing you the height it occupied when you first met it.
 * Drawn (claim.css) as one glass capsule with an indigo pill that slides to the current step (--step-i of --step-n);
 * the current label sits on that solid pill, the others on the capsule's >= 80% porcelain.
 */
export function Stepper({
  steps,
  current,
  label,
  reachable = [],
  onGo,
  disabled = false,
  goLabel,
}: {
  steps: Array<{ id: string; text: string }>;
  current: string;
  label: string;
  /** ids of the steps already reached; each one other than the current step becomes a button */
  reachable?: string[];
  onGo?: (id: string) => void;
  /** while the app is busy (reading, checking) no step can be opened */
  disabled?: boolean;
  /** "Go to step: {step}" for assistive tech */
  goLabel?: (text: string) => string;
}) {
  const idx = steps.findIndex((s) => s.id === current);
  const nav = useRef<HTMLElement>(null);
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const el = nav.current;
    if (!el || typeof window === "undefined") return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const navH = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--nav-h")) || 68;
      setStuck(el.getBoundingClientRect().top <= navH + 2);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <nav
      ref={nav}
      aria-label={label}
      className="stepper"
      data-stuck={stuck ? "true" : undefined}
      style={{ ["--step-progress" as string]: `${((idx + 1) / steps.length) * 100}%`, ["--step-i" as string]: String(Math.max(0, idx)), ["--step-n" as string]: String(steps.length) }}
    >
      <ol className="m-0 list-none p-0">
        {steps.map((s, i) => {
          const state = i < idx ? "done" : i === idx ? "current" : "todo";
          return (
            <li
              key={s.id}
              aria-current={state === "current" ? "step" : undefined}
              data-state={state}
              className="step"
            >
              {onGo && state !== "current" && reachable.includes(s.id) ? (
                <button
                  type="button"
                  className="step-go"
                  data-step={s.id}
                  disabled={disabled}
                  aria-label={goLabel ? goLabel(s.text) : undefined}
                  onClick={() => onGo(s.id)}
                >
                  {state === "done" ? <Tick /> : null}
                  {s.text}
                </button>
              ) : (
                <>
                  {state === "done" ? <Tick /> : null}
                  {s.text}
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Tick() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}
