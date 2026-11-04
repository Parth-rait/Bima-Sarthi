import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Progress through a fixed sequence. Not links: the claim flow is gated, so a step you have not earned cannot be opened.
 * The current step is aria-current="step"; finished steps carry a tick glyph and a distinct outline (never colour alone).
 *
 * It sticks under the navbar while you work. Once it is stuck it condenses — shorter tabs, a progress line — because a
 * step tracker you have already read should not keep costing you the height it occupied when you first met it.
 * The glass plate behind the tabs is a non-textual surface only: every label sits on a solid tab fill, so no text
 * is ever composited over a blur.
 */
export function Stepper({ steps, current, label }: { steps: Array<{ id: string; text: string }>; current: string; label: string }) {
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
    <nav ref={nav} aria-label={label} className="stepper" data-stuck={stuck ? "true" : undefined} style={{ ["--step-progress" as string]: `${((idx + 1) / steps.length) * 100}%` }}>
      <ol className="m-0 list-none p-0">
        {steps.map((s, i) => {
          const state = i < idx ? "done" : i === idx ? "current" : "todo";
          return (
            <li
              key={s.id}
              aria-current={state === "current" ? "step" : undefined}
              data-state={state}
              className={cn(
                "step",
                state === "current" && "border-ink bg-paper text-ink",
                state === "done" && "border-line-strong bg-peach text-ink",
                state === "todo" && "border-line bg-ivory text-ink-soft",
              )}
            >
              {state === "done" ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                  <path d="m5 12.5 4.5 4.5L19 7.5" />
                </svg>
              ) : null}
              {s.text}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
